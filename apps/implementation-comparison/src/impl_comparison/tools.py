"""Small, policy-guarded tools shared by all comparison systems."""

import re
import os
import heapq
import selectors
import signal
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol

from .policy import Decision, PolicyError, decide_tool, validate_path
from .protocol import ExecutionPolicy, RunLimits
from .telemetry import MetricsAccumulator

MAX_TOOL_MATCHES = 1000


class Tool(Protocol):
    name: str
    read_only: bool
    destructive: bool
    concurrency_safe: bool

    def run(self, arguments: Dict[str, Any], context: "ToolContext") -> Dict[str, Any]:
        ...


class ToolContext:
    def __init__(
        self,
        workspace_root: Path,
        policy: ExecutionPolicy,
        limits: RunLimits = None,
        max_output_chars: int = None,
        approval_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
        metrics: Optional[MetricsAccumulator] = None,
    ):
        self.workspace_root = Path(workspace_root).expanduser().resolve()
        self.policy = policy
        if policy.workspace_root is not None:
            configured_root = Path(policy.workspace_root).expanduser().resolve()
            if configured_root != self.workspace_root:
                raise PolicyError("tool context does not match policy workspace root")
        self.limits = limits or RunLimits()
        self.max_output_chars = (
            self.limits.max_output_chars
            if max_output_chars is None
            else max_output_chars
        )
        if self.max_output_chars <= 0:
            raise ValueError("max_output_chars must be positive")
        self.approval_callback = approval_callback
        self.metrics = metrics

    def path(self, value: Any) -> Path:
        return validate_path(value, self.workspace_root)


class GlobTool:
    name = "glob"
    read_only = True
    destructive = False
    concurrency_safe = True

    def run(self, arguments: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        pattern = str(arguments.get("pattern", "*"))
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise PolicyError("glob pattern is outside the workspace")
        max_matches = _max_matches(arguments)
        def candidates():
            for path in context.workspace_root.glob(pattern):
                validate_path(path, context.workspace_root)
                yield path.relative_to(context.workspace_root).as_posix()

        matches = heapq.nsmallest(max_matches + 1, candidates())
        return {
            "matches": matches[:max_matches],
            "truncated": len(matches) > max_matches,
        }


class ListTool:
    name = "list"
    read_only = True
    destructive = False
    concurrency_safe = True

    def run(self, arguments: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        directory = context.path(arguments.get("path", "."))
        if not directory.is_dir():
            raise NotADirectoryError(str(directory))
        max_matches = _max_matches(arguments)
        entries = heapq.nsmallest(
            max_matches + 1,
            (
                path.relative_to(context.workspace_root).as_posix()
                for path in directory.iterdir()
            ),
        )
        return {
            "entries": entries[:max_matches],
            "truncated": len(entries) > max_matches,
        }


class ReadTool:
    name = "read"
    read_only = True
    destructive = False
    concurrency_safe = True

    def run(self, arguments: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        path = context.path(arguments["path"])
        if not path.is_file():
            raise FileNotFoundError(str(path))
        content, truncated = _read_bounded(path, context.max_output_chars)
        return {
            "path": path.relative_to(context.workspace_root).as_posix(),
            "content": content[: context.max_output_chars],
            "truncated": truncated,
        }


class SearchTool:
    name = "search"
    read_only = True
    destructive = False
    concurrency_safe = True

    def run(self, arguments: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        path = context.path(arguments["path"])
        if not path.is_file():
            raise FileNotFoundError(str(path))
        pattern = str(arguments.get("pattern", ""))
        if not pattern:
            raise ValueError("search pattern must not be empty")
        matcher = re.compile(pattern)
        max_matches = _max_matches(arguments)
        matches = []
        truncated = False
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, 1):
                if matcher.search(line):
                    if len(matches) >= max_matches:
                        truncated = True
                        break
                    matches.append(
                        {
                            "line": line_number,
                            "text": line[: context.max_output_chars],
                        }
                    )
        return {
            "path": path.relative_to(context.workspace_root).as_posix(),
            "matches": matches,
            "truncated": truncated,
        }


class WriteTool:
    name = "write"
    read_only = False
    destructive = False
    concurrency_safe = False

    def run(self, arguments: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        path = context.path(arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(arguments.get("content", "")), encoding="utf-8")
        return {
            "path": path.relative_to(context.workspace_root).as_posix(),
            "bytes": path.stat().st_size,
        }


class EditTool:
    name = "edit"
    read_only = False
    destructive = False
    concurrency_safe = False

    def run(self, arguments: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        path = context.path(arguments["path"])
        content = path.read_text(encoding="utf-8")
        old = str(arguments["old"])
        new = str(arguments.get("new", ""))
        if old not in content:
            raise ValueError("edit target was not found")
        if arguments.get("replace_all", False):
            updated = content.replace(old, new)
        else:
            updated = content.replace(old, new, 1)
        path.write_text(updated, encoding="utf-8")
        return {
            "path": path.relative_to(context.workspace_root).as_posix(),
            "replacements": content.count(old) if arguments.get("replace_all", False) else 1,
        }


class ReplaceTool(EditTool):
    name = "replace"


class ShellTool:
    name = "shell"
    read_only = False
    destructive = True
    concurrency_safe = False

    def run(self, arguments: Dict[str, Any], context: ToolContext) -> Dict[str, Any]:
        command = str(arguments.get("command", "")).strip()
        if not command:
            raise ValueError("shell command must not be empty")
        _reject_shell_escape(command)
        cwd = context.path(arguments.get("cwd", "."))
        if not cwd.is_dir():
            raise NotADirectoryError(str(cwd))
        timeout = min(
            float(arguments.get("timeout_seconds", context.limits.timeout_seconds)),
            context.limits.timeout_seconds,
        )
        stdout, stderr, returncode, timed_out, truncated, limit_hit = _run_bounded_shell(
            command, cwd, timeout, context.max_output_chars
        )
        output = stdout + stderr
        error = None
        if timed_out:
            error = {"code": "timeout", "message": "command exceeded its timeout"}
        elif limit_hit:
            error = {
                "code": "output_limit",
                "message": "command exceeded its output limit",
            }
        elif returncode:
            error = {
                "code": "nonzero_exit",
                "message": "command exited with status {}".format(returncode),
            }
        return {
            "ok": error is None,
            "stdout": stdout,
            "stderr": stderr,
            "output": output,
            "returncode": returncode,
            "timed_out": timed_out,
            "truncated": truncated,
            "error": error,
        }


def _read_bounded(path: Path, limit: int):
    with path.open("rb") as handle:
        raw = handle.read(limit + 1)
    truncated = len(raw) > limit
    return raw[:limit].decode("utf-8", errors="replace"), truncated


def _max_matches(arguments: Dict[str, Any]) -> int:
    value = int(arguments.get("max_matches", 100))
    if value <= 0 or value > MAX_TOOL_MATCHES:
        raise ValueError(
            "max_matches must be between one and {}".format(MAX_TOOL_MATCHES)
        )
    return value


def _run_bounded_shell(command, cwd, timeout, output_limit):
    process = subprocess.Popen(
        command,
        shell=True,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout
    timed_out = False
    limit_hit = False

    try:
        while selector.get_map():
            remaining_time = deadline - time.monotonic()
            if remaining_time <= 0:
                timed_out = True
                _terminate_process_group(process)
                break
            for key, _ in selector.select(remaining_time):
                stream = key.fileobj
                label = key.data
                chunk = os.read(stream.fileno(), min(65536, output_limit + 1))
                if not chunk:
                    selector.unregister(stream)
                    continue
                remaining_output = output_limit - sum(
                    len(value) for value in buffers.values()
                )
                if len(chunk) > remaining_output:
                    if remaining_output > 0:
                        buffers[label].extend(chunk[:remaining_output])
                    limit_hit = True
                    _terminate_process_group(process)
                    selector.close()
                    return (
                        _as_text(bytes(buffers["stdout"])),
                        _as_text(bytes(buffers["stderr"])),
                        process.returncode,
                        False,
                        True,
                        True,
                    )
                buffers[label].extend(chunk)
        if timed_out:
            selector.close()
        else:
            process.wait()
    finally:
        selector.close()
        if process.poll() is None:
            _terminate_process_group(process)
    return (
        _as_text(bytes(buffers["stdout"])),
        _as_text(bytes(buffers["stderr"])),
        process.returncode,
        timed_out,
        False,
        limit_hit,
    )


def _terminate_process_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (OSError, AttributeError):
        process.terminate()
    try:
        process.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (OSError, AttributeError):
            process.kill()
        process.wait()


def _reject_shell_escape(command: str) -> None:
    if re.search(r"(?:^|[;&|])\s*cd\s+(?:/|~|\.\.)", command):
        raise PolicyError("shell command changes to an external directory")
    if re.search(
        r"(?:--(?:directory|cwd)|-(?:C|w))\s*(?:=|\s+)(?:/|~|\.\.)",
        command,
    ):
        raise PolicyError("shell command selects an external working directory")


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool] = ()):
        self._tools = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError("tool already registered: {}".format(tool.name))
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise PolicyError("unknown tool: {}".format(name)) from exc

    def names(self) -> List[str]:
        return sorted(self._tools)

    def execute_many(
        self,
        calls,
        context: ToolContext,
        max_workers: int = 4,
    ) -> List[Dict[str, Any]]:
        """Run safe reads in bounded batches and mutations serially."""
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")
        calls = list(calls)
        results = []
        index = 0
        while index < len(calls):
            name, arguments = _split_call(calls[index])
            tool = self.get(name)
            if tool.read_only and tool.concurrency_safe:
                batch = []
                while index < len(calls):
                    next_name, next_arguments = _split_call(calls[index])
                    next_tool = self.get(next_name)
                    if not (
                        next_tool.read_only and next_tool.concurrency_safe
                    ):
                        break
                    batch.append((next_name, next_arguments))
                    index += 1
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    results.extend(
                        pool.map(
                            lambda call: self.execute(call[0], call[1], context),
                            batch,
                        )
                    )
            else:
                results.append(self.execute(name, arguments, context))
                index += 1
        return results

    def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: ToolContext,
        approval_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
    ) -> Dict[str, Any]:
        tool = self.get(name)
        if context.metrics is not None:
            context.metrics.record_tool_call()
        decision = decide_tool(
            tool.name, tool.read_only, tool.destructive, context.policy
        )
        if decision is Decision.ASK:
            callback = approval_callback or context.approval_callback
            if (
                context.policy.headless
                or callback is None
                or not callback(name, arguments)
            ):
                raise PolicyError("tool {} requires approval".format(tool.name))
        elif decision is not Decision.ALLOW:
            raise PolicyError(
                "tool {} is not allowed ({})".format(tool.name, decision.value)
            )
        return tool.run(arguments, context)


def _split_call(call):
    if isinstance(call, dict):
        return call["name"], call.get("arguments", {})
    return call[0], call[1]


def default_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            GlobTool(),
            ListTool(),
            ReadTool(),
            SearchTool(),
            WriteTool(),
            EditTool(),
            ShellTool(),
        ]
    )


def _function_schema(name, description, properties, required=None):
    parameters = {
        "type": "object",
        "properties": properties,
    }
    if required:
        parameters["required"] = list(required)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def default_tool_schemas() -> List[Dict[str, Any]]:
    """OpenAI function-calling schemas for the default registry tools."""
    return [
        _function_schema(
            "glob",
            "Find files in the workspace matching a glob pattern.",
            {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern relative to the workspace root. Defaults to '*'.",
                },
                "max_matches": {
                    "type": "integer",
                    "description": "Maximum number of matches to return (1-1000). Defaults to 100.",
                },
            },
        ),
        _function_schema(
            "list",
            "List entries in a workspace directory.",
            {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to the workspace root. Defaults to '.'.",
                },
                "max_matches": {
                    "type": "integer",
                    "description": "Maximum number of entries to return (1-1000). Defaults to 100.",
                },
            },
        ),
        _function_schema(
            "read",
            "Read a text file from the workspace.",
            {
                "path": {
                    "type": "string",
                    "description": "File path relative to the workspace root.",
                },
            },
            required=["path"],
        ),
        _function_schema(
            "search",
            "Search a workspace file for a regular-expression pattern.",
            {
                "path": {
                    "type": "string",
                    "description": "File path relative to the workspace root.",
                },
                "pattern": {
                    "type": "string",
                    "description": "Regular expression to search for. Must not be empty.",
                },
                "max_matches": {
                    "type": "integer",
                    "description": "Maximum number of matches to return (1-1000). Defaults to 100.",
                },
            },
            required=["path", "pattern"],
        ),
        _function_schema(
            "write",
            "Create or overwrite a text file in the workspace.",
            {
                "path": {
                    "type": "string",
                    "description": "File path relative to the workspace root.",
                },
                "content": {
                    "type": "string",
                    "description": "File contents to write. Defaults to an empty string.",
                },
            },
            required=["path"],
        ),
        _function_schema(
            "edit",
            "Replace text in a workspace file.",
            {
                "path": {
                    "type": "string",
                    "description": "File path relative to the workspace root.",
                },
                "old": {
                    "type": "string",
                    "description": "Exact text to replace. Must already exist in the file.",
                },
                "new": {
                    "type": "string",
                    "description": "Replacement text. Defaults to an empty string.",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "If true, replace every occurrence. Defaults to false.",
                },
            },
            required=["path", "old"],
        ),
        _function_schema(
            "shell",
            "Run a shell command in the workspace.",
            {
                "command": {
                    "type": "string",
                    "description": "Shell command to run. Must not be empty.",
                },
                "cwd": {
                    "type": "string",
                    "description": "Working directory relative to the workspace root. Defaults to '.'.",
                },
                "timeout_seconds": {
                    "type": "number",
                    "description": "Command timeout in seconds, capped by the run limit.",
                },
            },
            required=["command"],
        ),
    ]

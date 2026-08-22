"""Creation and validation of isolated run artifact directories."""

from pathlib import Path
import os
import re
import shutil
from typing import Optional, Union
import uuid

from .security import sanitize_source_file

class WorkspacePathError(ValueError):
    pass


class WorkspaceManager:
    def __init__(self, root: Union[str, Path]):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.runs_root = self.root / "runs"
        self.runs_root.mkdir(exist_ok=True)
        self._attempts = set()

    def create_attempt(
        self, task_id: str, attempt_id: Optional[str] = None
    ) -> Path:
        if not task_id.strip():
            raise ValueError("task_id must not be empty")
        safe_task = _safe_component(task_id)
        safe_attempt = _safe_component(attempt_id or uuid.uuid4().hex)
        attempt = (self.runs_root / safe_task / safe_attempt).resolve()
        self._ensure_contained(attempt)
        if attempt.exists():
            raise FileExistsError(str(attempt))
        attempt.mkdir(parents=True)
        # Deliberately create an empty directory; source files and secrets are
        # never copied into an attempt workspace.
        self._attempts.add(attempt)
        return attempt

    def validate_attempt(self, attempt_dir: Union[str, Path]) -> Path:
        attempt = Path(attempt_dir).expanduser().resolve()
        if attempt not in self._attempts:
            raise WorkspacePathError("attempt directory is not registered")
        return attempt

    def discard_attempt(self, attempt_dir: Union[str, Path]) -> None:
        attempt = self.validate_attempt(attempt_dir)
        shutil.rmtree(attempt, ignore_errors=True)
        self._attempts.discard(attempt)
        try:
            attempt.parent.rmdir()
        except OSError:
            pass

    def validate_artifact_path(
        self, attempt_dir: Union[str, Path], relative_path: Union[str, Path]
    ) -> Path:
        attempt = self.validate_attempt(attempt_dir)
        candidate = Path(relative_path).expanduser()
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (attempt / candidate).resolve()
        try:
            resolved.relative_to(attempt)
        except ValueError as exc:
            raise WorkspacePathError("artifact path is outside the attempt") from exc
        return resolved

    def create_workspace(
        self, attempt_dir: Union[str, Path], source: Union[str, Path]
    ) -> Path:
        """Create an isolated source snapshot beneath a registered attempt."""
        attempt = self.validate_attempt(attempt_dir)
        source_path = Path(source).expanduser().resolve()
        if not source_path.is_dir():
            raise WorkspacePathError("source workspace is not a directory")
        if _is_within(source_path, attempt):
            raise WorkspacePathError("source workspace is inside the attempt")
        workspace = attempt / "workspace"
        workspace.mkdir()
        if source_path == self.root:
            return workspace
        destination_roots = (attempt,)
        if _is_within(self.root, source_path):
            destination_roots = (self.root, attempt)
        for current, directories, files in os.walk(source_path):
            current_path = Path(current)
            directories[:] = [
                name
                for name in directories
                if not _excluded_directory(name)
                and not _is_destination_subtree(
                    current_path / name, destination_roots
                )
            ]
            relative = current_path.relative_to(source_path)
            target_dir = workspace / relative
            target_dir.mkdir(parents=True, exist_ok=True)
            for name in files:
                source_file = current_path / name
                if _excluded_file(name) or source_file.is_symlink():
                    continue
                target_file = target_dir / name
                _copy_source_file(source_file, target_file)
        return workspace

    def _ensure_contained(self, path: Path) -> None:
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise WorkspacePathError("workspace path is outside the root") from exc


def _safe_component(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise WorkspacePathError("invalid workspace component")
    return value


def _excluded_directory(name: str) -> bool:
    return name.lower() in {
        ".git",
        ".venv",
        "venv",
        "env",
        "runs",
        "worktrees",
        "cache",
        ".cache",
        "__pycache__",
        ".pytest_cache",
    }


def _excluded_file(name: str) -> bool:
    lowered = name.lower()
    if lowered == ".env" or lowered.startswith(".env."):
        return True
    if lowered.endswith((".pem", ".key")):
        return True
    if lowered in {".npmrc", ".pypirc"}:
        return True
    return bool(
        re.search(r"(credential|secret|password|token|api[_-]?key)", lowered)
    )


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_destination_subtree(path: Path, destination_roots) -> bool:
    resolved = path.resolve()
    return any(_is_within(resolved, root.resolve()) for root in destination_roots)


def _copy_source_file(source: Path, target: Path) -> None:
    sanitize_source_file(source, target)
    if target.exists():
        shutil.copystat(source, target)

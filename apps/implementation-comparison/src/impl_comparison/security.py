"""Small, conservative redaction helpers for persisted run artifacts."""

import re
from pathlib import Path
from typing import Any


_SECRET_KEY = re.compile(
    r"(?:api[_-]?key|access[_-]?token|secret|password|credential|private[_-]?key)",
    re.IGNORECASE,
)
_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
    re.compile(r"hf_[A-Za-z0-9_-]{16,}"),
)
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b((?:[A-Za-z][A-Za-z0-9-]*[-_])?"
    r"(?:API[-_]?KEY|PRIVATE[-_]?KEY|ACCESS[-_]?TOKEN|TOKEN|SECRET|PASSWORD))"
    r"\s*=\s*(['\"]?)([^\s,;\"'}]+)\2"
)
_AUTHORIZATION_PATTERN = re.compile(
    r"(?i)\b(authorization\s*:\s*bearer|bearer)\s+"
    r"([A-Za-z0-9._~+/=-]{16,})"
)
_STRUCTURED_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)([\"']?(?:[A-Za-z][A-Za-z0-9_-]*[-_])?"
    r"(?:API[-_]?KEY|PRIVATE[-_]?KEY|ACCESS[-_]?TOKEN|TOKEN|SECRET|PASSWORD)"
    r"[\"']?\s*:\s*[\"']?)([^\s,\"'}]+)"
)
_BINARY_SECRET_PATTERNS = (
    re.compile(rb"sk-ant-[A-Za-z0-9_-]{16,}"),
    re.compile(rb"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(rb"AIza[A-Za-z0-9_-]{20,}"),
    re.compile(rb"hf_[A-Za-z0-9_-]{16,}"),
    re.compile(rb"(?i)bearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(
        rb"(?i)\b[\"']?(?:[A-Za-z][A-Za-z0-9_-]*[-_])?"
        rb"(?:API[-_]?KEY|PRIVATE[-_]?KEY|ACCESS[-_]?TOKEN|TOKEN|SECRET|PASSWORD)"
        rb"[\"']?\s*[:=]\s*"
        rb"['\"]?[^\s,;'\"]+"
    ),
)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _SECRET_KEY.search(str(key)) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    if isinstance(value, str):
        redacted = value
        redacted = _ASSIGNMENT_PATTERN.sub(
            lambda match: "{}=[REDACTED]".format(match.group(1)),
            redacted,
        )
        redacted = _STRUCTURED_ASSIGNMENT_PATTERN.sub(
            lambda match: "{}[REDACTED]".format(match.group(1)),
            redacted,
        )
        redacted = _AUTHORIZATION_PATTERN.sub(
            lambda match: "{} [REDACTED]".format(match.group(1)),
            redacted,
        )
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    return value


def sanitize_bytes(data: bytes):
    """Return redacted bytes, or ``None`` when unsafe binary content is found."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        if _contains_sensitive_bytes(data):
            return None
        return data
    return redact_sensitive(text).encode("utf-8")


def sanitize_artifact_tree(root: Path) -> None:
    """Redact or remove sensitive files created during a run."""
    for path in Path(root).rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if path.stat().st_size > MAX_SCAN_BYTES:
            if _stream_contains_sensitive_bytes(path):
                path.unlink()
            continue
        data = path.read_bytes()
        sanitized = sanitize_bytes(data)
        if sanitized is None:
            path.unlink()
        elif sanitized != data:
            path.write_bytes(sanitized)


MAX_SCAN_BYTES = 1024 * 1024
SCAN_CHUNK_SIZE = 64 * 1024


def sanitize_source_file(source: Path, target: Path) -> None:
    if source.stat().st_size > MAX_SCAN_BYTES:
        if _stream_contains_sensitive_bytes(source):
            return
        with source.open("rb") as source_handle, target.open("wb") as target_handle:
            while True:
                chunk = source_handle.read(SCAN_CHUNK_SIZE)
                if not chunk:
                    break
                target_handle.write(chunk)
        return
    sanitized = sanitize_bytes(source.read_bytes())
    if sanitized is not None:
        target.write_bytes(sanitized)


def _contains_sensitive_bytes(data: bytes) -> bool:
    return any(pattern.search(data) for pattern in _BINARY_SECRET_PATTERNS)


def _stream_contains_sensitive_bytes(path: Path) -> bool:
    overlap = b""
    max_pattern_size = 128
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(SCAN_CHUNK_SIZE)
            if not chunk:
                return _contains_sensitive_bytes(overlap)
            data = overlap + chunk
            if _contains_sensitive_bytes(data):
                return True
            overlap = data[-max_pattern_size:]

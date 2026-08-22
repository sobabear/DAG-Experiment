"""Append-only JSONL run event recording."""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .security import redact_sensitive

EVENT_TYPES = frozenset(
    {
        "run_started",
        "turn_started",
        "model_request",
        "model_response",
        "tool_requested",
        "permission_decision",
        "tool_started",
        "tool_finished",
        "child_started",
        "child_finished",
        "run_finished",
    }
)


class EventLog:
    event_types = EVENT_TYPES

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, **payload: Any) -> None:
        if not event_type.strip():
            raise ValueError("event type must not be empty")
        if event_type not in self.event_types:
            raise ValueError("unsupported event type: {}".format(event_type))
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
        }
        record.update(redact_sensitive(payload))
        record["type"] = event_type
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
            handle.flush()

    emit = append

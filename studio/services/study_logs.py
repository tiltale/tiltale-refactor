"""Local JSONL study-log storage and result summaries.

The local preview uses one Django process, so a process-wide lock is sufficient
to serialize appends. A deployed study should post to a real collector. Every
event includes ``session_id`` and increasing ``seq`` so a remote collector can
deduplicate retries safely.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from typing import Any

from django.conf import settings

LOG_LOCK = threading.Lock()
SESSION_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_-]{8,120}$")


@dataclass(frozen=True, slots=True)
class SessionSummary:
    session_id: str
    event_count: int
    first_timestamp: str
    last_timestamp: str
    last_frame: str
    file_name: str


def _log_path(session_id: str) -> Path:
    if not SESSION_PATTERN.fullmatch(session_id):
        raise ValueError("Invalid session ID.")
    return settings.PROJECT_DIR / "logs" / f"{session_id}.jsonl"


def append_event(event: dict[str, Any]) -> None:
    session_id: str = str(event.get("session_id", ""))
    path: Path = _log_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized: dict[str, Any] = {
        **event,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    line: str = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    with LOG_LOCK:
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")


def read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value: Any = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path.name}, line {line_number}: invalid JSON.") from error
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}, line {line_number}: event must be a JSON object.")
            events.append(value)
    return events


def session_summaries() -> list[SessionSummary]:
    root: Path = settings.PROJECT_DIR / "logs"
    if not root.is_dir():
        return []
    summaries: list[SessionSummary] = []
    for path in root.glob("*.jsonl"):
        try:
            events = read_events(path)
        except ValueError:
            continue
        if not events:
            continue
        first: dict[str, Any] = events[0]
        last: dict[str, Any] = events[-1]
        last_frame: str = ""
        for event in reversed(events):
            frame: object = event.get("frame")
            if isinstance(frame, str) and frame:
                last_frame = frame
                break
        summaries.append(
            SessionSummary(
                session_id=str(first.get("session_id", path.stem)),
                event_count=len(events),
                first_timestamp=str(first.get("timestamp", first.get("received_at", ""))),
                last_timestamp=str(last.get("timestamp", last.get("received_at", ""))),
                last_frame=last_frame,
                file_name=path.name,
            )
        )
    return sorted(summaries, key=lambda item: item.last_timestamp, reverse=True)


def import_jsonl(uploaded_name: str, data: bytes) -> Path:
    """Validate imported JSONL before writing it into /project/logs."""
    text: str = data.decode("utf-8-sig")
    parsed: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value: Any = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Line {line_number} is not valid JSON.") from error
        if not isinstance(value, dict) or not value.get("session_id"):
            raise ValueError(f"Line {line_number} needs a session_id.")
        parsed.append(value)
    if not parsed:
        raise ValueError("The uploaded log contains no events.")

    first_session: str = str(parsed[0]["session_id"])
    _log_path(first_session)  # validates the ID
    if any(str(event["session_id"]) != first_session for event in parsed):
        raise ValueError("One imported JSONL file must contain exactly one session_id.")
    stem: str = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(uploaded_name).stem).strip("-")
    destination: Path = settings.PROJECT_DIR / "logs" / f"{stem or first_session}.jsonl"
    destination.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) for item in parsed) + "\n",
        encoding="utf-8",
    )
    return destination

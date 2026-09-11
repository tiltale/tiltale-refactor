"""Study logs: one JSONL file per participant *visit*.

The story runtime posts every event to ``log.php`` on the web server, or to
the studio's stand-in for it during local preview. Both name files the same way::

    <participant_id>--<visit_id>.jsonl      (unsafe characters become "-")

A visit is one page load, so a participant who opens the link twice (for
example after a crash) gets a second file and nothing is overwritten.

JSONL = one JSON object per line: every event is appended immediately and an
interrupted write can only damage the last line, never the earlier ones.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
from typing import Any

from django.conf import settings

FINISHED_EVENT: str = "Story finished"
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")
_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class SessionSummary:
    file_name: str
    participant_id: str
    visit_id: str
    language: str
    event_count: int
    started: str
    last_frame: str
    finished: bool
    kind: str  # "study", "preview" or "play-test"
    events: tuple[dict[str, Any], ...]


def logs_dir() -> Path:
    return settings.PROJECT_DIR / "logs"


def safe_name(value: object) -> str:
    """Same rule as runtime/log.php and runtime/tiltale.js."""
    return _UNSAFE.sub("-", str(value)).strip("-")[:80]


def log_file_name(event: dict[str, Any]) -> str:
    participant, visit = safe_name(event.get("participant_id", "")), safe_name(event.get("visit_id", ""))
    if not participant or not visit or not isinstance(event.get("event"), str):
        raise ValueError("A log event needs participant_id, visit_id and event.")
    return f"{participant}--{visit}.jsonl"


def append_event(event: dict[str, Any]) -> None:
    path: Path = logs_dir() / log_file_name(event)
    line: str = json.dumps({**event, "received_at": datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)
    with _lock, path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def parse_events(text: str, source: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value: Any = json.loads(line)
        except json.JSONDecodeError:
            raise ValueError(f"{source}, line {number}: not valid JSON.") from None
        if not isinstance(value, dict):
            raise ValueError(f"{source}, line {number}: each line must be a JSON object.")
        events.append(value)
    return events


def read_events(path: Path) -> list[dict[str, Any]]:
    return parse_events(path.read_text(encoding="utf-8-sig"), path.name)


def session_kind(participant_id: str) -> str:
    for prefix, kind in (("playtest-", "play-test"), ("preview-", "preview")):
        if participant_id.startswith(prefix):
            return kind
    return "study"


def session_summaries() -> list[SessionSummary]:
    summaries: list[SessionSummary] = []
    for path in logs_dir().glob("*.jsonl"):
        try:
            events = read_events(path)
        except ValueError:
            continue
        if not events:
            continue
        first: dict[str, Any] = events[0]
        participant: str = str(first.get("participant_id", ""))
        frames: list[str] = [str(event["frame"]) for event in events if event.get("frame")]
        summaries.append(SessionSummary(
            file_name=path.name,
            participant_id=participant,
            visit_id=str(first.get("visit_id", "")),
            language=next((str(e["language"]) for e in reversed(events) if e.get("language")), ""),
            event_count=len(events),
            started=str(first.get("timestamp", "")),
            last_frame=frames[-1] if frames else "",
            finished=any(event.get("event") == FINISHED_EVENT for event in events),
            kind=session_kind(participant),
            events=tuple(events),
        ))
    return sorted(summaries, key=lambda item: item.started, reverse=True)


def _time(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def frame_visits(events: list[dict[str, Any]]) -> list[tuple[str, float | None]]:
    """Frames in the order shown, each with the seconds until the next frame (``None`` for the last one)."""
    stops = [event for event in events if event.get("event") in ("frame", FINISHED_EVENT)]
    visits: list[tuple[str, float | None]] = []
    for current, following in zip(stops, [*stops[1:], None]):
        if current["event"] != "frame":
            continue
        seconds = None if following is None else (_time(following["timestamp"]) - _time(current["timestamp"])).total_seconds()
        visits.append((str(current.get("frame", "")), seconds))
    return visits


def readable_events(events: list[dict[str, Any]], frame_names: dict[str, str], element_labels: dict[int, str]) -> list[str]:
    """One plain-English line per event, e.g. ``Intro scene: visited for 12 s``."""
    durations = iter(seconds for _key, seconds in frame_visits(events))
    lines: list[str] = []
    for event in events:
        kind = str(event.get("event", ""))
        frame: str = frame_names.get(str(event.get("frame", "")), str(event.get("frame", "")))
        if kind == "frame":
            seconds = next(durations)
            if event.get("how") == "resumed":
                lines.append("IDN refreshed")
            lines.append(f"{frame}: visited (last frame)" if seconds is None else f"{frame}: visited for {seconds:.0f} s")
        elif kind == "choice":
            label = element_labels.get(event.get("element_id"), str(event.get("component", "element")))
            lines.append(f"{frame}: clicked '{label}'")
        else:
            lines.append(kind)
    return lines


def session_record(summary: SessionSummary, frame_names: dict[str, str], element_labels: dict[int, str]) -> dict[str, Any]:
    """Everything the Results page shows for one visit: the list entry, its timeline and the path for the flowchart."""
    return {
        "file_name": summary.file_name, "participant_id": summary.participant_id, "kind": summary.kind,
        "language": summary.language, "event_count": summary.event_count, "finished": summary.finished,
        "started": summary.started,
        "started_label": _time(summary.started).strftime("%d %b %Y, %H:%M UTC") if summary.started else "",
        "frames": frame_visits(summary.events),
        "choices": [event["element_id"] for event in summary.events if event.get("event") == "choice" and event.get("element_id") is not None],
        "lines": readable_events(summary.events, frame_names, element_labels),
    }


def import_jsonl(file_name: str, data: bytes) -> Path:
    """Store one downloaded server log in /project/logs/ without overwriting anything."""
    try:
        events = parse_events(data.decode("utf-8-sig"), file_name)
    except UnicodeDecodeError:
        raise ValueError(f"{file_name} is not a UTF-8 text file.") from None
    if not events:
        raise ValueError(f"{file_name} contains no events.")
    names: set[str] = {log_file_name(event) for event in events}
    if len(names) != 1:
        raise ValueError(f"{file_name} must contain exactly one participant visit.")
    destination: Path = logs_dir() / names.pop()
    if destination.exists():
        raise ValueError(f"{destination.name} is already in /project/logs/.")
    destination.write_text("".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events), encoding="utf-8")
    return destination

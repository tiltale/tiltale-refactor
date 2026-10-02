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

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from django.conf import settings

from .log_keys import LockedLog, decrypt_event, encrypt_event, is_encrypted

FINISHED_EVENT: str = "Story finished"
DECISION_EVENT: str = "decision"  # a validation point chose a path (frame, element_id "rule-7", target, variables)
VARIABLE_EVENT: str = "variable"  # a global variable changed (variable, from, to)
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
    device: str  # "iPhone · Safari · 390×844", from the visit header
    local_time: str  # the participant's own clock at the start, with UTC offset
    events: tuple[dict[str, Any], ...]


def logs_dir() -> Path:
    """``/project/logs/``, made if it is gone (as ``log.php`` does on the server)."""
    path: Path = settings.PROJECT_DIR / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_name(value: object) -> str:
    """Same rule as runtime/log.php and runtime/tiltale.js."""
    return _UNSAFE.sub("-", str(value)).strip("-")[:80]


def log_file_name(event: dict[str, Any]) -> str:
    participant, visit = safe_name(event.get("participant_id", "")), safe_name(event.get("visit_id", ""))
    if not participant or not visit or not isinstance(event.get("event"), str):
        raise ValueError("A log event needs participant_id, visit_id and event.")
    return f"{participant}--{visit}.jsonl"


def append_event(event: dict[str, Any], public_key: str = "") -> None:
    """Write one preview or play-test event, encrypted like log.php does when the project has a key
    (``public_key``). TILTALE_PLAIN_LOCAL_LOGS=1 in the environment keeps local logs readable for developers."""
    path: Path = logs_dir() / log_file_name(event)
    received: dict[str, Any] = {**event, "received_at": datetime.now(timezone.utc).isoformat()}
    line: str = encrypt_event(received, public_key) if public_key else json.dumps(received, ensure_ascii=False)
    with _lock, path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def parse_events(text: str, source: str, key: RSAPrivateKey | None = None) -> list[dict[str, Any]]:
    """The events in a log file. Lines written by ``log.php`` with a key are decrypted with ``key``."""
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
        if is_encrypted(value) and key is None:
            raise LockedLog(f"{source} is encrypted: provide the project's key file first.")
        events.append(decrypt_event(value, key) if is_encrypted(value) and key else value)
    return events


def read_events(path: Path, key: RSAPrivateKey | None = None) -> list[dict[str, Any]]:
    return parse_events(path.read_text(encoding="utf-8-sig"), path.name, key)


VISIT_EVENT: str = "visit"  # the header line tiltale.js writes first: local time, screen, browser
ERROR_EVENT: str = "error"  # tiltale.js logs every JavaScript error (message, file, line)
UNSUPPORTED_EVENT: str = "Browser not supported"  # a browser too old for the story got a message instead; its only line

_BROWSERS: tuple[tuple[str, str], ...] = (  # order matters: Edge and Samsung say "Chrome" too, Chrome says "Safari"
    ("Edg/", "Edge"), ("SamsungBrowser/", "Samsung Internet"), ("OPR/", "Opera"), ("Firefox/", "Firefox"),
    ("FxiOS/", "Firefox"), ("CriOS/", "Chrome"), ("Chrome/", "Chrome"), ("Safari/", "Safari"),
)
_DEVICES: tuple[tuple[str, str], ...] = (
    ("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"),
    ("Macintosh", "Mac"), ("CrOS", "Chromebook"), ("Linux", "Linux"),
)


def describe_visit(header: dict[str, Any]) -> str:
    """``iPhone · Safari · 390×844`` from the visit header, as far as the browser told us."""
    agent: str = str(header.get("user_agent", ""))
    device: str = next((name for needle, name in _DEVICES if needle in agent), "")
    model = re.search(r"Android [^;]*; ([^;)]+?)(?: Build|\))", agent)  # "SM-G991B" on most Android phones
    if device == "Android" and model:
        device = f"Android ({model.group(1).strip()})"
    browser: str = next((name for needle, name in _BROWSERS if needle in agent), "")
    screen: Any = header.get("screen") or {}
    size: str = f"{screen.get('width')}×{screen.get('height')}" if screen.get("width") else ""
    return " · ".join(part for part in (device, browser, size) if part)


def session_kind(participant_id: str) -> str:
    for prefix, kind in (("playtest-", "play-test"), ("preview-", "preview")):
        if participant_id.startswith(prefix):
            return kind
    return "study"


def session_summaries(key: RSAPrivateKey | None = None) -> list[SessionSummary]:
    summaries: list[SessionSummary] = []
    for path in logs_dir().glob("*.jsonl"):
        try:
            events = read_events(path, key)
        except ValueError:  # damaged, or encrypted while no key is given
            continue
        if not events:
            continue
        first: dict[str, Any] = events[0]
        participant: str = str(first.get("participant_id", ""))
        frames: list[str] = [str(event["frame"]) for event in events if event.get("frame")]
        header: dict[str, Any] = next((event for event in events if event.get("event") in (VISIT_EVENT, UNSUPPORTED_EVENT)), {})
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
            device=describe_visit(header),
            local_time=str(header.get("local_time", "")),
            events=tuple(events),
        ))
    return sorted(summaries, key=lambda item: item.started, reverse=True)


def device_report(summaries: list[SessionSummary]) -> list[dict[str, Any]]:
    """One row per device: visits, finished visits, JavaScript errors and "browser too old" visits.

    Read this after play-tests on real phones and after a study: a device with errors or
    without finished visits is where the story struggles. Problems sort to the top.
    """
    rows: dict[str, dict[str, Any]] = {}
    for summary in summaries:
        kinds: list[str] = [str(event.get("event", "")) for event in summary.events]
        row = rows.setdefault(summary.device or "Unknown device", {
            "device": summary.device or "Unknown device", "visits": 0, "finished": 0, "errors": 0, "unsupported": 0,
        })
        row["visits"] += 1
        row["finished"] += summary.finished
        row["errors"] += kinds.count(ERROR_EVENT)
        row["unsupported"] += UNSUPPORTED_EVENT in kinds
    return sorted(rows.values(), key=lambda row: (-row["errors"] - row["unsupported"], -row["visits"], row["device"]))


def _time(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


def frame_visits(events: list[dict[str, Any]]) -> list[tuple[str, float | None]]:
    """Frames in the order shown, each with the seconds until the next frame (``None`` for the last one).

    A validation point is passed through in no time, so it is listed with ``None`` seconds.
    """
    stops = [event for event in events if event.get("event") in ("frame", DECISION_EVENT, FINISHED_EVENT)]
    visits: list[tuple[str, float | None]] = []
    for current, following in zip(stops, [*stops[1:], None]):
        if current["event"] == FINISHED_EVENT:
            continue
        instant: bool = current["event"] == DECISION_EVENT or following is None
        seconds = None if instant else (_time(following["timestamp"]) - _time(current["timestamp"])).total_seconds()
        visits.append((str(current.get("frame", "")), seconds))
    return visits


def final_variables(events: list[dict[str, Any]]) -> dict[str, Any]:
    """The last value each global variable had in this visit, from the variable events."""
    return {str(event["variable"]): event.get("to") for event in events if event.get("event") == VARIABLE_EVENT}


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
        elif kind == DECISION_EVENT:
            next(durations)
            label = element_labels.get(event.get("element_id"), "no rule matched")
            target: str = frame_names.get(str(event.get("target", "")), str(event.get("target", "")))
            lines.append(f"{frame}: {label} → {target}")
        elif kind == VARIABLE_EVENT:
            lines.append(f"{event.get('variable')}: {event.get('from')} → {event.get('to')}")
        elif kind == "choice" and event.get("component") == "close":
            lines.append(f"{frame}: closed, back to the previous frame")
        elif kind == "choice":
            label = element_labels.get(event.get("element_id"), str(event.get("component", "element")))
            lines.append(f"{frame}: clicked '{label}'")
        elif kind == ERROR_EVENT:
            lines.append(f"JavaScript error: {event.get('message')} ({event.get('file') or '?'}, line {event.get('line') or '?'})")
        elif kind == VISIT_EVENT:
            made_with: str = f" (story made with TilTale {event['tiltale_version']})" if event.get("tiltale_version") else ""
            lines.append(f"Visit started at {event.get('local_time', '?')} on {describe_visit(event) or 'an unknown device'}{made_with}")
        else:
            lines.append(kind)
    return lines


def session_record(summary: SessionSummary, frame_names: dict[str, str], element_labels: dict[int, str]) -> dict[str, Any]:
    """Everything the Results page shows for one visit: the list entry, its timeline and the path for the flowchart."""
    return {
        "file_name": summary.file_name, "participant_id": summary.participant_id, "kind": summary.kind,
        "language": summary.language, "event_count": summary.event_count, "finished": summary.finished,
        "started": summary.started, "device": summary.device, "local_time": summary.local_time,
        "started_label": _time(summary.started).strftime("%d %b %Y, %H:%M UTC") if summary.started else "",
        "frames": frame_visits(summary.events),
        "choices": [
            event["element_id"] for event in summary.events
            if event.get("event") in ("choice", DECISION_EVENT) and event.get("element_id") is not None
        ],
        "variables": final_variables(summary.events),
        "lines": readable_events(summary.events, frame_names, element_labels),
    }


def import_jsonl(file_name: str, data: bytes, key: RSAPrivateKey | None = None) -> Path:
    """Store one downloaded server log in /project/logs/ without overwriting anything.

    An encrypted file is checked with ``key`` and stored as it is, still encrypted.
    """
    try:
        text: str = data.decode("utf-8-sig")
        events = parse_events(text, file_name, key)
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
    lines: list[str] = [line for line in text.splitlines() if line.strip()]
    destination.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return destination

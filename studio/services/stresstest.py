"""The Stress test page: does the story work everywhere? (README, Play-test and Stress test)

A checklist of rows, each red, orange or green. The rows here need no browser and are computed when
the page opens: the story player's compatibility with old phones, Regenerate's warnings, and what the
logs say about real phones. The other rows (the play-test robot under pretended bad conditions) are run
by ``setupStresstest`` in app.js, which also sorts every row so that red comes first.
"""

from dataclasses import dataclass
import re
from typing import Any

from django.conf import settings

from .study_logs import SessionSummary, device_report

RED, ORANGE, GREEN = "red", "orange", "green"
ORDER: dict[str, int] = {RED: 0, ORANGE: 1, GREEN: 2}

RUNTIME_FILES: tuple[str, ...] = ("tiltale.js", "bubbles.js")
OLDEST_BROWSERS: str = "iOS 13, Chrome 61 or newer"
REAL_DEVICES_WANTED: int = 3  # finished visits on this many different phones before a study


@dataclass(frozen=True, slots=True)
class Check:
    key: str
    title: str
    status: str  # RED, ORANGE or GREEN
    message: str
    advice: str = ""  # shown when the row is not green


@dataclass(frozen=True, slots=True)
class RobotCheck:
    """A row that app.js fills in by running the play-test robot with ``?stress=``."""
    key: str
    title: str
    stress: str  # the ?stress= value tiltale.js understands ("" for none)
    expect: str  # "pass", or "fail" for the deliberate crash
    advice: str


ROBOT_CHECKS: tuple[RobotCheck, ...] = (
    RobotCheck("normal", "Plays to the end", "", "pass",
               "Open Play-test: it shows which button or frame the robot got stuck on."),
    RobotCheck("slow", "Survives a slow connection", "slow", "pass",
               "The story or its log upload does not cope with a slow line. Compare with a normal run under Play-test."),
    RobotCheck("lost", "Survives a lost connection", "lost-connection", "pass",
               "Log events written while offline must arrive after the connection returns. If not, the queue in tiltale.js is broken."),
    RobotCheck("no-cache", "Works without cache storage", "no-cache", "pass",
               "The story must play from memory alone."),
    RobotCheck("no-storage", "Works without local storage", "no-storage", "pass",
               "The story must play without remembering anything on the device."),
    RobotCheck("everything", "Survives all of these at once", "slow,lost-connection,no-cache,no-storage", "pass",
               "Look at the single conditions above first."),
    RobotCheck("crash", "A crash is caught and logged", "crash", "fail",
               "A deliberate JavaScript error must make the robot fail with 'JavaScript error' and put an error line in the log. If this row is red, real crashes on participants' phones would go unnoticed."),
)

# Tokens that ES5 does not have. Strings and comments are removed first, so a word inside a text or a
# remark does not count. Not caught: shorthand methods and default parameters, which are rare in this code.
_MODERN = re.compile(r"=>|`|\.\.\.|\b(?:const|let|class|async|await|import|export|yield|static)\b")
_STRINGS_AND_COMMENTS = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|/\*[\s\S]*?\*/|//[^\n]*')


def es5_problems(text: str, name: str) -> list[str]:
    """Lines of ``text`` that use JavaScript newer than ES5, e.g. ``tiltale.js line 12: '=>'``."""
    stripped: str = _STRINGS_AND_COMMENTS.sub(lambda match: "\n" * match.group(0).count("\n"), text)
    return [
        f"{name} line {number}: '{found.group(0)}'"
        for number, line in enumerate(stripped.splitlines(), start=1)
        for found in _MODERN.finditer(line)
    ]


def runtime_check() -> Check:
    problems: list[str] = [
        problem for name in RUNTIME_FILES
        for problem in es5_problems((settings.RUNTIME_DIR / name).read_text(encoding="utf-8"), name)
    ]
    if problems:
        return Check("runtime", "Runs on old phones", RED, "; ".join(problems[:5]),
                     "runtime/ must stay ES5 JavaScript (no const, let, =>, `, ...). Rewrite these lines; python manage.py test reports them too.")
    return Check("runtime", "Runs on old phones", GREEN, f"The story player is plain ES5 JavaScript: {OLDEST_BROWSERS}.")


def build_check(report: dict[str, Any] | None) -> Check:
    """Regenerate's own findings: unreadable text on a small phone, buttons that lead nowhere, and so on."""
    if report is None:
        return Check("build", "Regenerate found no problems", RED, "Nothing has been generated yet.", "Press Regenerate on the Develop page first.")
    issues: list[dict[str, Any]] = list(report.get("issues", []))
    errors: list[str] = [str(issue.get("message", "")) for issue in issues if issue.get("severity") == "error"]
    warnings: list[str] = [str(issue.get("message", "")) for issue in issues if issue.get("severity") != "error"]
    if errors:
        return Check("build", "Regenerate found no problems", RED, f"{len(errors)} error(s), e.g. {errors[0]}",
                     "The Develop page lists them all. Fix them and Regenerate.")
    if warnings:
        return Check("build", "Regenerate found no problems", ORANGE, f"{len(warnings)} warning(s), e.g. {warnings[0]}",
                     "The Develop page lists them all. Text too small for a phone is the usual one.")
    return Check("build", "Regenerate found no problems", GREEN, "No errors or warnings in the last Regenerate.")


def device_checks(summaries: list[SessionSummary]) -> list[Check]:
    """What the logs of real visits (not previews or play-tests in this studio) say about real phones."""
    real: list[SessionSummary] = [summary for summary in summaries if summary.kind == "study"]
    rows: list[dict[str, Any]] = [row for row in device_report(real) if row["device"] != "Unknown device"]
    finished: list[str] = [row["device"] for row in rows if row["finished"]]
    troubled: list[str] = [row["device"] for row in rows if row["errors"] or row["unsupported"]]
    title: str = f"Finished on {REAL_DEVICES_WANTED} or more real phones"
    advice: str = "Open the story on a real phone with ?autoplay added to the address; it appears here once its visit is under Results."
    if not finished:
        phones = Check("phones", title, RED, f"No finished visit from a real phone yet ({len(real)} real visit(s) so far).", advice)
    elif len(finished) < REAL_DEVICES_WANTED:
        phones = Check("phones", title, ORANGE, f"{len(finished)} so far: " + ", ".join(finished), advice)
    else:
        phones = Check("phones", title, GREEN, f"{len(finished)} devices: " + ", ".join(finished))
    errors_title: str = "No errors on any real device"
    if troubled:
        errors = Check("device-errors", errors_title, RED, "Errors or a browser too old on: " + ", ".join(troubled),
                       "Open Results: the visit's timeline names the error and its line in tiltale.js.")
    else:
        errors = Check("device-errors", errors_title, GREEN, f"No JavaScript error in {len(real)} real visit(s)." if real else "No real visits yet.")
    return [phones, errors]


def checklist(report: dict[str, Any] | None, summaries: list[SessionSummary]) -> list[Check]:
    """Every row that needs no browser, red first."""
    checks: list[Check] = [runtime_check(), build_check(report), *device_checks(summaries)]
    return sorted(checks, key=lambda check: ORDER[check.status])

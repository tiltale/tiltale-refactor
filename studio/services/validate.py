"""Preflight checks shown on the dashboard. They warn; they never block Regenerate.

Each issue names a frame when possible so the dashboard can link to it.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from django.conf import settings

from studio.models import Element, Frame, ProjectSettings

from .components import ComponentDefinition, component_map
from .content import ContentRow, ContentTable
from .flow import distances, frame_edges

Severity = Literal["warning", "error"]
MIN_TEXT_PX: float = 12.0


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: Severity
    message: str
    frame_id: int | None = None
    frame_name: str = ""


def _issue(severity: Severity, message: str, frame: Frame | None = None) -> ValidationIssue:
    return ValidationIssue(severity, message, frame.id if frame else None, frame.name if frame else "")


@dataclass(frozen=True, slots=True)
class DevicePreset:
    label: str
    width: int
    height: int


# The first entry is the smallest device the runtime supports (iOS 12 / 2013+).
DEVICE_PRESETS: tuple[DevicePreset, ...] = (
    DevicePreset("iPhone 5s / SE 1st gen", 320, 568),
    DevicePreset("Galaxy S5", 360, 640),
    DevicePreset("iPhone 8", 375, 667),
    DevicePreset("iPhone 15", 393, 852),
    DevicePreset("Pixel 8", 412, 915),
    DevicePreset("iPad 10.2″", 810, 1080),
    DevicePreset("Laptop", 1366, 768),
    DevicePreset("Desktop full HD", 1920, 1080),
)


def smallest_scale(project: ProjectSettings) -> float:
    """Frame scale on the smallest device, held in its best-fitting orientation."""
    device = DEVICE_PRESETS[0]
    return max(
        min(device.width / project.frame_width, device.height / project.frame_height),
        min(device.height / project.frame_width, device.width / project.frame_height),
    )


@dataclass(frozen=True, slots=True)
class _Checks:
    """What every element check needs, computed once per validation."""

    project: ProjectSettings
    languages: tuple[str, ...]
    rows: dict[int, ContentRow]
    components: dict[str, ComponentDefinition]
    scale: float


def validate_project(project: ProjectSettings, content: ContentTable) -> list[ValidationIssue]:
    """Everything worth checking before publishing, most general first."""
    frames: list[Frame] = list(Frame.objects.prefetch_related("elements__language_overrides"))
    story: list[Frame] = [frame for frame in frames if not frame.is_language_picker]
    pickers: list[Frame] = [frame for frame in frames if frame.is_language_picker]
    issues: list[ValidationIssue] = list(_project_issues(project, content, pickers))
    if not story:
        return [*issues, _issue("warning", "The story has no frames yet.")]
    checks = _Checks(project, content.languages, content.by_id(), component_map(), smallest_scale(project))
    for frame in frames:
        issues += _background_issues(frame)
        for element in frame.elements.all():
            issues += _element_issues(element, frame, checks)
    edges: dict[str, list[str]] = frame_edges(frames)
    issues += _reach_issues(story, edges)
    if len(content.languages) > 1:
        issues += _reach_issues(pickers, edges)
        issues += _picker_language_issues(pickers, content)
    issues += _redirect_issues(project, any(element.ends_story for frame in story for element in frame.elements.all()))
    return issues


def _project_issues(project: ProjectSettings, content: ContentTable, pickers: list[Frame]) -> Iterator[ValidationIssue]:
    if project.base_language not in content.languages:
        yield _issue("error", f"Base language '{project.base_language}' is missing from content.xlsx.")
    if pickers and len(content.languages) < 2:
        yield _issue("warning", "Language-picker frames are ignored: content.xlsx has only one language.", pickers[0])


def _background_issues(frame: Frame) -> Iterator[ValidationIssue]:
    if frame.background_type == Frame.BackgroundType.NONE:
        yield _issue("warning", "Frame has no background yet.", frame)
        return
    if frame.background_type != Frame.BackgroundType.IMAGE:
        return
    if not (settings.PROJECT_DIR / "materials" / frame.background_image).is_file():
        yield _issue("error", f"Background image '{frame.background_image}' cannot be found.", frame)


def _element_issues(element: Element, frame: Frame, checks: _Checks) -> Iterator[ValidationIssue]:
    component: ComponentDefinition | None = checks.components.get(element.component)
    if component is None:
        yield _issue("error", f"Element #{element.id} uses unknown component '{element.component}'.", frame)
        return
    label: str = f"{component.name} #{element.id}"
    if component.clickable and not (element.target_frame_id or element.target_language or element.ends_story):
        yield _issue("warning", f"{label} is clickable but leads nowhere.", frame)
    if not (0 <= element.x <= checks.project.frame_width and 0 <= element.y <= checks.project.frame_height):
        yield _issue("warning", f"{label} has its center outside the frame.", frame)
    if not component.accepts_content:
        return
    for severity, problem in _text_problems(element, frame, checks):
        yield _issue(severity, f"{label} {problem}", frame)
    smallest_font: float = min(element.geometry(language)["font_size"] for language in checks.languages)
    if smallest_font * checks.scale < MIN_TEXT_PX:
        yield _issue("warning", (
            f"{label}: text is about {smallest_font * checks.scale:.1f}px on a {DEVICE_PRESETS[0].label} "
            f"(minimum {MIN_TEXT_PX:g}px). Increase the font size."
        ), frame)


def _text_problems(element: Element, frame: Frame, checks: _Checks) -> Iterator[tuple[Severity, str]]:
    if frame.is_language_picker:
        if not element.text.strip():
            yield "warning", "has no text."
        return
    if element.content_id is None:
        yield "warning", "has no content selected."
        return
    row: ContentRow | None = checks.rows.get(element.content_id)
    if row is None:
        yield "error", f"uses content_id {element.content_id}, which is not in content.xlsx."
        return
    missing: list[str] = [language for language in checks.languages if not row.values.get(language)]
    if missing:
        yield "warning", f"(content_id {element.content_id}) has no text in {', '.join(missing)}."


def _reach_issues(group: list[Frame], edges: dict[str, list[str]]) -> Iterator[ValidationIssue]:
    if not group:
        return
    steps: dict[str, int] = distances(group[0].name, edges)
    for frame in group:
        if frame.name not in steps:
            yield _issue("warning", f"{frame.name} cannot be reached from {group[0].name}.", frame)


def _picker_language_issues(pickers: list[Frame], content: ContentTable) -> Iterator[ValidationIssue]:
    if not pickers:
        return
    targeted: set[str] = {element.target_language for frame in pickers for element in frame.elements.all()}
    for language in content.languages:
        if language not in targeted:
            yield _issue("error", f"No language-picker button leads to {language}.", pickers[0])


def _redirect_issues(project: ProjectSettings, story_can_end: bool) -> Iterator[ValidationIssue]:
    redirect: str = project.finish_redirect_url
    if redirect and not story_can_end:
        yield _issue("warning", "A finish redirect URL is set, but no element is set to “End story”.")
    if redirect and "{ID}" not in redirect:
        yield _issue("warning", "The finish redirect URL has no {ID}, so the participant ID is not passed back.")

"""Fast pre-generation checks that warn without blocking the preview.

These are deliberately practical checks, not an abstract linting framework.
Each warning points back to a frame whenever possible so a developer can fix it
from the dashboard.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from django.conf import settings

from studio.models import Element, Frame, ProjectSettings

from .components import component_map
from .content import ContentTable

Severity = Literal["warning", "error"]


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: Severity
    message: str
    frame_name: str | None = None
    element_id: int | None = None


@dataclass(frozen=True, slots=True)
class DevicePreset:
    key: str
    label: str
    width: int
    height: int


DEVICE_PRESETS: tuple[DevicePreset, ...] = (
    DevicePreset("iphone-4", "iPhone 4 / older", 320, 480),
    DevicePreset("galaxy-s5", "Galaxy S5 / older", 360, 640),
    DevicePreset("iphone-6", "iPhone 6", 375, 667),
    DevicePreset("iphone-15", "iPhone 15", 393, 852),
    DevicePreset("pixel-8", "Pixel 8", 412, 915),
    DevicePreset("desktop-hd", "Desktop 1920×1080", 1920, 1080),
)


def _effective_font_size(element: Element, language: str) -> float:
    override = next(
        (item for item in element.language_overrides.all() if item.language == language),
        None,
    )
    if override and override.font_size is not None:
        return float(override.font_size)
    return float(element.font_size)


def validate_project(project: ProjectSettings, content: ContentTable) -> list[ValidationIssue]:
    """Return actionable errors/warnings for the current project state."""
    issues: list[ValidationIssue] = []
    components = component_map()
    content_by_id = content.by_id()
    frames: list[Frame] = list(
        Frame.objects.prefetch_related("elements__language_overrides", "elements__target_frame").all()
    )

    if project.base_language not in content.languages:
        issues.append(
            ValidationIssue(
                "error",
                f"Base language '{project.base_language}' is missing from content.xlsx.",
            )
        )
    if not frames:
        issues.append(ValidationIssue("warning", "The story has no frames yet."))
        return issues

    frame_names: set[str] = {frame.name for frame in frames}
    reachable: set[str] = set()
    pending: list[str] = [frames[0].name]
    edges: dict[str, set[str]] = {frame.name: set() for frame in frames}

    for frame in frames:
        if frame.background_type == Frame.BackgroundType.NONE:
            issues.append(
                ValidationIssue("warning", "Frame has no background yet.", frame.name)
            )
        elif frame.background_type == Frame.BackgroundType.IMAGE:
            image_path: Path = settings.PROJECT_DIR / "materials" / frame.background_image
            if not frame.background_image or not image_path.is_file():
                issues.append(
                    ValidationIssue("error", "Background image cannot be found.", frame.name)
                )

        for element in frame.elements.all():
            component = components.get(element.component)
            if component is None:
                issues.append(
                    ValidationIssue(
                        "error",
                        f"Unknown component '{element.component}'.",
                        frame.name,
                        element.id,
                    )
                )
                continue

            if component.accepts_content:
                if element.content_id is None:
                    issues.append(
                        ValidationIssue(
                            "warning",
                            f"{component.name} has no content selected.",
                            frame.name,
                            element.id,
                        )
                    )
                elif element.content_id not in content_by_id:
                    issues.append(
                        ValidationIssue(
                            "error",
                            f"content_id {element.content_id} does not exist in content.xlsx.",
                            frame.name,
                            element.id,
                        )
                    )
                else:
                    row = content_by_id[element.content_id]
                    for language in content.languages:
                        if not row.values.get(language, "").strip():
                            issues.append(
                                ValidationIssue(
                                    "warning",
                                    f"content_id {element.content_id} has no {language} text.",
                                    frame.name,
                                    element.id,
                                )
                            )

            if component.clickable:
                if element.target_frame_id is None:
                    issues.append(
                        ValidationIssue(
                            "warning",
                            f"{component.name} has no target frame.",
                            frame.name,
                            element.id,
                        )
                    )
                elif element.target_frame and element.target_frame.name in frame_names:
                    edges[frame.name].add(element.target_frame.name)

            if not (0 <= element.x <= project.frame_width and 0 <= element.y <= project.frame_height):
                issues.append(
                    ValidationIssue(
                        "warning",
                        "Element center is outside the base frame.",
                        frame.name,
                        element.id,
                    )
                )

            # Portrait phones display a landscape story with letterboxing. This
            # check exposes text that becomes physically too small on old phones.
            smallest = DEVICE_PRESETS[0]
            scale: float = min(
                smallest.width / project.frame_width,
                smallest.height / project.frame_height,
            )
            for language in content.languages:
                rendered_px: float = _effective_font_size(element, language) * scale
                if rendered_px < 14 and component.accepts_content:
                    issues.append(
                        ValidationIssue(
                            "warning",
                            f"Text is about {rendered_px:.1f}px on {smallest.label} in {language}; consider a larger font or language override.",
                            frame.name,
                            element.id,
                        )
                    )
                    break

    while pending:
        current: str = pending.pop()
        if current in reachable:
            continue
        reachable.add(current)
        pending.extend(edges.get(current, set()) - reachable)

    for frame in frames:
        if frame.name not in reachable:
            issues.append(
                ValidationIssue(
                    "warning",
                    f"{frame.name} is not reachable from the first frame.",
                    frame.name,
                )
            )

    return issues

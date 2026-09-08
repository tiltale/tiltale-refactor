"""Compile project data into framework-free language-specific story websites."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any

from django.conf import settings
from PIL import Image, ImageOps

from studio.models import Element, Frame, ProjectSettings

from .components import ComponentDefinition, component_css, component_map
from .content import ContentTable, load_content_table
from .project import newest_source_timestamp, safe_child
from .validate import ValidationIssue, validate_project


@dataclass(frozen=True, slots=True)
class LanguageBuild:
    language: str
    directory: str
    bytes_on_disk: int


@dataclass(frozen=True, slots=True)
class BuildReport:
    project: str
    generated_at: str
    generated_timestamp: float
    source_timestamp: float
    languages: tuple[LanguageBuild, ...]
    issues: tuple[ValidationIssue, ...]


def _safe_language_segment(language: str) -> str:
    """Keep normal language codes readable while making arbitrary headers safe."""
    segment: str = re.sub(r"[^A-Za-z0-9._-]+", "-", language.strip()).strip("-.")
    return segment or "language"


def language_directory(project_slug: str, language: str) -> str:
    return f"{project_slug}---{_safe_language_segment(language)}"


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _background_variants(source: Path, asset_dir: Path, relative_source: str) -> list[dict[str, Any]]:
    """Create small WebP variants without upscaling the author's material."""
    digest: str = hashlib.sha1(relative_source.encode("utf-8")).hexdigest()[:8]
    safe_stem: str = re.sub(r"[^A-Za-z0-9_-]+", "-", source.stem).strip("-") or "image"
    with Image.open(source) as opened:
        image: Image.Image = ImageOps.exif_transpose(opened)
        if getattr(image, "is_animated", False):
            image.seek(0)
        has_alpha: bool = "A" in image.getbands()
        base: Image.Image = image.convert("RGBA" if has_alpha else "RGB")
        original_width: int = base.width
        target_widths: list[int] = sorted(
            {min(width, original_width) for width in (480, 960, 1920)} | {original_width}
        )
        variants: list[dict[str, Any]] = []
        for width in target_widths:
            resized: Image.Image = base.copy()
            if width < original_width:
                height: int = max(1, round(base.height * width / original_width))
                resized = base.resize((width, height), Image.Resampling.LANCZOS)
            filename: str = f"{safe_stem}-{digest}-{width}w.webp"
            destination: Path = asset_dir / filename
            resized.save(destination, "WEBP", quality=82, method=6)
            variants.append(
                {
                    "width": width,
                    "path": f"assets/{filename}",
                    "bytes": destination.stat().st_size,
                }
            )
        return variants


def _effective_element_values(element: Element, language: str) -> dict[str, float]:
    override = next(
        (item for item in element.language_overrides.all() if item.language == language),
        None,
    )
    values: dict[str, float] = {
        "x": float(element.x),
        "y": float(element.y),
        "width": float(element.width),
        "height": float(element.height),
        "font_size": float(element.font_size),
    }
    if override:
        for key in values:
            override_value: float | None = getattr(override, key)
            if override_value is not None:
                values[key] = float(override_value)
    return values


def _story_payload(
    project: ProjectSettings,
    language: str,
    content: ContentTable,
    backgrounds: dict[str, list[dict[str, Any]]],
    components: dict[str, ComponentDefinition],
) -> dict[str, Any]:
    content_by_id = content.by_id()
    frames: list[Frame] = list(
        Frame.objects.prefetch_related("elements__language_overrides", "elements__target_frame").all()
    )
    payload_frames: list[dict[str, Any]] = []

    for frame in frames:
        if frame.background_type == Frame.BackgroundType.IMAGE:
            background: dict[str, Any] = {
                "type": "image",
                "sources": backgrounds.get(frame.background_image, []),
            }
        elif frame.background_type == Frame.BackgroundType.SOLID:
            background = {"type": "solid", "color": frame.background_color}
        else:
            background = {"type": "none"}

        elements: list[dict[str, Any]] = []
        for element in frame.elements.all():
            component = components.get(element.component)
            if component is None:
                continue
            row = content_by_id.get(element.content_id) if element.content_id is not None else None
            text: str = row.values.get(language, "") if row else ""
            geometry: dict[str, float] = _effective_element_values(element, language)
            elements.append(
                {
                    "id": element.id,
                    "component": component.slug,
                    "content_id": element.content_id,
                    "svg": component.svg,
                    "text": text,
                    "accepts_content": component.accepts_content,
                    "clickable": component.clickable,
                    "target": element.target_frame.name if element.target_frame else None,
                    **geometry,
                    "fill": element.fill_color,
                    "border": element.border_color,
                    "text_color": element.text_color,
                    "break_long_words": element.break_long_words,
                    "delay_mode": element.delay_mode,
                }
            )

        payload_frames.append(
            {
                "name": frame.name,
                "fade_in": frame.fade_in,
                "background": background,
                "elements": elements,
            }
        )

    return {
        "project": project.slug,
        "project_name": project.name,
        "language": language,
        "frame_width": project.frame_width,
        "frame_height": project.frame_height,
        "letterbox_color": project.letterbox_color,
        "default_delay_seconds": float(project.default_delay_seconds),
        "log_endpoint": project.log_endpoint,
        "start_frame": frames[0].name if frames else None,
        "base_bytes": 0,
        "frames": payload_frames,
    }


def _write_language_build(
    root: Path,
    project: ProjectSettings,
    language: str,
    content: ContentTable,
    components: dict[str, ComponentDefinition],
    background_sources: set[str],
) -> LanguageBuild:
    directory_name: str = language_directory(project.slug, language)
    output: Path = root / directory_name
    asset_dir: Path = output / "assets"
    asset_dir.mkdir(parents=True)

    backgrounds: dict[str, list[dict[str, Any]]] = {}
    material_root: Path = settings.PROJECT_DIR / "materials"
    for relative_source in sorted(background_sources):
        source: Path = safe_child(material_root, relative_source)
        if source.is_file():
            backgrounds[relative_source] = _background_variants(
                source,
                asset_dir,
                relative_source,
            )

    story: dict[str, Any] = _story_payload(project, language, content, backgrounds, components)
    runtime_html: str = (settings.RUNTIME_DIR / "index.html").read_text(encoding="utf-8")
    runtime_css: str = (settings.RUNTIME_DIR / "style.css").read_text(encoding="utf-8")
    runtime_js: str = (settings.RUNTIME_DIR / "script.js").read_text(encoding="utf-8")
    colors_css: str = (settings.PROJECT_DIR / "default-colors.css").read_text(encoding="utf-8")
    overrides_css: str = (settings.PROJECT_DIR / "style-overrides.css").read_text(encoding="utf-8")

    style_text: str = (
        "/* Generated by TilTale. Edit source/project files and regenerate; do not hand-edit /dist/. */\n\n"
        + "\n\n".join([runtime_css, component_css(), colors_css, overrides_css])
        + "\n"
    )
    (output / "index.html").write_text(
        runtime_html.replace("__TILTALE_LANGUAGE__", escape(language, quote=True)).replace(
            "__TILTALE_TITLE__", escape(project.name)
        ),
        encoding="utf-8",
    )
    (output / "style.css").write_text(style_text, encoding="utf-8")

    # ``base_bytes`` lets the runtime log a useful startup size: static HTML/CSS/JS
    # plus the responsive background variants chosen for the current device.
    script_path: Path = output / "script.js"
    for _ in range(3):
        story_json: str = json.dumps(story, ensure_ascii=False, separators=(",", ":"))
        script_text: str = (
            "/* Generated by TilTale. Edit source/project files and regenerate; do not hand-edit /dist/. */\n"
            f"const STORY = {story_json};\n\n{runtime_js}\n"
        )
        script_path.write_text(script_text, encoding="utf-8")
        base_bytes: int = (
            (output / "index.html").stat().st_size
            + (output / "style.css").stat().st_size
            + script_path.stat().st_size
        )
        if story["base_bytes"] == base_bytes:
            break
        story["base_bytes"] = base_bytes

    return LanguageBuild(
        language=language,
        directory=directory_name,
        bytes_on_disk=_directory_size(output),
    )


def generate_dist(project: ProjectSettings) -> BuildReport:
    """Validate and completely regenerate ``/dist`` for every workbook language."""
    content_path: Path = settings.PROJECT_DIR / "content.xlsx"
    content: ContentTable = load_content_table(content_path, assign_missing_ids=True)
    issues: list[ValidationIssue] = validate_project(project, content)
    components = component_map()

    language_segments: list[str] = [_safe_language_segment(language) for language in content.languages]
    if len(set(language_segments)) != len(language_segments):
        raise ValueError("Two language columns would generate the same safe folder name.")

    background_sources: set[str] = set(
        Frame.objects.filter(background_type=Frame.BackgroundType.IMAGE)
        .exclude(background_image="")
        .values_list("background_image", flat=True)
    )

    if settings.DIST_DIR.exists():
        shutil.rmtree(settings.DIST_DIR)
    settings.DIST_DIR.mkdir()

    builds: list[LanguageBuild] = []
    for language in content.languages:
        builds.append(
            _write_language_build(
                settings.DIST_DIR,
                project,
                language,
                content,
                components,
                background_sources,
            )
        )

    generated: datetime = datetime.now(timezone.utc)
    report = BuildReport(
        project=project.slug,
        generated_at=generated.isoformat(),
        generated_timestamp=generated.timestamp(),
        source_timestamp=newest_source_timestamp(),
        languages=tuple(builds),
        issues=tuple(issues),
    )
    report_data: dict[str, Any] = {
        "project": report.project,
        "generated_at": report.generated_at,
        "generated_timestamp": report.generated_timestamp,
        "source_timestamp": report.source_timestamp,
        "languages": [asdict(item) for item in report.languages],
        "issues": [asdict(item) for item in report.issues],
    }
    (settings.DIST_DIR / ".build.json").write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def load_build_report() -> dict[str, Any] | None:
    path: Path = settings.DIST_DIR / ".build.json"
    if not path.is_file():
        return None
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def dist_is_stale() -> bool:
    report: dict[str, Any] | None = load_build_report()
    if report is None:
        return True
    try:
        built_source_timestamp: float = float(report["source_timestamp"])
    except (KeyError, TypeError, ValueError):
        return True
    return newest_source_timestamp() > built_source_timestamp + 0.001


def build_folder_for_language(project: ProjectSettings, language: str) -> Path:
    return settings.DIST_DIR / language_directory(project.slug, language)

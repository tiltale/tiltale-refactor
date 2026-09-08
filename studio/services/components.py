"""Read source-controlled reusable component definitions.

A component folder contains only a manifest, SVG, and CSS. The loader validates
that small contract once and returns a typed immutable object. No plugin
framework is needed until components genuinely need executable authoring hooks.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from django.conf import settings


@dataclass(frozen=True, slots=True)
class ComponentDefinition:
    slug: str
    name: str
    description: str
    accepts_content: bool
    clickable: bool
    default_width: float
    default_height: float
    default_font_size: float
    fill: str
    border: str
    text: str
    variants: tuple[str, ...]
    svg: str
    css: str


def _required_text(data: dict[str, Any], key: str, source: Path) -> str:
    value: object = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source}: '{key}' must be non-empty text.")
    return value.strip()


def _required_number(data: dict[str, Any], key: str, source: Path) -> float:
    value: object = data.get(key)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{source}: '{key}' must be a number.")
    return float(value)


def _required_bool(data: dict[str, Any], key: str, source: Path) -> bool:
    value: object = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{source}: '{key}' must be true or false.")
    return value


def load_component(folder: Path) -> ComponentDefinition:
    """Load one component folder or raise a readable configuration error."""
    manifest_path: Path = folder / "component.json"
    svg_path: Path = folder / "component.svg"
    css_path: Path = folder / "component.css"
    missing: list[str] = [
        path.name for path in (manifest_path, svg_path, css_path) if not path.is_file()
    ]
    if missing:
        raise ValueError(f"{folder}: missing {', '.join(missing)}.")

    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    colors: object = data.get("colors")
    if not isinstance(colors, dict):
        raise ValueError(f"{manifest_path}: 'colors' must be an object.")
    size: object = data.get("default_size")
    if not isinstance(size, dict):
        raise ValueError(f"{manifest_path}: 'default_size' must be an object.")

    variants_value: object = data.get("variants", ["default"])
    if not isinstance(variants_value, list) or not all(
        isinstance(item, str) and item for item in variants_value
    ):
        raise ValueError(f"{manifest_path}: 'variants' must be a list of names.")

    return ComponentDefinition(
        slug=_required_text(data, "slug", manifest_path),
        name=_required_text(data, "name", manifest_path),
        description=_required_text(data, "description", manifest_path),
        accepts_content=_required_bool(data, "accepts_content", manifest_path),
        clickable=_required_bool(data, "clickable", manifest_path),
        default_width=_required_number(size, "width", manifest_path),
        default_height=_required_number(size, "height", manifest_path),
        default_font_size=_required_number(data, "default_font_size", manifest_path),
        fill=_required_text(colors, "fill", manifest_path),  # type: ignore[arg-type]
        border=_required_text(colors, "border", manifest_path),  # type: ignore[arg-type]
        text=_required_text(colors, "text", manifest_path),  # type: ignore[arg-type]
        variants=tuple(variants_value),
        svg=svg_path.read_text(encoding="utf-8").strip(),
        css=css_path.read_text(encoding="utf-8").strip(),
    )


def load_components() -> list[ComponentDefinition]:
    """Return components sorted by their human-facing name."""
    root: Path = settings.COMPONENTS_DIR
    definitions: list[ComponentDefinition] = []
    if not root.is_dir():
        return definitions
    seen_slugs: set[str] = set()
    for folder in root.iterdir():
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        component: ComponentDefinition = load_component(folder)
        if component.slug in seen_slugs:
            raise ValueError(f"Duplicate component slug '{component.slug}'.")
        seen_slugs.add(component.slug)
        definitions.append(component)
    return sorted(definitions, key=lambda item: item.name.casefold())


def component_map() -> dict[str, ComponentDefinition]:
    return {component.slug: component for component in load_components()}


def component_css() -> str:
    """Combine source CSS without inventing a build dependency."""
    return "\n\n".join(component.css for component in load_components())


def default_color_css() -> str:
    """Create the editable project color table from current component defaults."""
    lines: list[str] = [
        "/*",
        " * TilTale project-wide component colors.",
        " * Change a HEX value here to update every element that has no per-element color override.",
        " */",
        ":root {",
    ]
    for component in load_components():
        lines.extend(
            [
                f"  --component-{component.slug}-fill: {component.fill};",
                f"  --component-{component.slug}-border: {component.border};",
                f"  --component-{component.slug}-text: {component.text};",
            ]
        )
    lines.append("}")
    return "\n".join(lines) + "\n"

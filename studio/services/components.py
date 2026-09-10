"""Read the reusable component definitions in ``/components/``.

A component folder holds ``component.json``, ``component.svg`` and
``component.css``. The folder name is the component's slug and must match the
``.component-<slug>`` CSS class used in its stylesheet.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from django.conf import settings

TAILS: tuple[str, ...] = ("", "speech", "thought", "scream")


@dataclass(frozen=True, slots=True)
class ComponentDefinition:
    slug: str
    name: str
    description: str
    accepts_content: bool
    clickable: bool
    auto_height: bool  # the element grows with its text; the stored height is the minimum
    tail: str  # "", or the kind of tail bubbles.js draws: speech, thought or scream
    default_width: float
    default_height: float
    default_font_size: float
    fill: str
    border: str
    text: str
    svg: str
    css: str


def _field(data: dict[str, Any], key: str, kind: type | tuple[type, ...], source: Path) -> Any:
    value: object = data.get(key)
    if isinstance(value, bool) and kind is not bool:
        value = None  # JSON true/false is not a number or text
    if not isinstance(value, kind) or value == "":
        raise ValueError(f"{source}: '{key}' is missing or has the wrong type.")
    return value


def load_component(folder: Path) -> ComponentDefinition:
    """Load one component folder or raise a readable configuration error."""
    paths: dict[str, Path] = {suffix: folder / f"component.{suffix}" for suffix in ("json", "svg", "css")}
    missing: list[str] = [path.name for path in paths.values() if not path.is_file()]
    if missing:
        raise ValueError(f"{folder}: missing {', '.join(missing)}.")

    manifest: Path = paths["json"]
    data: dict[str, Any] = json.loads(manifest.read_text(encoding="utf-8"))
    size: dict[str, Any] = _field(data, "default_size", dict, manifest)
    colors: dict[str, Any] = _field(data, "colors", dict, manifest)
    number = (int, float)
    tail: object = data.get("tail", "")
    if tail not in TAILS:
        raise ValueError(f"{manifest}: 'tail' must be one of {', '.join(repr(item) for item in TAILS)}.")
    return ComponentDefinition(
        slug=folder.name,
        name=_field(data, "name", str, manifest),
        description=_field(data, "description", str, manifest),
        accepts_content=_field(data, "accepts_content", bool, manifest),
        clickable=_field(data, "clickable", bool, manifest),
        auto_height=data.get("auto_height") is True,
        tail=str(tail),
        default_width=float(_field(size, "width", number, manifest)),
        default_height=float(_field(size, "height", number, manifest)),
        default_font_size=float(_field(data, "default_font_size", number, manifest)),
        fill=_field(colors, "fill", str, manifest),
        border=_field(colors, "border", str, manifest),
        text=_field(colors, "text", str, manifest),
        svg=paths["svg"].read_text(encoding="utf-8").strip(),
        css=paths["css"].read_text(encoding="utf-8").strip(),
    )


def load_components() -> list[ComponentDefinition]:
    """Return every component, sorted by its human-facing name."""
    root: Path = settings.COMPONENTS_DIR
    folders: list[Path] = [
        folder for folder in root.iterdir() if folder.is_dir() and not folder.name.startswith(".")
    ] if root.is_dir() else []
    return sorted((load_component(folder) for folder in folders), key=lambda item: item.name.casefold())


def component_map() -> dict[str, ComponentDefinition]:
    return {component.slug: component for component in load_components()}


def component_css() -> str:
    return "\n\n".join(component.css for component in load_components())


def default_color_css() -> str:
    """The editable project color table, pre-filled with component defaults."""
    lines: list[str] = [
        "/*",
        " * Project-wide component colors. Change a HEX value to recolor every element",
        " * of that component that has no per-element color override.",
        " */",
        ":root {",
    ]
    for component in load_components():
        for part, value in (("fill", component.fill), ("border", component.border), ("text", component.text)):
            lines.append(f"  --component-{component.slug}-{part}: {value};")
    lines.append("}")
    return "\n".join(lines) + "\n"

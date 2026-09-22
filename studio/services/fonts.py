"""Read and change the Fonts block of ``/project/style-overrides.css`` from the studio.

The block is one line per component (``.component-basic-narrator { font-family: …; }``, written
when the project is created; see ``default_font_css`` in components.py). The Content page lets an
author pick each component's font from a fixed set of stacks instead of editing CSS. A line that
matches no preset (an own font file, a hand-edited stack) is shown as "Custom" and left alone.

Every preset ends with ``sans-serif`` or ``serif``, never ``cursive``/``fantasy``/``monospace``:
Android maps those to faces that ruin a story (see the README, Fonts).
"""

from pathlib import Path
import re

from django.conf import settings

# name shown in the studio -> the font-family stack written to style-overrides.css
FONT_PRESETS: dict[str, str] = {
    "Clean": "Arial, Helvetica, sans-serif",
    "Rounded": "Verdana, Geneva, sans-serif",
    "Narrow": '"Arial Narrow", "Helvetica Neue", sans-serif',
    "Serif": 'Georgia, "Times New Roman", serif',
    "Typewriter": '"Courier New", Courier, serif',
    "Comic": '"Comic Sans MS", "Comic Sans", "Chalkboard SE", sans-serif',
    "Handwriting": '"Segoe Print", "Bradley Hand", "Chalkboard SE", sans-serif',
    "Heavy": 'Impact, "Arial Black", sans-serif',
}

_FONT_LINE = re.compile(r"^(?P<indent>\s*)\.component-(?P<slug>[A-Za-z0-9_-]+)\s*\{\s*font-family:\s*(?P<stack>[^;}]+?)\s*;\s*\}\s*$")


def _css_path() -> Path:
    return settings.PROJECT_DIR / "style-overrides.css"


def component_fonts() -> dict[str, str]:
    """The current stack per component slug, read from the Fonts block."""
    fonts: dict[str, str] = {}
    for line in _css_path().read_text(encoding="utf-8").splitlines():
        found = _FONT_LINE.match(line)
        if found:
            fonts[found.group("slug")] = found.group("stack")
    return fonts


def set_component_font(slug: str, preset: str) -> str:
    """Write one component's font line; returns the stack written.

    ``preset`` is a key of FONT_PRESETS: only known stacks are ever written into the CSS.
    A project made before the Fonts block existed gets the line appended.
    """
    if preset not in FONT_PRESETS:
        raise ValueError("Unknown font. Choose one of the offered fonts.")
    stack: str = FONT_PRESETS[preset]
    new_line: str = f".component-{slug} {{ font-family: {stack}; }}"
    path: Path = _css_path()
    lines: list[str] = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines):
        found = _FONT_LINE.match(line)
        if found and found.group("slug") == slug:
            lines[number] = new_line
            break
    else:
        lines.append(new_line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stack


def preset_of(stack: str) -> str:
    """The preset name behind ``stack``, or ``""`` for a custom stack the studio leaves alone."""
    squeezed = re.sub(r"\s+", " ", stack).strip()
    return next((name for name, preset in FONT_PRESETS.items() if preset == squeezed), "")

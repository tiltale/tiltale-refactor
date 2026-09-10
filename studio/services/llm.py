"""Prompt 2 from docs/llm-prompts/: fill it in for one frame, and read the model's answer back."""

import json
from string import Template
from typing import Any

from django.conf import settings

from studio.models import Frame, ProjectSettings

from .components import ComponentDefinition, component_map
from .content import ContentTable

PROMPT_FILE: str = "02-build-frame.md"
REQUIRED_KEYS: tuple[str, ...] = ("component", "x", "y")


def frame_prompt(project: ProjectSettings, frame: Frame, content: ContentTable) -> str:
    """The build-a-frame prompt with this project's components, texts and frames filled in."""
    template = Template((settings.PROMPTS_DIR / PROMPT_FILE).read_text(encoding="utf-8"))
    components: list[dict[str, Any]] = [{
        "component": component.slug, "description": component.description,
        "has_text": component.accepts_content, "clickable": component.clickable,
        "default_width": component.default_width, "default_height": component.default_height,
        "default_font_size": component.default_font_size,
    } for component in component_map().values()]
    texts: str = "\n".join(
        f"{row.content_id}\t{row.note}\t{row.values.get(project.base_language, '')}" for row in content.rows
    )
    targets: list[str] = [
        f"`{item.key}` ({item.name})" for item in Frame.objects.filter(is_language_picker=False).exclude(pk=frame.pk)
    ]
    return template.substitute(
        frame_id=frame.key,
        frame_name=frame.name,
        frame_width=f"{project.frame_width:g}",
        frame_height=f"{project.frame_height:g}",
        language=project.base_language,
        components=json.dumps(components, indent=2),
        texts=texts or "(content.xlsx has no rows yet)",
        targets=", ".join(targets) or "(no other frames yet)",
    )


def parse_elements(
    answer: str, components: dict[str, ComponentDefinition], content_ids: set[int], targets: dict[str, int],
) -> list[dict[str, Any]]:
    """Element field values from the model's JSON answer. Raises ValueError naming the bad element."""
    unfenced: str = answer.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        items: Any = json.loads(unfenced).get("elements")
    except (json.JSONDecodeError, AttributeError):
        raise ValueError('The answer must be JSON like {"elements": [...]}.') from None
    if not isinstance(items, list) or not items:
        raise ValueError('The answer has no "elements" list.')
    values: list[dict[str, Any]] = []
    for number, item in enumerate(items, start=1):
        try:
            values.append(_element_values(item, components, content_ids, targets))
        except (TypeError, ValueError) as error:
            raise ValueError(f"Element {number}: {error}") from None
    return values


def _element_values(
    item: Any, components: dict[str, ComponentDefinition], content_ids: set[int], targets: dict[str, int],
) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError("must be a JSON object.")
    missing: list[str] = [key for key in REQUIRED_KEYS if key not in item]
    if missing:
        raise ValueError(f"missing {', '.join(missing)}.")
    component: ComponentDefinition | None = components.get(item["component"])
    if component is None:
        raise ValueError(f"unknown component {item['component']!r}.")
    content_id: Any = item.get("content_id")
    if content_id is not None and content_id not in content_ids:
        raise ValueError(f"content_id {content_id!r} is not in content.xlsx.")
    target: Any = item.get("target")
    if target is not None and target != "end" and target not in targets:
        raise ValueError(f"unknown target {target!r}.")
    return {
        "component": component.slug,
        "content_id": content_id if component.accepts_content else None,
        "x": float(item["x"]),
        "y": float(item["y"]),
        "width": float(item.get("width", component.default_width)),
        "height": float(item.get("height", component.default_height)),
        "font_size": float(item.get("font_size", component.default_font_size)),
        "target_frame_id": targets.get(target) if component.clickable else None,
        "ends_story": component.clickable and target == "end",
    }

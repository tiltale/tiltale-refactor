"""Template filters that keep dictionary lookups out of views."""

from typing import Any

from django import template

register = template.Library()


@register.filter
def get_item(mapping: object, key: object) -> Any:
    """Return ``mapping[key]`` for dictionaries, or an empty string."""
    if isinstance(mapping, dict):
        return mapping.get(key, "")
    return ""

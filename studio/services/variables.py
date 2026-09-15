"""Global variables: how a typed value is read, and the type rules that keep the story from crashing.

A variable's type is decided by its initial value and never changes: ``0``, ``2.5`` and ``-3`` make a
*number*, anything else makes *text*. Write the value in quotes to force text (``"12"``). Every update
and every rule that uses a variable must fit that type, which ``check_value`` enforces when the author
saves and ``validate.py`` re-checks before publishing. The story player (tiltale.js) then trusts the
values it gets in story.js.
"""

import re

NAME_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
PLACEHOLDER: re.Pattern[str] = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")  # {score} in an element text

Value = int | float | str

COMPARATORS: dict[str, str] = {
    "==": "is", "!=": "is not", "<": "is less than", "<=": "is at most", ">": "is more than", ">=": "is at least",
}
NUMBER_ONLY: frozenset[str] = frozenset({"<", "<=", ">", ">="})
OPERATIONS: dict[str, str] = {"set": "set it to", "add": "add"}


def parse_value(raw: str) -> Value:
    """``"3"`` → 3, ``"2.5"`` → 2.5, ``"path 1"`` → ``"path 1"``, ``'"12"'`` → ``"12"`` (quotes force text)."""
    text: str = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    for number in (int, float):
        try:
            return number(text)
        except ValueError:
            continue
    return text


def kind_of(value: Value) -> str:
    return "text" if isinstance(value, str) else "number"


def check_name(name: str) -> str:
    cleaned: str = name.strip()
    if not NAME_PATTERN.fullmatch(cleaned):
        raise ValueError("A variable name starts with a letter and uses only letters, digits and '_' (e.g. score, path_a).")
    return cleaned


def check_value(variable_kind: str, raw: str, operation: str = "set") -> Value:
    """The typed value for an update or rule, or a ValueError explaining the type clash."""
    value: Value = parse_value(raw)
    if raw.strip() == "":
        raise ValueError("Type a value.")
    if operation == "add" and variable_kind != "number":
        raise ValueError("Only numbers can be added to; this variable is text.")
    if operation in NUMBER_ONLY and variable_kind != "number":
        raise ValueError(f"'{COMPARATORS[operation]}' only works with numbers; this variable is text.")
    if kind_of(value) != variable_kind:
        expected: str = "a number such as 1 or 2.5" if variable_kind == "number" else 'text (in quotes if it looks like a number: "12")'
        raise ValueError(f"The variable is {variable_kind}, so the value must be {expected}.")
    return value


def unknown_placeholders(text: str, variable_names: set[str]) -> list[str]:
    """``{names}`` written in a text that are not global variables (probably a typo)."""
    return [name for name in PLACEHOLDER.findall(text) if name not in variable_names]


def rule_label(variable_name: str | None, comparator: str, raw_value: str) -> str:
    """How a rule reads in the flowchart and the logs: ``score is at least 3`` or ``otherwise``."""
    if variable_name is None:
        return "otherwise"
    return f"{variable_name} {COMPARATORS.get(comparator, comparator)} {raw_value}"

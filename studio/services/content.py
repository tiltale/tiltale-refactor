"""Create and read the project's content workbook.

``content_id`` is a machine-managed integer. It is intentionally different from
Excel's physical row number: users may sort or insert rows without breaking the
story database. If a user adds a non-empty row without an ID, TilTale assigns
the next ID and writes it back to the workbook. Existing IDs never change.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet


@dataclass(frozen=True, slots=True)
class ContentRow:
    content_id: int
    excel_row: int
    values: dict[str, str]
    note: str


@dataclass(frozen=True, slots=True)
class ContentTable:
    languages: tuple[str, ...]
    rows: tuple[ContentRow, ...]

    def by_id(self) -> dict[int, ContentRow]:
        return {row.content_id: row for row in self.rows}


def create_content_workbook(path: Path, languages: list[str]) -> None:
    """Create the smallest useful content.xlsx template."""
    workbook: Workbook = Workbook()
    sheet: Worksheet = workbook.active
    sheet.title = "content"
    sheet.append(["content_id", "note", *languages])
    sheet.freeze_panes = "A2"
    sheet.column_dimensions["A"].width = 14
    sheet.column_dimensions["B"].width = 28
    for index in range(3, 3 + len(languages)):
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = 42
    workbook.save(path)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _content_id(value: Any, excel_row: int) -> int:
    """Parse a workbook ID without silently truncating values such as 3.5."""
    if isinstance(value, bool):
        raise ValueError(f"Excel row {excel_row}: content_id must be an integer.")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"Excel row {excel_row}: content_id must be an integer.")
        parsed: int = int(value)
    else:
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError) as error:
            raise ValueError(f"Excel row {excel_row}: content_id must be an integer.") from error
    if parsed <= 0:
        raise ValueError(f"Excel row {excel_row}: content_id must be greater than zero.")
    return parsed


def load_content_table(path: Path, assign_missing_ids: bool = True) -> ContentTable:
    """Read content and optionally assign stable IDs to newly typed rows."""
    if not path.is_file():
        raise FileNotFoundError(f"Content workbook not found: {path}")

    try:
        workbook = load_workbook(path)
    except PermissionError as error:
        raise ValueError(
            "content.xlsx cannot be read. Close it in Excel or another program, then reload TilTale."
        ) from error
    sheet: Worksheet = workbook.active
    headers: list[str] = [_text(cell.value) for cell in sheet[1]]
    while headers and not headers[-1]:
        headers.pop()
    if not headers or headers[0] != "content_id":
        raise ValueError("content.xlsx must start with a 'content_id' column.")
    if len(headers) < 2 or headers[1] != "note":
        raise ValueError("The second column in content.xlsx must be 'note'. Language columns go after it.")

    languages: tuple[str, ...] = tuple(headers[2:])
    if not languages:
        raise ValueError("content.xlsx needs at least one language column after 'note'.")
    if any(not language for language in languages):
        raise ValueError("Language columns in content.xlsx must be named; do not leave blank columns between languages.")
    if len({language.casefold() for language in languages}) != len(languages):
        raise ValueError("Language column names in content.xlsx must be unique.")

    # First establish the highest existing ID and reject duplicates. This avoids
    # an ID depending on where a blank-ID row happens to appear in the sheet.
    highest_id: int = 0
    seen_ids: set[int] = set()
    for excel_row in range(2, sheet.max_row + 1):
        raw_id: Any = sheet.cell(excel_row, 1).value
        if raw_id in (None, ""):
            continue
        content_id: int = _content_id(raw_id, excel_row)
        if content_id in seen_ids:
            raise ValueError(f"Duplicate content_id {content_id} in content.xlsx.")
        seen_ids.add(content_id)
        highest_id = max(highest_id, content_id)

    rows: list[ContentRow] = []
    workbook_changed: bool = False
    for excel_row in range(2, sheet.max_row + 1):
        language_values: dict[str, str] = {
            language: _text(sheet.cell(excel_row, 3 + index).value)
            for index, language in enumerate(languages)
        }
        note: str = _text(sheet.cell(excel_row, 2).value)
        raw_id = sheet.cell(excel_row, 1).value
        row_has_content: bool = bool(note or any(language_values.values()))
        if not row_has_content and raw_id in (None, ""):
            continue

        if raw_id in (None, ""):
            if not assign_missing_ids:
                raise ValueError(f"Excel row {excel_row} has content but no content_id.")
            highest_id += 1
            content_id = highest_id
            sheet.cell(excel_row, 1).value = content_id
            workbook_changed = True
        else:
            content_id = _content_id(raw_id, excel_row)

        rows.append(
            ContentRow(
                content_id=content_id,
                excel_row=excel_row,
                values=language_values,
                note=note,
            )
        )

    if workbook_changed:
        try:
            workbook.save(path)
        except PermissionError as error:
            raise ValueError(
                "content.xlsx could not be updated. Close it in Excel or another program, then reload TilTale."
            ) from error

    return ContentTable(languages=languages, rows=tuple(rows))

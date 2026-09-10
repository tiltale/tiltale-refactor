"""Create, read and append to the project's ``content.xlsx``.

Layout: column A ``content_id``, column B ``note``, then one column per language.
``content_id`` is a stable integer, deliberately not the Excel row number, so
authors can sort or insert rows freely. A typed row without an ID gets the
next free ID, which is written back to the workbook. Existing IDs never change.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet

LOCKED_MESSAGE: str = (
    "content.xlsx is locked. Close it in Excel (or any other program), then reload "
    "this browser page. Restarting TilTale is not needed."
)


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
    """Create the empty workbook for a new project."""
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
    return "" if value is None else str(value).strip()


def _content_id(value: Any, excel_row: int) -> int:
    """Parse an ID without silently truncating values such as 3.5."""
    error = ValueError(f"Excel row {excel_row}: content_id must be a whole number above zero.")
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise error
    try:
        parsed: int = int(str(value).strip()) if not isinstance(value, float) else int(value)
    except ValueError:
        raise error from None
    if parsed <= 0:
        raise error
    return parsed


def _languages(sheet: Worksheet) -> tuple[str, ...]:
    headers: list[str] = [_text(cell.value) for cell in sheet[1]]
    while headers and not headers[-1]:
        headers.pop()
    if headers[:2] != ["content_id", "note"]:
        raise ValueError("content.xlsx must start with the columns 'content_id' and 'note'. Language columns go after them.")
    languages: tuple[str, ...] = tuple(headers[2:])
    if not languages:
        raise ValueError("content.xlsx needs at least one language column after 'note'.")
    if not all(languages):
        raise ValueError("Language columns in content.xlsx must be named; do not leave empty columns between them.")
    if len({language.casefold() for language in languages}) != len(languages):
        raise ValueError("Language column names in content.xlsx must be unique.")
    return languages


def load_content_table(path: Path) -> ContentTable:
    """Read the workbook and assign IDs to newly typed rows."""
    if not path.is_file():
        raise FileNotFoundError(f"Content workbook not found: {path}")
    try:
        workbook = load_workbook(path)
    except PermissionError:
        raise ValueError(LOCKED_MESSAGE) from None
    sheet: Worksheet = workbook.active
    languages: tuple[str, ...] = _languages(sheet)

    # Find the highest existing ID first so a new ID never depends on where
    # an ID-less row happens to sit in the sheet.
    seen: set[int] = set()
    for excel_row in range(2, sheet.max_row + 1):
        raw = sheet.cell(excel_row, 1).value
        if raw in (None, ""):
            continue
        content_id: int = _content_id(raw, excel_row)
        if content_id in seen:
            raise ValueError(f"Duplicate content_id {content_id} in content.xlsx.")
        seen.add(content_id)
    next_id: int = max(seen, default=0) + 1

    rows: list[ContentRow] = []
    changed: bool = False
    for excel_row in range(2, sheet.max_row + 1):
        values: dict[str, str] = {
            language: _text(sheet.cell(excel_row, 3 + index).value) for index, language in enumerate(languages)
        }
        note: str = _text(sheet.cell(excel_row, 2).value)
        raw = sheet.cell(excel_row, 1).value
        if raw in (None, ""):
            if not note and not any(values.values()):
                continue
            sheet.cell(excel_row, 1).value = content_id = next_id
            next_id += 1
            changed = True
        else:
            content_id = _content_id(raw, excel_row)
        rows.append(ContentRow(content_id=content_id, excel_row=excel_row, values=values, note=note))

    if changed:
        try:
            workbook.save(path)
        except PermissionError:
            raise ValueError(LOCKED_MESSAGE) from None
    return ContentTable(languages=languages, rows=tuple(rows))


def append_content_row(path: Path, note: str, values: dict[str, str]) -> ContentRow:
    """Append one author-created row and return it with its new stable ID."""
    table: ContentTable = load_content_table(path)
    cleaned: dict[str, str] = {language: values.get(language, "").strip() for language in table.languages}
    note = note.strip()
    if not note and not any(cleaned.values()):
        raise ValueError("Add a note or text in at least one language.")
    next_id: int = max((row.content_id for row in table.rows), default=0) + 1
    try:
        workbook = load_workbook(path)
        sheet: Worksheet = workbook.active
        sheet.append([next_id, note, *cleaned.values()])
        workbook.save(path)
    except PermissionError:
        raise ValueError(LOCKED_MESSAGE) from None
    return ContentRow(content_id=next_id, excel_row=sheet.max_row, values=cleaned, note=note)

"""Small behavior tests for rules that could otherwise damage a project.

These tests intentionally avoid HTML formatting, line counts, private helpers,
and other brittle implementation details.
"""

from importlib.resources import path
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from openpyxl import load_workbook

from .forms import normalize_language, parse_extra_languages
from .services.content import create_content_workbook, load_content_table
from .services.project import safe_child
from .services.study_logs import import_jsonl


class LanguageTests(SimpleTestCase):
    def test_language_codes_are_normalized(self) -> None:
        self.assertEqual(normalize_language(" pt_br "), "pt-BR")

    def test_extra_languages_keep_order_without_duplicates(self) -> None:
        self.assertEqual(
            parse_extra_languages("nl-NL, DE-de, nl-nl", "en-US"),
            ["nl-NL", "de-DE"],
        )


class ContentWorkbookTests(SimpleTestCase):
    def test_created_workbook_puts_note_before_languages(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / "content.xlsx"
            create_content_workbook(path, ["en-US", "nl-NL"])
            workbook = load_workbook(path)
            headers = [cell.value for cell in workbook.active[1]]
            self.assertEqual(headers, ["content_id", "note", "en-US", "nl-NL"])

    def test_missing_id_is_assigned_once_and_survives_row_insertion(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / "content.xlsx"
            create_content_workbook(path, ["en-US", "nl-NL"])
            workbook = load_workbook(path)
            sheet = workbook.active
            sheet.append([None, "opening", "Hello", "Hallo"])
            workbook.save(path)

            first = load_content_table(path)
            self.assertEqual(first.rows[0].content_id, 1)

            workbook = load_workbook(path)
            workbook.active.insert_rows(2)
            workbook.save(path)
            second = load_content_table(path)
            self.assertEqual(second.rows[0].content_id, 1)
            self.assertEqual(second.rows[0].excel_row, 3)

    def test_fractional_content_id_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / "content.xlsx"
            create_content_workbook(path, ["en-US"])
            workbook = load_workbook(path)
            workbook.active.append([1.5, "bad ID", "Hello"])
            workbook.save(path)
            with self.assertRaisesRegex(ValueError, "must be an integer"):
                load_content_table(path)


    def test_locked_workbook_has_a_clear_error(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / "content.xlsx"
            path.touch()
            with patch("studio.services.content.load_workbook", side_effect=PermissionError):
                with self.assertRaisesRegex(ValueError, "Close it in Excel"):
                    load_content_table(path)

 
class FileBoundaryTests(SimpleTestCase):
    def test_safe_child_rejects_parent_traversal(self) -> None:
        with TemporaryDirectory() as directory:
            root: Path = Path(directory)
            with self.assertRaises(ValueError):
                safe_child(root, "../outside.txt")


class StudyLogTests(SimpleTestCase):
    def test_import_rejects_multiple_sessions_in_one_file(self) -> None:
        with TemporaryDirectory() as directory:
            project_dir: Path = Path(directory)
            (project_dir / "logs").mkdir()
            data: bytes = (
                b'{"session_id":"session-one","event":"frame"}\n'
                b'{"session_id":"session-two","event":"frame"}\n'
            )
            with override_settings(PROJECT_DIR=project_dir):
                with self.assertRaisesRegex(ValueError, "exactly one session_id"):
                    import_jsonl("mixed.jsonl", data)

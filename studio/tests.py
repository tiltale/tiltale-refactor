"""Small behavior tests for rules that could otherwise damage a project.

These tests intentionally avoid HTML formatting, line counts, private helpers,
and other brittle implementation details.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

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
    def test_missing_id_is_assigned_once_and_survives_row_insertion(self) -> None:
        with TemporaryDirectory() as directory:
            path: Path = Path(directory) / "content.xlsx"
            create_content_workbook(path, ["en-US", "nl-NL"])
            workbook = load_workbook(path)
            sheet = workbook.active
            sheet.append([None, "Hello", "Hallo", "opening"])
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
            workbook.active.append([1.5, "Hello", "bad ID"])
            workbook.save(path)
            with self.assertRaisesRegex(ValueError, "must be an integer"):
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

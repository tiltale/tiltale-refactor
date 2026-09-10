"""Behavior tests for the rules that protect a project, a study, or the generated website.

Run with ``python manage.py test``. Database tests use an in-memory copy of the
project database, so /project/ is never touched.
"""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from .forms import ProjectSettingsForm, normalize_language, parse_extra_languages
from .models import Element, Frame, ProjectSettings
from .services.components import default_color_css
from .services.content import append_content_row, create_content_workbook, load_content_table
from .services.flow import STEP_X, create_frame, tidy_layout
from .services.generate import generate_dist, language_folder, reset_dist_directory
from .services.project import safe_child
from .services.study_logs import import_jsonl, log_file_name, safe_name, session_kind
from .services.validate import validate_project

EVENT: dict[str, object] = {"participant_id": "R_abc", "visit_id": "20260910T101530Z-a1b2", "event": "frame", "seq": 1}


def make_project_folder(root: Path, languages: list[str]) -> ProjectSettings:
    """Files of a minimal project in ``root`` plus its settings row (test database)."""
    (root / "materials").mkdir(parents=True)
    (root / "logs").mkdir()
    (root / "project.sqlite3").touch()  # project_settings() checks that the file exists
    create_content_workbook(root / "content.xlsx", languages)
    (root / "default-colors.css").write_text(default_color_css(), encoding="utf-8")
    (root / "style-overrides.css").write_text("", encoding="utf-8")
    return ProjectSettings.objects.create(name="Demo", slug="demo", base_language=languages[0])


class LanguageTests(SimpleTestCase):
    def test_language_codes_are_normalized(self) -> None:
        self.assertEqual(normalize_language(" pt_br "), "pt-BR")

    def test_extra_languages_keep_order_without_duplicates(self) -> None:
        self.assertEqual(parse_extra_languages("nl-NL, DE-de, nl-nl", "en-US"), ["nl-NL", "de-DE"])

    def test_single_language_project_uses_the_dist_root(self) -> None:
        self.assertEqual(language_folder(ProjectSettings(slug="demo"), "en-US", ("en-US",)), "")

    def test_each_language_gets_its_own_dist_folder(self) -> None:
        self.assertEqual(language_folder(ProjectSettings(slug="demo"), "nl-NL", ("en-US", "nl-NL")), "demo---nl-NL")


class ContentWorkbookTests(SimpleTestCase):
    def test_created_workbook_puts_note_before_languages(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "content.xlsx"
            create_content_workbook(path, ["en-US", "nl-NL"])
            headers = [cell.value for cell in load_workbook(path).active[1]]
        self.assertEqual(headers, ["content_id", "note", "en-US", "nl-NL"])

    def test_appended_rows_get_the_next_id(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "content.xlsx"
            create_content_workbook(path, ["en-US"])
            append_content_row(path, "greeting", {"en-US": "Hello"})
            row = append_content_row(path, "reply", {"en-US": "Hi"})
            table = load_content_table(path)
        self.assertEqual(row.content_id, 2)
        self.assertEqual(table.by_id()[2].values["en-US"], "Hi")


class SettingsFormTests(SimpleTestCase):
    def form(self, **changes: object) -> ProjectSettingsForm:
        data = {
            "name": "Demo", "frame_width": "1920", "frame_height": "1080", "default_delay_seconds": "0.75",
            "letterbox_color": "#000000", "participant_parameter": "ppn", "finish_redirect_url": "",
        }
        return ProjectSettingsForm({**data, **changes})

    def test_redirect_url_may_contain_the_id_placeholder(self) -> None:
        self.assertTrue(self.form(finish_redirect_url="https://x.qualtrics.com/jfe/form/SV_1?ppn={ID}").is_valid())

    def test_participant_parameter_rejects_spaces(self) -> None:
        self.assertFalse(self.form(participant_parameter="my id").is_valid())

    def test_frame_size_accepts_decimals(self) -> None:
        self.assertTrue(self.form(frame_width="1080.5").is_valid())


class FileBoundaryTests(SimpleTestCase):
    def test_safe_child_rejects_parent_traversal(self) -> None:
        with TemporaryDirectory() as directory, self.assertRaises(ValueError):
            safe_child(Path(directory), "../outside.txt")

    def test_regeneration_refuses_a_dist_inside_project(self) -> None:
        with TemporaryDirectory() as directory:
            base = Path(directory)
            with override_settings(BASE_DIR=base, PROJECT_DIR=base / "project", DIST_DIR=base / "project" / "dist"):
                with self.assertRaises(ValueError):
                    reset_dist_directory()

    def test_regeneration_keeps_downloaded_study_logs(self) -> None:
        with TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "dist" / "logs").mkdir(parents=True)
            (base / "dist" / "logs" / "R_abc--v1.jsonl").write_text("{}\n", encoding="utf-8")
            (base / "dist" / "old.html").write_text("", encoding="utf-8")
            with override_settings(BASE_DIR=base, PROJECT_DIR=base / "project", DIST_DIR=base / "dist"):
                reset_dist_directory()
            names = sorted(path.name for path in (base / "dist").rglob("*"))
        self.assertEqual(names, ["R_abc--v1.jsonl", "logs"])


class StudyLogTests(SimpleTestCase):
    def test_every_visit_gets_its_own_log_file(self) -> None:
        self.assertEqual(log_file_name(EVENT), "R_abc--20260910T101530Z-a1b2.jsonl")

    def test_unsafe_participant_ids_are_made_file_safe(self) -> None:
        self.assertEqual(safe_name("../R abc"), "R-abc")

    def test_play_test_visits_are_recognized(self) -> None:
        self.assertEqual(session_kind("playtest-en-us-123"), "play-test")

    def test_qualtrics_ids_count_as_study_visits(self) -> None:
        self.assertEqual(session_kind("R_1abcDEF"), "study")

    def test_import_never_overwrites_an_existing_log(self) -> None:
        data = (json.dumps(EVENT) + "\n").encode()
        with TemporaryDirectory() as directory:
            (Path(directory) / "logs").mkdir()
            with override_settings(PROJECT_DIR=Path(directory)):
                import_jsonl("first.jsonl", data)
                with self.assertRaises(ValueError):
                    import_jsonl("again.jsonl", data)

    def test_import_rejects_two_visits_in_one_file(self) -> None:
        data = (json.dumps(EVENT) + "\n" + json.dumps({**EVENT, "visit_id": "other"}) + "\n").encode()
        with TemporaryDirectory() as directory:
            (Path(directory) / "logs").mkdir()
            with override_settings(PROJECT_DIR=Path(directory)), self.assertRaises(ValueError):
                import_jsonl("mixed.jsonl", data)


class FlowchartTests(TestCase):
    databases = {"project"}

    def test_new_linked_frame_is_placed_right_of_its_source(self) -> None:
        source = Frame.objects.create(name="frame-1", flow_x=100, flow_y=50)
        frame = create_frame(linked_from=source)
        self.assertEqual((frame.flow_x, frame.flow_y), (100 + STEP_X, 50))

    def test_second_frame_from_the_same_source_does_not_overlap(self) -> None:
        source = Frame.objects.create(name="frame-1", flow_x=100, flow_y=50)
        first = create_frame(linked_from=source)
        second = create_frame(linked_from=source)
        self.assertNotEqual((first.flow_x, first.flow_y), (second.flow_x, second.flow_y))


class ProjectTestCase(TestCase):
    """A throw-away project folder, dist folder and in-memory project database."""

    databases = {"project"}
    languages: list[str] = ["en-US"]

    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        project_dir = self.root / "project"
        settings_override = override_settings(
            BASE_DIR=self.root, PROJECT_DIR=project_dir, PROJECT_DB=project_dir / "project.sqlite3", DIST_DIR=self.root / "dist",
        )
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.project = make_project_folder(project_dir, self.languages)


class StudioViewTests(ProjectTestCase):

    def test_dragged_flowchart_positions_are_stored(self) -> None:
        Frame.objects.create(name="frame-1")
        Frame.objects.create(name="frame-2")
        body = {"positions": [{"name": "frame-1", "x": 10, "y": 20}, {"name": "frame-2", "x": 300, "y": 20}]}
        self.client.post(reverse("studio:flow_positions_api"), json.dumps(body), content_type="application/json")
        positions = list(Frame.objects.values_list("name", "flow_x", "flow_y"))
        self.assertEqual(positions, [("frame-1", 10.0, 20.0), ("frame-2", 300.0, 20.0)])

    def test_single_language_projects_cannot_create_picker_frames(self) -> None:
        self.client.post(reverse("studio:new_frame"), {"picker": "1"})
        self.assertFalse(Frame.objects.filter(is_language_picker=True).exists())

    def test_regenerate_works_twice_in_a_row(self) -> None:
        Frame.objects.create(name="frame-1")
        generate_dist(self.project)
        generate_dist(self.project)
        self.assertTrue((self.root / "dist" / "index.html").is_file())

    def test_single_language_story_is_the_dist_root(self) -> None:
        Frame.objects.create(name="frame-1")
        report = generate_dist(self.project)
        self.assertEqual([build.folder for build in report.builds], [""])

    def test_preview_log_writes_one_file_per_visit(self) -> None:
        url = reverse("studio:preview_log")
        self.client.post(url, json.dumps(EVENT), content_type="application/json")
        self.client.post(url, json.dumps({**EVENT, "visit_id": "second"}), content_type="application/json")
        names = sorted(path.name for path in (self.root / "project" / "logs").iterdir())
        self.assertEqual(names, ["R_abc--20260910T101530Z-a1b2.jsonl", "R_abc--second.jsonl"])


class MultiLanguageTests(ProjectTestCase):
    languages = ["en-US", "nl-NL"]

    def setUp(self) -> None:
        super().setUp()
        Frame.objects.create(name="frame-1")
        picker = Frame.objects.create(name="picker-1", is_language_picker=True)
        Element.objects.create(frame=picker, component="choice-button", text="Nederlands", target_language="nl-NL")

    def test_picker_page_comes_first_then_one_folder_per_language(self) -> None:
        report = generate_dist(self.project)
        self.assertEqual([build.folder for build in report.builds], ["", "demo---en-US", "demo---nl-NL"])

    def test_every_language_folder_has_its_own_page(self) -> None:
        generate_dist(self.project)
        self.assertTrue((self.root / "dist" / "demo---nl-NL" / "index.html").is_file())

    def test_picker_frames_are_not_in_the_language_pages(self) -> None:
        generate_dist(self.project)
        story_js = (self.root / "dist" / "demo---en-US" / "story.js").read_text(encoding="utf-8")
        self.assertNotIn("picker-1", story_js)

    def test_a_language_without_a_picker_button_is_an_error(self) -> None:
        issues = validate_project(self.project, load_content_table(self.root / "project" / "content.xlsx"))
        self.assertIn("No language-picker button leads to en-US.", [issue.message for issue in issues])

    def test_tidy_up_puts_picker_frames_left_of_the_story(self) -> None:
        tidy_layout()
        self.assertLess(Frame.objects.get(name="picker-1").flow_x, Frame.objects.get(name="frame-1").flow_x)

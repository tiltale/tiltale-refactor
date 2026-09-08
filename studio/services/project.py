"""Project-folder lifecycle and filesystem helpers."""

from dataclasses import dataclass
from pathlib import Path
import re
import shutil
from typing import Iterable

from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError, connections
from django.utils.text import slugify

from studio.models import Frame, ProjectSettings

from .components import default_color_css
from .content import create_content_workbook


@dataclass(frozen=True, slots=True)
class ProjectHealth:
    exists: bool
    ready: bool
    problems: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MaterialFile:
    relative_path: str
    name: str
    modified_timestamp: float


PROJECT_REQUIRED_PATHS: tuple[str, ...] = (
    "project.sqlite3",
    "content.xlsx",
    "materials",
    "logs",
    "default-colors.css",
    "style-overrides.css",
)
IMAGE_SUFFIXES: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})


def project_exists() -> bool:
    return settings.PROJECT_DIR.is_dir()


def project_health() -> ProjectHealth:
    if not project_exists():
        return ProjectHealth(exists=False, ready=False, problems=())
    problems: list[str] = [
        f"Missing project/{name}"
        for name in PROJECT_REQUIRED_PATHS
        if not (settings.PROJECT_DIR / name).exists()
    ]
    return ProjectHealth(exists=True, ready=not problems, problems=tuple(problems))


def project_settings() -> ProjectSettings | None:
    """Return the singleton only when a usable project database exists.

    The explicit file check prevents SQLite from silently creating a blank file
    when someone manually creates an incomplete ``/project`` directory.
    """
    if not settings.PROJECT_DB.is_file():
        return None
    try:
        return ProjectSettings.objects.using("project").first()
    except DatabaseError:
        return None


def create_project(name: str, base_language: str, extra_languages: list[str]) -> ProjectSettings:
    """Create the complete project folder atomically enough for a local tool."""
    if project_exists():
        raise FileExistsError("A /project directory already exists.")

    project_dir: Path = settings.PROJECT_DIR
    project_dir.mkdir()
    try:
        (project_dir / "materials").mkdir()
        (project_dir / "logs").mkdir()
        languages: list[str] = [base_language, *extra_languages]
        create_content_workbook(project_dir / "content.xlsx", languages)
        (project_dir / "default-colors.css").write_text(default_color_css(), encoding="utf-8")
        (project_dir / "style-overrides.css").write_text(
            "/* Advanced project CSS overrides. Keep this file small and document unusual rules. */\n",
            encoding="utf-8",
        )

        # The database alias already points here. Closing any stale connection is
        # enough after the directory is created; no settings mutation is needed.
        connections["project"].close()
        call_command("migrate", database="project", interactive=False, verbosity=0)
        row: ProjectSettings = ProjectSettings.objects.using("project").create(
            name=name.strip(),
            slug=slugify(name) or "tiltale-project",
            base_language=base_language,
        )
        return row
    except Exception:
        connections["project"].close()
        shutil.rmtree(project_dir, ignore_errors=True)
        raise


def next_frame_name() -> str:
    """Use the highest numeric frame suffix + 1; deleted names are not reused."""
    highest: int = 0
    pattern: re.Pattern[str] = re.compile(r"^frame-(\d+)$")
    for name in Frame.objects.values_list("name", flat=True):
        match: re.Match[str] | None = pattern.fullmatch(name)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"frame-{highest + 1}"


def safe_child(root: Path, relative_path: str) -> Path:
    """Resolve a user-derived path while preventing ``../`` traversal."""
    candidate: Path = (root / relative_path).resolve()
    resolved_root: Path = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("Path escapes the allowed TilTale directory.")
    return candidate


def list_materials() -> list[MaterialFile]:
    root: Path = settings.PROJECT_DIR / "materials"
    if not root.is_dir():
        return []
    files: list[MaterialFile] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            files.append(
                MaterialFile(
                    relative_path=path.relative_to(root).as_posix(),
                    name=path.name,
                    modified_timestamp=path.stat().st_mtime,
                )
            )
    return sorted(files, key=lambda item: item.name.casefold())


def newest_source_timestamp(extra_paths: Iterable[Path] = ()) -> float:
    """Return the newest relevant source mtime for stale-build detection."""
    candidates: list[Path] = [settings.PROJECT_DB, settings.PROJECT_DIR / "content.xlsx"]
    candidates.extend(extra_paths)
    for folder in (settings.PROJECT_DIR / "materials", settings.COMPONENTS_DIR, settings.RUNTIME_DIR):
        if folder.exists():
            candidates.extend(path for path in folder.rglob("*") if path.is_file())
    candidates.extend(
        path
        for path in (
            settings.PROJECT_DIR / "default-colors.css",
            settings.PROJECT_DIR / "style-overrides.css",
        )
        if path.exists()
    )
    mtimes: list[float] = [path.stat().st_mtime for path in candidates if path.exists()]
    return max(mtimes, default=0.0)

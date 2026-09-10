"""The ``/project/`` folder: creation, health, schema and file helpers."""

from dataclasses import dataclass
from pathlib import Path
import shutil
import threading

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import DatabaseError, connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.utils.text import slugify

from studio.models import ProjectSettings

from .components import default_color_css
from .content import create_content_workbook

PROJECT_FILES: tuple[str, ...] = (
    "project.sqlite3", "content.xlsx", "materials", "logs", "default-colors.css", "style-overrides.css",
)
BRANDING_FILES: tuple[str, ...] = ("logo-tiltale.png", "favicon.ico")  # in the repository root; /project/ may override
IMAGE_SUFFIXES: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})

_schema_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class ProjectHealth:
    exists: bool
    problems: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.exists and not self.problems


def project_exists() -> bool:
    return settings.PROJECT_DIR.is_dir()


def project_health() -> ProjectHealth:
    if not project_exists():
        return ProjectHealth(exists=False, problems=())
    missing = tuple(f"Missing project/{name}" for name in PROJECT_FILES if not (settings.PROJECT_DIR / name).exists())
    return ProjectHealth(exists=True, problems=missing)


def _ensure_schema() -> None:
    """Apply committed migrations whenever the project database lacks the newest one.

    Checked on every call (one small query) rather than remembered per process,
    so a deleted and re-created /project/ is migrated too. Django generates the
    migration files; this only runs ``migrate`` for the project alias.
    """
    with _schema_lock:
        newest: list[tuple[str, str]] = MigrationLoader(None).graph.leaf_nodes("studio")
        if not newest:
            raise ImproperlyConfigured("studio has no migrations yet. Run: python manage.py makemigrations studio")
        applied = MigrationRecorder(connections["project"]).applied_migrations()
        if all(key in applied for key in newest):
            return
        call_command("migrate", database="project", interactive=False, verbosity=0)


def project_settings() -> ProjectSettings | None:
    """Return the settings row, or ``None`` when there is no usable project.

    The file check stops SQLite from creating an empty database inside an
    incomplete, hand-made ``/project/`` folder.
    """
    if not settings.PROJECT_DB.is_file():
        return None
    try:
        _ensure_schema()
        return ProjectSettings.objects.first()
    except DatabaseError:
        return None


def create_project(name: str, base_language: str, extra_languages: list[str]) -> ProjectSettings:
    """Create the complete project folder, or nothing at all."""
    if project_exists():
        raise FileExistsError("A /project/ folder already exists.")
    project_dir: Path = settings.PROJECT_DIR
    project_dir.mkdir()
    try:
        (project_dir / "materials").mkdir()
        (project_dir / "logs").mkdir()
        create_content_workbook(project_dir / "content.xlsx", [base_language, *extra_languages])
        (project_dir / "default-colors.css").write_text(default_color_css(), encoding="utf-8")
        (project_dir / "style-overrides.css").write_text(
            "/* Advanced project CSS. Loaded after all component and color CSS. */\n", encoding="utf-8"
        )
        connections["project"].close()
        _ensure_schema()
        return ProjectSettings.objects.create(
            name=name.strip(), slug=slugify(name) or "tiltale-project", base_language=base_language,
        )
    except Exception:
        connections["project"].close()
        shutil.rmtree(project_dir, ignore_errors=True)
        raise


def safe_child(root: Path, relative_path: str) -> Path:
    """Resolve a user-supplied relative path, refusing ``../`` escapes."""
    candidate: Path = (root / relative_path).resolve()
    resolved_root: Path = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("Path escapes the allowed TilTale directory.")
    return candidate


def list_materials() -> list[str]:
    """Image paths relative to ``/project/materials/``, including subfolders."""
    root: Path = settings.PROJECT_DIR / "materials"
    if not root.is_dir():
        return []
    paths = (path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    return sorted(paths, key=str.casefold)


def newest_source_timestamp() -> float:
    """Newest modification time of anything that ends up in ``/dist/``."""
    files: list[Path] = [
        settings.PROJECT_DB,
        settings.PROJECT_DIR / "content.xlsx",
        settings.PROJECT_DIR / "default-colors.css",
        settings.PROJECT_DIR / "style-overrides.css",
        *(folder / name for folder in (settings.BRANDING_DIR, settings.PROJECT_DIR) for name in BRANDING_FILES),
    ]
    for folder in (settings.PROJECT_DIR / "materials", settings.COMPONENTS_DIR, settings.RUNTIME_DIR):
        if folder.is_dir():
            files.extend(path for path in folder.rglob("*") if path.is_file())
    return max((path.stat().st_mtime for path in files if path.exists()), default=0.0)

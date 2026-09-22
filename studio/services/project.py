"""The ``/project/`` folder: creation, health, schema and file helpers."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import shutil
import threading

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import DatabaseError, connections
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder
from django.utils.text import slugify
from PIL import ExifTags, Image, ImageOps

from studio.models import ProjectSettings

from .components import default_color_css, default_font_css
from .content import create_content_workbook

PROJECT_FILES: tuple[str, ...] = (  # data: TilTale never recreates these, so nothing is silently replaced
    "project.sqlite3", "content.xlsx", "default-colors.css", "style-overrides.css",
)
PROJECT_FOLDERS: tuple[str, ...] = ("materials", "logs")  # containers: an empty one is the same as a missing one
BRANDING_FILES: tuple[str, ...] = ("logo-tiltale.png", "favicon.ico")  # in /branding/; /project/ may override
IMAGE_SUFFIXES: frozenset[str] = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
QUARTER_TURNS: frozenset[int] = frozenset({5, 6, 7, 8})  # EXIF orientations that ImageOps.exif_transpose turns 90°

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
    """Report missing data files, after recreating the two folders that hold nothing of their own.

    Deleting ``logs/`` to start a study clean, or ``materials/`` to shrink a ZIP, is normal; empty
    folders are also dropped by ZIP files and Git. Recreating them hides nothing: a lost image still
    shows up in the preflight check of the frame that uses it.
    """
    if not project_exists():
        return ProjectHealth(exists=False, problems=())
    for name in PROJECT_FOLDERS:
        (settings.PROJECT_DIR / name).mkdir(exist_ok=True)
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
        for name in PROJECT_FOLDERS:
            (project_dir / name).mkdir()
        create_content_workbook(project_dir / "content.xlsx", [base_language, *extra_languages])
        (project_dir / "default-colors.css").write_text(default_color_css(), encoding="utf-8")
        (project_dir / "style-overrides.css").write_text(
            default_font_css() + "\n/* Advanced project CSS. Loaded after all component and color CSS. */\n", encoding="utf-8"
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


def save_material(file_name: str, content: bytes) -> str:
    """Store an uploaded image in ``/project/materials/`` and return its cleaned name.

    An existing file of the same name is replaced (that is how an image is updated);
    the caller says so in its message.
    """
    suffix: str = Path(file_name).suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise ValueError(f"{file_name}: only images are stored in /project/materials/ "
                         f"({', '.join(sorted(IMAGE_SUFFIXES))}).")
    stem: str = re.sub(r"[^A-Za-z0-9_-]+", "-", Path(file_name).stem).strip("-") or "image"
    cleaned: str = stem + suffix
    destination: Path = safe_child(settings.PROJECT_DIR / "materials", cleaned)
    destination.write_bytes(content)
    return cleaned


def delete_material(relative_path: str) -> None:
    path: Path = safe_child(settings.PROJECT_DIR / "materials", relative_path)
    if not path.is_file():
        raise ValueError(f"{relative_path} is not in /project/materials/.")
    path.unlink()


THUMBNAIL_PIXELS: int = 360  # longest edge of a grid thumbnail


def material_thumbnail(relative_path: str) -> Path:
    """A small cached WebP of a material, so the image grids never load multi-megabyte originals.

    Cached in ``/project/.thumbnails/`` under a name derived from the path and the file's
    modification time: a replaced image gets a fresh thumbnail, and the old one is just dead cache.
    """
    source: Path = safe_child(settings.PROJECT_DIR / "materials", relative_path)
    if not source.is_file():
        raise ValueError(f"{relative_path} is not in /project/materials/.")
    cache: Path = settings.PROJECT_DIR / ".thumbnails"
    cache.mkdir(exist_ok=True)
    key: str = hashlib.sha1(f"{relative_path}:{source.stat().st_mtime_ns}".encode("utf-8")).hexdigest()[:16]
    thumbnail: Path = cache / f"{key}.webp"
    if not thumbnail.is_file():
        with Image.open(source) as opened:
            opened.draft("RGB", (THUMBNAIL_PIXELS * 2, THUMBNAIL_PIXELS * 2))  # JPEGs decode at a fraction of full size
            image: Image.Image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((THUMBNAIL_PIXELS, THUMBNAIL_PIXELS))
            image.save(thumbnail, "WEBP", quality=72)
    return thumbnail


_thumbnail_warmer = threading.Lock()


def warm_thumbnails() -> None:
    """Generate any missing thumbnails in the background, so an image grid opens at full speed.

    Called when a page with a grid opens; with the cache warm this is one quick stat per image.
    At most one warmer runs at a time.
    """
    if not _thumbnail_warmer.acquire(blocking=False):
        return

    def work() -> None:
        try:
            for name in list_materials():
                try:
                    material_thumbnail(name)
                except (OSError, ValueError):
                    continue  # an unreadable file still gets its tile; the browser shows the gap
        finally:
            _thumbnail_warmer.release()

    threading.Thread(target=work, daemon=True).start()


def image_size(relative_path: str) -> tuple[int, int]:
    """Width and height of a material as browsers show it, i.e. after EXIF rotation. Reads only the header."""
    with Image.open(safe_child(settings.PROJECT_DIR / "materials", relative_path)) as image:
        width, height = image.size
        turned: bool = image.getexif().get(ExifTags.Base.Orientation) in QUARTER_TURNS
    return (height, width) if turned else (width, height)


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

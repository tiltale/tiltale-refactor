"""Small, local-only Django settings for TilTale.

TilTale deliberately has two database aliases:
- ``default`` is an in-memory bootstrap database. It lets Django start even when
  no project exists yet.
- ``project`` points to ``/project/project.sqlite3``. Studio models are routed
  there and are migrated only when a project is created or imported.

This keeps the root ``/project/`` directory meaningful: its absence means that
TilTale should show the create/import project gate.
"""

from pathlib import Path
import os

BASE_DIR: Path = Path(__file__).resolve().parent.parent
PROJECT_DIR: Path = BASE_DIR / "project"
PROJECT_DB: Path = PROJECT_DIR / "project.sqlite3"
DIST_DIR: Path = BASE_DIR / "dist"
COMPONENTS_DIR: Path = BASE_DIR / "components"
RUNTIME_DIR: Path = BASE_DIR / "runtime"

SECRET_KEY: str = os.environ.get(
    "TILTALE_SECRET_KEY",
    "tiltale-local-development-only-do-not-deploy-this-secret",
)
DEBUG: bool = True
ALLOWED_HOSTS: list[str] = ["127.0.0.1", "localhost"]

INSTALLED_APPS: list[str] = [
    "django.contrib.staticfiles",
    "studio",
]

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF: str = "config.urls"

TEMPLATES: list[dict[str, object]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    }
]

WSGI_APPLICATION: str = "config.wsgi.application"

DATABASES: dict[str, dict[str, object]] = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "project": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(PROJECT_DB),
        # Tests must never create /project/. Django uses an in-memory project
        # database when running the source test suite.
        "TEST": {"NAME": ":memory:"},
    },
}
DATABASE_ROUTERS: list[str] = ["studio.db.ProjectDatabaseRouter"]

LANGUAGE_CODE: str = "en-us"
TIME_ZONE: str = "UTC"
USE_I18N: bool = True
USE_TZ: bool = True

STATIC_URL: str = "static/"
DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"

# The generated story is shown inside the developer dashboard's same-origin iframe.
X_FRAME_OPTIONS: str = "SAMEORIGIN"

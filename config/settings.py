"""Small, local-only Django settings for TilTale.

TilTale has two database aliases:

- ``default`` is deliberately empty. Django requires the alias, but TilTale keeps
  no data there. Because it is empty, ``runserver`` has nothing to report as
  "unapplied migrations", even when no project exists yet.
- ``project`` is ``/project/project.sqlite3``. ``studio.db.ProjectDatabaseRouter``
  sends every studio model there, and TilTale applies pending migrations to it
  automatically when a project is created or opened (``services/project.py``).

So the absence of ``/project/`` simply means "no active project".
"""

from pathlib import Path
import os

TILTALE_VERSION: str = "2.6.7"  # bump on every release; CI checks this on pull requests

BASE_DIR: Path = Path(__file__).resolve().parent.parent
PROJECT_DIR: Path = BASE_DIR / "project"
PROJECT_DB: Path = PROJECT_DIR / "project.sqlite3"
DIST_DIR: Path = PROJECT_DIR / "dist"  # the generated website lives with the project it belongs to
COMPONENTS_DIR: Path = BASE_DIR / "components"
FRAME_TYPES_DIR: Path = BASE_DIR / "frame-types"  # names and help texts of the frame kinds
RUNTIME_DIR: Path = BASE_DIR / "runtime"
BRANDING_DIR: Path = BASE_DIR / "branding"  # default logo-tiltale.png and favicon.ico for every project
PROMPTS_DIR: Path = BASE_DIR / "docs" / "llm-prompts"

SECRET_KEY: str = os.environ.get(
    "TILTALE_SECRET_KEY",
    "tiltale-local-development-only-do-not-deploy-this-secret",
)
DEBUG: bool = True
ALLOWED_HOSTS: list[str] = ["127.0.0.1", "localhost"]

INSTALLED_APPS: list[str] = [
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "studio",
]

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "studio.middleware.RememberChoicesMiddleware",  # keeps the selected language and the edit origin
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
                "django.contrib.messages.context_processors.messages",
                "studio.views.status_context",
            ],
        },
    }
]

WSGI_APPLICATION: str = "config.wsgi.application"

DATABASES: dict[str, dict[str, object]] = {
    "default": {},
    "project": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(PROJECT_DB),
        # The test suite never touches /project/: it uses an in-memory database.
        # DEPENDENCIES defaults to ["default"], which is never created here, so
        # the test runner would report a "circular dependency".
        "TEST": {"NAME": ":memory:", "DEPENDENCIES": []},
    },
}
DATABASE_ROUTERS: list[str] = ["studio.db.ProjectDatabaseRouter"]

# Flash messages ("Saved.", "Regenerated.") live in a signed cookie, so no
# session table or extra database is needed.
MESSAGE_STORAGE: str = "django.contrib.messages.storage.cookie.CookieStorage"

LANGUAGE_CODE: str = "en-us"
TIME_ZONE: str = "UTC"
USE_I18N: bool = False
USE_TZ: bool = True

STATIC_URL: str = "static/"
STATICFILES_DIRS: list[tuple[str, Path]] = [("runtime", RUNTIME_DIR)]  # the frame editor loads runtime/bubbles.js
DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"

# The generated story is shown inside same-origin iframes in the studio.
X_FRAME_OPTIONS: str = "SAMEORIGIN"

# Regenerate reports its progress in the terminal running ``runserver`` (silent in tests, where DEBUG is off).
LOGGING: dict[str, object] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"require_debug_true": {"()": "django.utils.log.RequireDebugTrue"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "filters": ["require_debug_true"]}},
    "loggers": {"studio": {"handlers": ["console"], "level": "INFO"}},
}

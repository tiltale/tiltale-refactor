"""Database routing for project-scoped authoring data.

Keeping this policy in one small router is simpler than sprinkling ``.using()``
through every view and service. All models in the ``studio`` app belong to the
active project's SQLite file; Django's bootstrap database stays disposable.
"""

from typing import Any


class ProjectDatabaseRouter:
    """Send every studio model read/write/migration to the project database."""

    project_app_label: str = "studio"
    project_alias: str = "project"

    def db_for_read(self, model: type[Any], **hints: Any) -> str | None:
        if model._meta.app_label == self.project_app_label:
            return self.project_alias
        return None

    def db_for_write(self, model: type[Any], **hints: Any) -> str | None:
        if model._meta.app_label == self.project_app_label:
            return self.project_alias
        return None

    def allow_relation(self, obj1: Any, obj2: Any, **hints: Any) -> bool | None:
        labels: set[str] = {obj1._meta.app_label, obj2._meta.app_label}
        if self.project_app_label in labels:
            return labels == {self.project_app_label}
        return None

    def allow_migrate(
        self,
        db: str,
        app_label: str,
        model_name: str | None = None,
        **hints: Any,
    ) -> bool | None:
        if app_label == self.project_app_label:
            return db == self.project_alias
        if db == self.project_alias:
            return False
        return None

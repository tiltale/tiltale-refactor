"""The laura-* components are now basic-*: rename them in every project's elements.

Run once by ``python manage.py migrate``. A project that never used them is untouched. The reverse
step puts the old names back, so ``migrate studio 0008`` still works.
"""

from django.db import migrations

RENAMED: dict[str, str] = {
    "laura-decision": "basic-decision",
    "laura-interact": "basic-interact",
    "laura-narrator": "basic-narrator",
    "laura-next-arrow": "basic-next-arrow",
    "laura-next-text": "basic-next-text",
    "laura-scream-bubble": "basic-scream-bubble",
    "laura-speech-bubble": "basic-speech-bubble",
    "laura-thought-bubble": "basic-thought-bubble",
}


def rename(apps, old_to_new: dict[str, str]) -> None:
    Element = apps.get_model("studio", "Element")
    for old, new in old_to_new.items():
        Element.objects.filter(component=old).update(component=new)


def forwards(apps, schema_editor) -> None:
    rename(apps, RENAMED)


def backwards(apps, schema_editor) -> None:
    rename(apps, {new: old for old, new in RENAMED.items()})


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0008_frame_fade_from_black"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

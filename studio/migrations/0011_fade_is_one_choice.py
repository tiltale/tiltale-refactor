"""Hand-added RunPython step, like 0006: "Fade in from black" used to be a second checkbox that
could be true while "Fade this frame in" was false, in which case the frame did not fade at all.
The editor now offers one three-way choice, stored as fade_in (does it fade?) plus fade_from_black
(from black instead of the previous frame?), so any old frame with only the black box ticked is
normalized to both flags — which is what its author meant.
"""

from django.db import migrations


def normalize_fade_flags(apps, schema_editor):
    Frame = apps.get_model("studio", "Frame")
    Frame.objects.using(schema_editor.connection.alias).filter(fade_from_black=True).update(fade_in=True)


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0010_projectsettings_show_participant_id"),
    ]

    operations = [
        migrations.RunPython(normalize_fade_flags, migrations.RunPython.noop),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("studio", "0009_rename_laura_components"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectsettings",
            name="show_participant_id",
            field=models.BooleanField(default=False),
        ),
    ]

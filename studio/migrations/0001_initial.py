# Generated for TilTale's initial project database schema.

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name="ProjectSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("slug", models.SlugField(max_length=120)),
                ("base_language", models.CharField(max_length=40)),
                ("frame_width", models.PositiveIntegerField(default=1920)),
                ("frame_height", models.PositiveIntegerField(default=1080)),
                ("default_delay_seconds", models.DecimalField(decimal_places=2, default=0.75, max_digits=5, validators=[django.core.validators.MinValueValidator(0)])),
                ("letterbox_color", models.CharField(default="#000000", max_length=7)),
                ("log_endpoint", models.URLField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Frame",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True)),
                ("background_type", models.CharField(choices=[("none", "None"), ("solid", "Solid color"), ("image", "Image")], default="none", max_length=10)),
                ("background_color", models.CharField(default="#111111", max_length=7)),
                ("background_image", models.CharField(blank=True, default="", max_length=500)),
                ("fade_in", models.BooleanField(default=False)),
                ("flow_x", models.FloatField(blank=True, null=True)),
                ("flow_y", models.FloatField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="Element",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("component", models.CharField(max_length=100)),
                ("content_id", models.PositiveIntegerField(blank=True, null=True)),
                ("x", models.FloatField(default=960.0)),
                ("y", models.FloatField(default=540.0)),
                ("width", models.FloatField(default=420.0)),
                ("height", models.FloatField(default=160.0)),
                ("fill_color", models.CharField(blank=True, default="", max_length=7)),
                ("border_color", models.CharField(blank=True, default="", max_length=7)),
                ("text_color", models.CharField(blank=True, default="", max_length=7)),
                ("font_size", models.FloatField(default=42.0)),
                ("break_long_words", models.BooleanField(default=True)),
                ("delay_mode", models.CharField(choices=[("none", "No delay behavior"), ("fade", "Fade in"), ("disable", "Disable click"), ("both", "Fade + disable click")], default="none", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("frame", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="elements", to="studio.frame")),
                ("target_frame", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="incoming_elements", to="studio.frame")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="ElementLanguageOverride",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("language", models.CharField(max_length=40)),
                ("x", models.FloatField(blank=True, null=True)),
                ("y", models.FloatField(blank=True, null=True)),
                ("width", models.FloatField(blank=True, null=True)),
                ("height", models.FloatField(blank=True, null=True)),
                ("font_size", models.FloatField(blank=True, null=True)),
                ("element", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="language_overrides", to="studio.element")),
            ],
        ),
        migrations.AddConstraint(
            model_name="elementlanguageoverride",
            constraint=models.UniqueConstraint(fields=("element", "language"), name="unique_element_language_override"),
        ),
    ]

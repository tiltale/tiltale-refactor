"""Project-scoped authoring models.

The model set is intentionally small. A reusable *component* lives in source
control under ``/components``. An *element* is one placed instance of a
component on a frame and therefore belongs in the project database.
"""

from django.core.validators import MinValueValidator
from django.db import models


class ProjectSettings(models.Model):
    """The single settings row for the active project."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120)
    base_language = models.CharField(max_length=40)
    frame_width = models.PositiveIntegerField(default=1920)
    frame_height = models.PositiveIntegerField(default=1080)
    default_delay_seconds = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.75,
        validators=[MinValueValidator(0)],
    )
    letterbox_color = models.CharField(max_length=7, default="#000000")
    log_endpoint = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class Frame(models.Model):
    """A unique story panel and its language-independent presentation."""

    class BackgroundType(models.TextChoices):
        NONE = "none", "None"
        SOLID = "solid", "Solid color"
        IMAGE = "image", "Image"

    name = models.CharField(max_length=80, unique=True)
    background_type = models.CharField(
        max_length=10,
        choices=BackgroundType.choices,
        default=BackgroundType.NONE,
    )
    background_color = models.CharField(max_length=7, default="#111111")
    background_image = models.CharField(max_length=500, blank=True, default="")
    fade_in = models.BooleanField(default=False)
    flow_x = models.FloatField(null=True, blank=True)
    flow_y = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering: list[str] = ["id"]

    def __str__(self) -> str:
        return self.name


class Element(models.Model):
    """One placed component instance on a frame."""

    class DelayMode(models.TextChoices):
        NONE = "none", "No delay behavior"
        FADE = "fade", "Fade in"
        DISABLE = "disable", "Disable click"
        BOTH = "both", "Fade + disable click"

    frame = models.ForeignKey(Frame, on_delete=models.CASCADE, related_name="elements")
    component = models.CharField(max_length=100)
    content_id = models.PositiveIntegerField(null=True, blank=True)
    x = models.FloatField(default=960.0)
    y = models.FloatField(default=540.0)
    width = models.FloatField(default=420.0)
    height = models.FloatField(default=160.0)

    # Blank means: inherit the component/project CSS variable. This is important:
    # changing /project/default-colors.css must update every non-overridden element.
    fill_color = models.CharField(max_length=7, blank=True, default="")
    border_color = models.CharField(max_length=7, blank=True, default="")
    text_color = models.CharField(max_length=7, blank=True, default="")

    font_size = models.FloatField(default=42.0)
    break_long_words = models.BooleanField(default=True)
    delay_mode = models.CharField(
        max_length=10,
        choices=DelayMode.choices,
        default=DelayMode.NONE,
    )
    target_frame = models.ForeignKey(
        Frame,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_elements",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering: list[str] = ["id"]

    def __str__(self) -> str:
        return f"{self.frame.name}: {self.component} #{self.pk}"


class ElementLanguageOverride(models.Model):
    """Optional presentation tweaks for one language only.

    Content itself stays in ``content.xlsx``. These overrides are limited to the
    values translators/designers may reasonably need to adjust when text grows.
    """

    element = models.ForeignKey(
        Element,
        on_delete=models.CASCADE,
        related_name="language_overrides",
    )
    language = models.CharField(max_length=40)
    x = models.FloatField(null=True, blank=True)
    y = models.FloatField(null=True, blank=True)
    width = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    font_size = models.FloatField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["element", "language"],
                name="unique_element_language_override",
            )
        ]

    def __str__(self) -> str:
        return f"{self.element_id} / {self.language}"

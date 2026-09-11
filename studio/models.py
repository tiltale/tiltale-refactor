"""Project-scoped authoring models.

A reusable *component* lives in source control under ``/components``. An
*element* is one placed instance of a component on a frame, so it lives here.

After changing this file run ``python manage.py makemigrations`` and commit the
generated file. Never write migrations by hand; TilTale applies them to
``/project/project.sqlite3`` automatically on the next request.
"""

from decimal import Decimal
import re
import unicodedata

from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models


def name_key(name: str) -> str:
    """How frame names are compared: "Scene 2_b", "scene-2-b" and "Scene 2 B" are the same name."""
    ascii_name: str = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


class ProjectSettings(models.Model):
    """The single settings row for the active project."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120)
    base_language = models.CharField(max_length=40)
    frame_width = models.FloatField(default=1920.0, validators=[MinValueValidator(1)])
    frame_height = models.FloatField(default=1080.0, validators=[MinValueValidator(1)])
    default_delay_seconds = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.75"),
        validators=[MinValueValidator(0), MaxValueValidator(30)],
    )
    letterbox_color = models.CharField(max_length=7, default="#000000")
    participant_parameter = models.CharField(
        max_length=40,
        default="ppn",
        validators=[RegexValidator(r"^[A-Za-z0-9_.-]+$", "Use letters, digits, '.', '_' or '-'.")],
    )
    finish_redirect_url = models.URLField(max_length=1000, blank=True, default="")

    def __str__(self) -> str:
        return self.name


class Frame(models.Model):
    """One story panel. Language-picker frames only exist in multi-language projects.

    ``key`` (``fnr-12``) identifies the frame in code, logs and preview links and never
    changes; SQLite never reuses the number. ``name`` is only for people.
    """

    class BackgroundType(models.TextChoices):
        NONE = "none", "None"
        SOLID = "solid", "Solid color"
        IMAGE = "image", "Image"

    name = models.CharField(max_length=80, unique=True)
    is_language_picker = models.BooleanField(default=False)
    background_type = models.CharField(
        max_length=10,
        choices=BackgroundType.choices,
        default=BackgroundType.NONE,
    )
    background_color = models.CharField(max_length=7, default="#111111")
    background_image = models.CharField(max_length=500, blank=True, default="")
    # Center and size of a moved or resized background image, in frame pixels. Empty: it covers the frame.
    background_x = models.FloatField(null=True, blank=True)
    background_y = models.FloatField(null=True, blank=True)
    background_width = models.FloatField(null=True, blank=True)
    background_height = models.FloatField(null=True, blank=True)
    fade_in = models.BooleanField(default=False)
    # Document frames: readers may zoom and drag the frame, and a fixed "× Close" button
    # returns to the previous frame. Its label is a row of content.xlsx (empty: just "×").
    zoomable = models.BooleanField(default=False)
    close_content_id = models.PositiveIntegerField(null=True, blank=True)
    flow_x = models.FloatField(default=0.0)
    flow_y = models.FloatField(default=0.0)

    class Meta:
        ordering: list[str] = ["id"]

    def __str__(self) -> str:
        return self.name

    @property
    def key(self) -> str:
        return f"fnr-{self.pk}"

    @property
    def background_box(self) -> dict[str, float] | None:
        """Where the background image was dragged to, or ``None`` while it covers the frame."""
        if self.background_width is None:
            return None
        return {"x": self.background_x, "y": self.background_y, "width": self.background_width, "height": self.background_height}


class Element(models.Model):
    """One placed component instance, or one image from /project/materials/, on a frame."""

    class DelayMode(models.TextChoices):
        NONE = "none", "No delay behavior"
        FADE = "fade", "Fade in"
        DISABLE = "disable", "Disable click"
        BOTH = "both", "Fade + disable click"

    frame = models.ForeignKey(Frame, on_delete=models.CASCADE, related_name="elements")
    component = models.CharField(max_length=100)  # empty for image elements
    image = models.CharField(max_length=500, blank=True, default="")  # path in /project/materials/
    # Story frames take text from content.xlsx. Language-picker frames are shown
    # before a language is known, so their text is typed directly into ``text``.
    content_id = models.PositiveIntegerField(null=True, blank=True)
    text = models.TextField(blank=True, default="")
    x = models.FloatField(default=960.0)
    y = models.FloatField(default=540.0)
    width = models.FloatField(default=420.0)
    height = models.FloatField(default=160.0)

    # Blank means "inherit the project/component color" from default-colors.css.
    fill_color = models.CharField(max_length=7, blank=True, default="")
    border_color = models.CharField(max_length=7, blank=True, default="")
    text_color = models.CharField(max_length=7, blank=True, default="")

    # Tip of a bubble's tail, in frame pixels from the element's center. Empty: the component's default place.
    tail_x = models.FloatField(null=True, blank=True)
    tail_y = models.FloatField(null=True, blank=True)

    font_size = models.FloatField(default=44.0)
    break_long_words = models.BooleanField(default=True)
    delay_mode = models.CharField(max_length=10, choices=DelayMode.choices, default=DelayMode.NONE)
    order = models.PositiveIntegerField(default=0)  # stacking on the frame: higher is in front; ties by id

    # What a click does. At most one of these is set (the editor enforces it).
    target_frame = models.ForeignKey(
        Frame,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_elements",
    )
    target_language = models.CharField(max_length=40, blank=True, default="")
    ends_story = models.BooleanField(default=False)

    class Meta:
        ordering: list[str] = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.frame.name}: {self.component} #{self.pk}"

    def save(self, *args: object, **kwargs: object) -> None:
        if self._state.adding and not self.order:  # a new element goes in front of the others
            top: int | None = Element.objects.filter(frame_id=self.frame_id).aggregate(top=models.Max("order"))["top"]
            self.order = (top or 0) + 1
        super().save(*args, **kwargs)

    def geometry(self, language: str) -> dict[str, float]:
        """Position, size and font size for ``language``, including overrides.

        Uses ``language_overrides.all()`` so callers can prefetch it.
        """
        values: dict[str, float] = {
            "x": self.x, "y": self.y, "width": self.width,
            "height": self.height, "font_size": self.font_size,
        }
        for override in self.language_overrides.all():
            if override.language != language:
                continue
            for key in values:
                value: float | None = getattr(override, key)
                if value is not None:
                    values[key] = value
        return values


class ElementLanguageOverride(models.Model):
    """Geometry/font tweaks for one translation. Text itself stays in content.xlsx."""

    element = models.ForeignKey(Element, on_delete=models.CASCADE, related_name="language_overrides")
    language = models.CharField(max_length=40)
    x = models.FloatField(null=True, blank=True)
    y = models.FloatField(null=True, blank=True)
    width = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    font_size = models.FloatField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["element", "language"], name="unique_element_language_override"),
        ]

    def __str__(self) -> str:
        return f"{self.element_id} / {self.language}"

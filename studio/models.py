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

from studio.services.variables import kind_of, parse_value  # pure helpers, no models: safe to import here


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
    # Shows "ID: <first characters>…" in the bottom-right corner of every frame that has an
    # "End story" or "Restart the story" element, so an experimenter can read back which
    # participant a device was on.
    show_participant_id = models.BooleanField(default=False)
    # Protecting logs (see ETHICS.md): the public key goes into /dist/, the private key is handed out
    # once and never stored. ``log_key_pending`` holds it only between generating and confirming the download.
    log_public_key = models.TextField(blank=True, default="")
    log_key_created = models.DateTimeField(null=True, blank=True)
    log_key_pending = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return self.name

    @property
    def logs_protected(self) -> bool:
        return bool(self.log_public_key)


class Frame(models.Model):
    """One node of the story. Its ``kind`` decides what readers get (see /frame-types/README.md).

    ``key`` (``fnr-12``) identifies the frame in code, logs and preview links and never
    changes; SQLite never reuses the number. ``name`` is only for people.
    """

    class Kind(models.TextChoices):
        FRAME = "frame", "Frame"
        PICKER = "picker", "Picker"  # start page of a multi-language project
        DOCUMENT = "document", "Document"  # one zoomable image, closed to return
        VALIDATION = "validation", "Validation point"  # invisible: rules on the variables decide the next frame
        MINIGAME = "minigame", "Minigame"  # like a frame, reserved for later

    class BackgroundType(models.TextChoices):
        NONE = "none", "None"
        SOLID = "solid", "Solid color"
        IMAGE = "image", "Image"

    name = models.CharField(max_length=80, unique=True)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.FRAME)
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
    fade_in = models.BooleanField(default=False)  # crossfades from the frame before it, in "Element delay" seconds
    fade_from_black = models.BooleanField(default=False)  # ...or from black instead
    # Documents: ``background_image`` is the document; the fixed "× Close" button returns to the
    # previous frame and its label is a row of content.xlsx (empty: just "×").
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
    def is_language_picker(self) -> bool:
        return self.kind == self.Kind.PICKER

    @property
    def is_document(self) -> bool:
        return self.kind == self.Kind.DOCUMENT

    @property
    def has_canvas(self) -> bool:
        """Frames whose elements readers see; documents show one image and validation points nothing."""
        return self.kind in (self.Kind.FRAME, self.Kind.PICKER, self.Kind.MINIGAME)

    @property
    def background_box(self) -> dict[str, float] | None:
        """Where the background image was dragged to, or ``None`` while it covers the frame."""
        if self.background_width is None:
            return None
        return {"x": self.background_x, "y": self.background_y, "width": self.background_width, "height": self.background_height}


class Variable(models.Model):
    """A global variable of the story, e.g. ``score`` starting at ``0`` (see services/variables.py)."""

    name = models.CharField(max_length=40, unique=True)
    initial_value = models.CharField(max_length=200)

    class Meta:
        ordering: list[str] = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def kind(self) -> str:
        """``"number"`` or ``"text"``, decided by the initial value."""
        return kind_of(parse_value(self.initial_value))


class Rule(models.Model):
    """One row of a validation point: ``if <variable> <comparator> <value> go to <target>``.

    Rules are checked in ``order``; a rule without a variable is the "otherwise" row that always matches.
    """

    frame = models.ForeignKey(Frame, on_delete=models.CASCADE, related_name="rules")
    order = models.PositiveIntegerField(default=0)
    variable = models.ForeignKey(Variable, on_delete=models.PROTECT, null=True, blank=True, related_name="rules")
    comparator = models.CharField(max_length=2, default="==")
    value = models.CharField(max_length=200, blank=True, default="")
    target_frame = models.ForeignKey(Frame, on_delete=models.SET_NULL, null=True, blank=True, related_name="incoming_rules")

    class Meta:
        ordering: list[str] = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.frame.name}: rule #{self.pk}"

    @property
    def key(self) -> str:
        """Identifies the rule in logs and the flowchart, like an element's id: ``rule-7``."""
        return f"rule-{self.pk}"

    @property
    def target_value(self) -> str:
        """The rule's target as the frame editor's dropdown value (``frame:12`` or empty)."""
        return f"frame:{self.target_frame_id}" if self.target_frame_id else ""


class Element(models.Model):
    """One placed component instance, or one image from /project/materials/, on a frame.

    Without a frame, an element (a scoreboard from Settings → Advanced) is shown on every story
    frame except those in ``hidden_on``.
    """

    class DelayMode(models.TextChoices):
        NONE = "none", "No delay behavior"
        FADE = "fade", "Fade in"
        DISABLE = "disable", "Disable click"
        BOTH = "both", "Fade + disable click"

    frame = models.ForeignKey(Frame, on_delete=models.CASCADE, null=True, blank=True, related_name="elements")
    hidden_on = models.ManyToManyField(Frame, blank=True, related_name="hidden_global_elements")
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
    break_long_words = models.BooleanField(default=False)
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
    restarts_story = models.BooleanField(default=False)

    # Optionally, a click also changes one global variable: set it to ``update_value`` or add ``update_value`` to it.
    update_variable = models.ForeignKey(Variable, on_delete=models.PROTECT, null=True, blank=True, related_name="updates")
    update_operation = models.CharField(max_length=3, default="set")
    update_value = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering: list[str] = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.frame.name if self.frame else 'every frame'}: {self.component} #{self.pk}"

    @property
    def leads_somewhere(self) -> bool:
        return bool(self.target_frame_id or self.target_language or self.ends_story or self.restarts_story)

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

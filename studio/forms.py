"""Server-side validation for input that changes durable project state."""

import re

from django import forms

from .models import Frame, ProjectSettings, name_key

LANGUAGE_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{2,8})*$")
HEX_PATTERN: re.Pattern[str] = re.compile(r"^#[0-9A-Fa-f]{6}$")


def normalize_language(value: str) -> str:
    """``" pt_br "`` → ``"pt-BR"``; ``"NL"`` → ``"nl"``."""
    cleaned: str = value.strip().replace("_", "-")
    if not LANGUAGE_PATTERN.fullmatch(cleaned):
        raise forms.ValidationError("Use a language code such as en-US, nl or pt-BR.")
    first, *rest = cleaned.split("-")
    return "-".join([first.lower(), *(part.upper() for part in rest)])


def parse_extra_languages(value: str, base_language: str) -> list[str]:
    """Comma-separated codes, in order, without duplicates or the base language."""
    result: list[str] = []
    seen: set[str] = {base_language.casefold()}
    for raw in filter(str.strip, value.split(",")):
        language: str = normalize_language(raw)
        if language.casefold() not in seen:
            seen.add(language.casefold())
            result.append(language)
    return result


def validate_hex(value: str) -> str:
    cleaned: str = value.strip()
    if not HEX_PATTERN.fullmatch(cleaned):
        raise forms.ValidationError("Use a color such as #003366.")
    return cleaned.upper()


class NewProjectForm(forms.Form):
    name = forms.CharField(max_length=120, label="Project name")
    base_language = forms.CharField(max_length=40, initial="en-US")
    extra_languages = forms.CharField(required=False)

    def clean_base_language(self) -> str:
        return normalize_language(self.cleaned_data["base_language"])

    def clean_extra_languages(self) -> list[str]:
        base: str = str(self.cleaned_data.get("base_language", ""))  # cleaned first: fields clean in order
        return parse_extra_languages(self.cleaned_data["extra_languages"], base)


class ProjectSettingsForm(forms.ModelForm):
    class Meta:
        model = ProjectSettings
        fields = [
            "name", "frame_width", "frame_height", "letterbox_color",
            "default_delay_seconds", "participant_parameter", "finish_redirect_url",
        ]
        labels = {
            "name": "Project name",
            "frame_width": "Frame width (px)",
            "frame_height": "Frame height (px)",
            "letterbox_color": "Color around the story",
            "default_delay_seconds": "Element delay (seconds)",
            "participant_parameter": "Participant ID parameter",
            "finish_redirect_url": "Finish redirect URL",
        }
        help_texts = {
            "name": "Shown as the browser tab title of the generated story. The /dist/ folder names keep the "
                    "slug chosen when the project was created.",
            "frame_width": "Width of the design canvas in pixels; decimals are allowed. Element positions are "
                           "stored in pixels, so changing this later does not move or rescale placed elements.",
            "frame_height": "Height of the design canvas in pixels. Same rule as the width.",
            "letterbox_color": "Fills the screen area that the story frame does not cover, e.g. the bars on a "
                               "phone held upright while the story is landscape.",
            "default_delay_seconds": "Used by elements whose delay behavior is “Fade in”, “Disable click” or both: "
                                     "they fade in, or ignore clicks, for this long so readers cannot skip a frame "
                                     "by clicking too fast.",
            "participant_parameter": "URL parameter that carries an external participant ID. With the default "
                                     "“ppn”, a link such as …/index.html?ppn=R_abc123 (e.g. from Qualtrics) logs as "
                                     "participant R_abc123. Without it, the story generates a random ID.",
            "finish_redirect_url": "Where participants go after clicking an element set to “End story”. Write {ID} "
                                   "where their participant ID belongs, e.g. "
                                   "https://yourschool.qualtrics.com/jfe/form/SV_abc?ppn={ID}. Leave empty to "
                                   "show a simple end screen instead.",
        }
        widgets = {
            "frame_width": forms.NumberInput(attrs={"step": "any", "min": "1"}),
            "frame_height": forms.NumberInput(attrs={"step": "any", "min": "1"}),
            "letterbox_color": forms.TextInput(attrs={"type": "color"}),
            "finish_redirect_url": forms.TextInput(attrs={"placeholder": "https://…?ppn={ID}", "spellcheck": "false"}),
        }

    def clean_letterbox_color(self) -> str:
        return validate_hex(self.cleaned_data["letterbox_color"])


class FrameForm(forms.ModelForm):
    """Frame-level settings: name, background and fade-in."""

    class Meta:
        model = Frame
        fields = ["name", "fade_in", "background_type", "background_color", "background_image"]
        labels = {"fade_in": "Fade this frame in", "background_type": "Background", "background_image": "Image"}
        help_texts = {"name": "Only for you: spaces are fine. The story's code and logs use the fixed ID below."}
        widgets = {"background_color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args: object, materials: list[str], **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.materials: list[str] = materials

    def clean_name(self) -> str:
        name: str = " ".join(self.cleaned_data["name"].split())
        key: str = name_key(name)
        if not key:
            raise forms.ValidationError("Use at least one letter or digit.")
        others = Frame.objects.exclude(pk=self.instance.pk).values_list("name", flat=True)
        clash: str | None = next((other for other in others if name_key(other) == key), None)
        if clash is not None:
            raise forms.ValidationError(f"Another frame is called “{clash}”. Names must differ in more than capitals, spaces, “-” or “_”.")
        return name

    def clean_background_color(self) -> str:
        return validate_hex(self.cleaned_data["background_color"])

    def clean(self) -> dict[str, object]:
        cleaned: dict[str, object] = super().clean()
        kind = cleaned.get("background_type")
        if kind == Frame.BackgroundType.IMAGE and cleaned.get("background_image") not in self.materials:
            self.add_error("background_image", "Choose an image that exists in /project/materials/.")
        if kind != Frame.BackgroundType.IMAGE:
            cleaned["background_image"] = ""
        return cleaned

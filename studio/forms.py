"""Small Django forms for server-side validation.

Forms are used where user input changes durable state. The visual element
inspector is intentionally handled by a focused view because its fields are
partly language-dependent; that view still validates every value server-side.
"""

from decimal import Decimal
import re

from django import forms

from .models import Frame, ProjectSettings

LANGUAGE_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{2,8})*$")
HEX_PATTERN: re.Pattern[str] = re.compile(r"^#[0-9A-Fa-f]{6}$")


def normalize_language(value: str) -> str:
    """Return a predictable language code such as ``en-US`` or ``nl``."""
    cleaned: str = value.strip().replace("_", "-")
    if not LANGUAGE_PATTERN.fullmatch(cleaned):
        raise forms.ValidationError("Use a language code such as en-US, nl, or pt-BR.")
    parts: list[str] = cleaned.split("-")
    if len(parts) == 1:
        return parts[0].lower()
    return "-".join([parts[0].lower(), *[part.upper() for part in parts[1:]]])


def parse_extra_languages(value: str, base_language: str) -> list[str]:
    """Parse comma-separated language codes, preserving order and uniqueness."""
    result: list[str] = []
    seen: set[str] = {base_language.casefold()}
    for raw in value.split(","):
        if not raw.strip():
            continue
        language: str = normalize_language(raw)
        key: str = language.casefold()
        if key not in seen:
            seen.add(key)
            result.append(language)
    return result


def validate_hex(value: str) -> str:
    """Validate and normalize a six-digit CSS hexadecimal color."""
    cleaned: str = value.strip()
    if not HEX_PATTERN.fullmatch(cleaned):
        raise forms.ValidationError("Use a color such as #003366.")
    return cleaned.upper()


class NewProjectForm(forms.Form):
    name = forms.CharField(max_length=120, label="Project name")
    base_language = forms.CharField(max_length=40, initial="en-US")
    extra_languages = forms.CharField(
        required=False,
        help_text="Optional, comma-separated. Example: nl-NL, de-DE",
    )

    def clean_base_language(self) -> str:
        return normalize_language(self.cleaned_data["base_language"])

    def clean(self) -> dict[str, object]:
        cleaned: dict[str, object] = super().clean()
        base: str | None = cleaned.get("base_language")  # type: ignore[assignment]
        extras: str = str(cleaned.get("extra_languages") or "")
        if base:
            cleaned["parsed_extra_languages"] = parse_extra_languages(extras, base)
        return cleaned


class ProjectSettingsForm(forms.ModelForm):
    class Meta:
        model = ProjectSettings
        fields = [
            "name",
            "frame_width",
            "frame_height",
            "default_delay_seconds",
            "letterbox_color",
            "log_endpoint",
        ]
        widgets = {"letterbox_color": forms.TextInput(attrs={"type": "color"})}

    def clean_letterbox_color(self) -> str:
        return validate_hex(self.cleaned_data["letterbox_color"])

    def clean_default_delay_seconds(self) -> Decimal:
        value: Decimal = self.cleaned_data["default_delay_seconds"]
        if value > Decimal("30"):
            raise forms.ValidationError("Keep the default delay at 30 seconds or less.")
        return value


class FrameBackgroundForm(forms.ModelForm):
    class Meta:
        model = Frame
        fields = ["background_type", "background_color", "background_image", "fade_in"]
        widgets = {"background_color": forms.TextInput(attrs={"type": "color"})}

    def clean_background_color(self) -> str:
        return validate_hex(self.cleaned_data["background_color"])

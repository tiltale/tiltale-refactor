"""HTTP views for TilTale's local authoring interface.

Views validate HTTP input and delegate file/workbook/generation work to services.
That keeps the browser layer conventional and the non-HTTP logic testable.
"""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .forms import FrameBackgroundForm, NewProjectForm, ProjectSettingsForm, validate_hex
from .models import Element, ElementLanguageOverride, Frame, ProjectSettings
from .services.components import ComponentDefinition, component_css, component_map, load_components
from .services.content import ContentRow, ContentTable, load_content_table
from .services.generate import dist_is_stale, generate_dist, language_directory, load_build_report
from .services.project import (
    create_project,
    list_materials,
    next_frame_name,
    project_exists,
    project_health,
    project_settings,
    safe_child,
)
from .services.study_logs import append_event, import_jsonl, read_events, session_summaries
from .services.validate import DEVICE_PRESETS, ValidationIssue, validate_project


def _notice_redirect(name: str, notice: str, **kwargs: object) -> HttpResponse:
    url: str = reverse(name, kwargs=kwargs or None)
    return redirect(f"{url}?notice={quote(notice)}")


def _active_project() -> ProjectSettings | None:
    return project_settings()


def _content_table() -> ContentTable:
    return load_content_table(settings.PROJECT_DIR / "content.xlsx", assign_missing_ids=True)


def _language(content: ContentTable, project: ProjectSettings, requested: str | None) -> str:
    if requested and requested in content.languages:
        return requested
    if project.base_language in content.languages:
        return project.base_language
    return content.languages[0]


def _float(value: object, label: str, minimum: float | None = None) -> float:
    try:
        parsed: float = float(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a number.") from error
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{label} must be at least {minimum:g}.")
    return parsed


def _optional_int(value: object, label: str) -> int | None:
    text: str = str(value or "").strip()
    if not text:
        return None
    try:
        parsed: int = int(text)
    except ValueError as error:
        raise ValueError(f"{label} must be an integer.") from error
    if parsed <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return parsed


def _effective_geometry(element: Element, language: str) -> dict[str, float]:
    values: dict[str, float] = {
        "x": float(element.x), "y": float(element.y),
        "width": float(element.width), "height": float(element.height),
        "font_size": float(element.font_size),
    }
    override: ElementLanguageOverride | None = next(
        (item for item in element.language_overrides.all() if item.language == language), None
    )
    if override:
        for field in tuple(values):
            value: float | None = getattr(override, field)
            if value is not None:
                values[field] = float(value)
    return values


def _element_view(
    element: Element,
    component: ComponentDefinition,
    row: ContentRow | None,
    language: str,
    base_language: str,
) -> dict[str, object]:
    geometry: dict[str, float] = _effective_geometry(element, language)
    return {
        "id": element.id,
        "component": component,
        "svg": mark_safe(component.svg),
        "text": row.values.get(language, "") if row else "",
        "content_id": element.content_id,
        "content_note": row.note if row else "",
        "target_frame_id": element.target_frame_id,
        "delay_mode": element.delay_mode,
        "break_long_words": element.break_long_words,
        "fill_color": element.fill_color,
        "border_color": element.border_color,
        "text_color": element.text_color,
        "default_fill": component.fill,
        "default_border": component.border,
        "default_text": component.text,
        "has_color_override": bool(element.fill_color or element.border_color or element.text_color),
        "has_language_override": language != base_language and any(
            item.language == language for item in element.language_overrides.all()
        ),
        **geometry,
    }


def help_page(request: HttpRequest) -> HttpResponse:
    """Show concise in-app explanations without depending on separate guide files."""
    return render(request, "studio/help.html", {
        "page": "help", "project": _active_project(),
    })


def home(request: HttpRequest) -> HttpResponse:
    health = project_health()
    project: ProjectSettings | None = _active_project() if health.ready else None
    database_problem: str = ""
    if health.ready and project is None:
        database_problem = "The project folder exists, but its project settings could not be read."
    return render(request, "studio/home.html", {
        "page": "home", "health": health, "project": project,
        "database_problem": database_problem, "notice": request.GET.get("notice", ""),
    })


def new_project(request: HttpRequest) -> HttpResponse:
    if project_exists():
        return _notice_redirect("studio:home", "A project already exists in /project/.")
    form = NewProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            project: ProjectSettings = create_project(
                name=str(form.cleaned_data["name"]),
                base_language=str(form.cleaned_data["base_language"]),
                extra_languages=list(form.cleaned_data.get("parsed_extra_languages", [])),
            )
        except (OSError, ValueError) as error:
            form.add_error(None, str(error))
        else:
            return _notice_redirect("studio:develop", f"Created {project.name}. Add the first frame when you are ready.")
    return render(request, "studio/new_project.html", {"page": "new-project", "form": form, "project": None})


def develop(request: HttpRequest) -> HttpResponse:
    project: ProjectSettings | None = _active_project()
    if project is None:
        return redirect("studio:home")
    content_error: str = ""
    issues: list[ValidationIssue] = []
    try:
        content: ContentTable = _content_table()
        selected_language: str = _language(content, project, request.GET.get("lang"))
        languages: tuple[str, ...] = content.languages
        issues = validate_project(project, content)
    except (OSError, ValueError) as error:
        content_error = str(error)
        selected_language = project.base_language
        languages = (project.base_language,)
    frames: list[Frame] = list(Frame.objects.all())
    build_folder: str = language_directory(project.slug, selected_language)
    preview_path: str = f"{build_folder}/index.html"
    return render(request, "studio/develop.html", {
        "page": "develop", "project": project, "frames": frames,
        "languages": languages, "selected_language": selected_language,
        "devices": DEVICE_PRESETS, "issues": issues,
        "report": load_build_report(),
        "dist_ready": (settings.DIST_DIR / preview_path).is_file(),
        "dist_stale": dist_is_stale(),
        "preview_url": reverse("studio:preview_file", kwargs={"path": preview_path}),
        "content_error": content_error, "notice": request.GET.get("notice", ""),
    })


@require_POST
def regenerate(request: HttpRequest) -> HttpResponse:
    project: ProjectSettings | None = _active_project()
    if project is None:
        return redirect("studio:home")
    try:
        report = generate_dist(project)
    except (OSError, ValueError) as error:
        return _notice_redirect("studio:develop", f"Generation failed: {error}")
    warnings: int = sum(issue.severity == "warning" for issue in report.issues)
    errors: int = sum(issue.severity == "error" for issue in report.issues)
    return _notice_redirect("studio:develop", f"Generated {len(report.languages)} language build(s): {errors} error(s), {warnings} warning(s).")


def project_config(request: HttpRequest) -> HttpResponse:
    project: ProjectSettings | None = _active_project()
    if project is None:
        return redirect("studio:home")
    form = ProjectSettingsForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        return _notice_redirect("studio:config", "Project settings saved.")
    content_error: str = ""
    try:
        languages: tuple[str, ...] = _content_table().languages
    except (OSError, ValueError) as error:
        content_error = str(error)
        languages = (project.base_language,)
    return render(request, "studio/config.html", {
        "page": "config", "project": project, "form": form,
        "languages": languages, "content_error": content_error,
        "notice": request.GET.get("notice", ""),
    })


@require_POST
def new_frame(request: HttpRequest) -> HttpResponse:
    if _active_project() is None:
        return redirect("studio:home")
    frame: Frame = Frame.objects.create(name=next_frame_name())
    return _notice_redirect("studio:frame_editor", f"Created {frame.name}.", frame_name=frame.name)


def flowchart(request: HttpRequest) -> HttpResponse:
    project: ProjectSettings | None = _active_project()
    if project is None:
        return redirect("studio:home")
    content_error: str = ""
    try:
        content: ContentTable = _content_table()
        language: str = _language(content, project, request.GET.get("lang"))
        content_by_id: dict[int, ContentRow] = content.by_id()
        languages: tuple[str, ...] = content.languages
    except (OSError, ValueError) as error:
        content_error = str(error)
        language = project.base_language
        languages = (project.base_language,)
        content_by_id = {}
    frames: list[Frame] = list(Frame.objects.prefetch_related("elements__target_frame").all())
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    for index, frame in enumerate(frames):
        nodes.append({
            "name": frame.name,
            "x": frame.flow_x if frame.flow_x is not None else 130 + (index % 4) * 260,
            "y": frame.flow_y if frame.flow_y is not None else 110 + (index // 4) * 175,
            "fade_in": frame.fade_in,
            "edit_url": reverse("studio:frame_editor", kwargs={"frame_name": frame.name}),
        })
        for element in frame.elements.all():
            if element.target_frame_id is None:
                continue
            row: ContentRow | None = content_by_id.get(element.content_id) if element.content_id else None
            label: str = row.values.get(language, "") if row else element.component
            edges.append({
                "source": frame.name, "target": element.target_frame.name if element.target_frame else "",
                "element_id": element.id, "label": label[:90],
            })
    return render(request, "studio/flowchart.html", {
        "page": "flowchart", "project": project, "nodes": nodes, "edges": edges,
        "languages": languages, "selected_language": language,
        "content_error": content_error, "notice": request.GET.get("notice", ""),
    })


def frame_editor(request: HttpRequest, frame_name: str) -> HttpResponse:
    project: ProjectSettings | None = _active_project()
    if project is None:
        return redirect("studio:home")
    frame: Frame = get_object_or_404(Frame, name=frame_name)
    materials = list_materials()
    background_form = FrameBackgroundForm(request.POST or None, instance=frame)
    if request.method == "POST" and background_form.is_valid():
        updated: Frame = background_form.save(commit=False)
        valid_materials: set[str] = {item.relative_path for item in materials}
        if updated.background_type == Frame.BackgroundType.IMAGE and updated.background_image not in valid_materials:
            background_form.add_error("background_image", "Choose an image that exists in /project/materials/.")
        else:
            if updated.background_type != Frame.BackgroundType.IMAGE:
                updated.background_image = ""
            updated.save()
            return _notice_redirect("studio:frame_editor", f"Saved {frame.name} background settings.", frame_name=frame.name)

    content_error: str = ""
    try:
        content: ContentTable = _content_table()
        language: str = _language(content, project, request.GET.get("lang"))
        languages: tuple[str, ...] = content.languages
        rows: tuple[ContentRow, ...] = content.rows
        by_id: dict[int, ContentRow] = content.by_id()
    except (OSError, ValueError) as error:
        content_error = str(error)
        language = project.base_language
        languages = (project.base_language,)
        rows, by_id = (), {}

    components: list[ComponentDefinition] = load_components()
    component_lookup: dict[str, ComponentDefinition] = {item.slug: item for item in components}
    element_views: list[dict[str, object]] = []
    for element in frame.elements.prefetch_related("language_overrides", "target_frame").all():
        component: ComponentDefinition | None = component_lookup.get(element.component)
        if component is None:
            continue
        row: ContentRow | None = by_id.get(element.content_id) if element.content_id else None
        element_views.append(_element_view(element, component, row, language, project.base_language))

    background_url: str = ""
    if frame.background_type == Frame.BackgroundType.IMAGE and frame.background_image:
        background_url = reverse("studio:material_file", kwargs={"path": frame.background_image})
    color_file: Path = settings.PROJECT_DIR / "default-colors.css"
    return render(request, "studio/edit_frame.html", {
        "page": "frame-editor", "project": project, "frame": frame,
        "background_form": background_form, "background_url": background_url,
        "components": components, "component_css": mark_safe(component_css()),
        "project_colors_css": mark_safe(color_file.read_text(encoding="utf-8") if color_file.is_file() else ""),
        "elements": element_views, "content_rows": rows,
        "languages": languages, "selected_language": language,
        "frames": Frame.objects.all(), "materials": materials,
        "delay_choices": Element.DelayMode.choices, "content_error": content_error,
        "notice": request.GET.get("notice", ""),
    })


@require_POST
def delete_frame(request: HttpRequest, frame_name: str) -> HttpResponse:
    if _active_project() is None:
        return redirect("studio:home")
    frame: Frame = get_object_or_404(Frame, name=frame_name)
    frame.delete()
    return _notice_redirect("studio:develop", f"Deleted {frame_name}.")


@require_POST
def add_element(request: HttpRequest, frame_name: str) -> HttpResponse:
    project: ProjectSettings | None = _active_project()
    if project is None:
        return redirect("studio:home")
    frame: Frame = get_object_or_404(Frame, name=frame_name)
    component: ComponentDefinition | None = component_map().get(request.POST.get("component", "").strip())
    if component is None:
        return _notice_redirect("studio:frame_editor", "Unknown component.", frame_name=frame.name)
    Element.objects.create(
        frame=frame, component=component.slug,
        x=project.frame_width / 2, y=project.frame_height / 2,
        width=component.default_width, height=component.default_height,
        font_size=component.default_font_size,
    )
    return _notice_redirect("studio:frame_editor", f"Added {component.name}.", frame_name=frame.name)


@require_POST
def save_element(request: HttpRequest, element_id: int) -> HttpResponse:
    project: ProjectSettings | None = _active_project()
    if project is None:
        return redirect("studio:home")
    element: Element = get_object_or_404(Element, pk=element_id)
    language: str = request.POST.get("language", project.base_language)
    try:
        content_table: ContentTable = _content_table()
        if language not in content_table.languages:
            raise ValueError("Unknown language selected.")
        content_id: int | None = _optional_int(request.POST.get("content_id"), "Content ID")
        target_id: int | None = _optional_int(request.POST.get("target_frame_id"), "Target frame")
        x: float = _float(request.POST.get("x"), "X")
        y: float = _float(request.POST.get("y"), "Y")
        width: float = _float(request.POST.get("width"), "Width", 20)
        height: float = _float(request.POST.get("height"), "Height", 20)
        font_size: float = _float(request.POST.get("font_size"), "Font size", 6)
        if content_id is not None and content_id not in content_table.by_id():
            raise ValueError(f"content_id {content_id} does not exist in content.xlsx.")
        if target_id is not None and not Frame.objects.filter(pk=target_id).exists():
            raise ValueError("Target frame does not exist.")
        delay_mode: str = request.POST.get("delay_mode", Element.DelayMode.NONE)
        if delay_mode not in Element.DelayMode.values:
            raise ValueError("Unknown delay behavior.")

        element.content_id = content_id
        element.target_frame_id = target_id
        element.delay_mode = delay_mode
        element.break_long_words = request.POST.get("break_long_words") == "on"
        if request.POST.get("override_colors") == "on":
            element.fill_color = validate_hex(request.POST.get("fill_color", ""))
            element.border_color = validate_hex(request.POST.get("border_color", ""))
            element.text_color = validate_hex(request.POST.get("text_color", ""))
        else:
            element.fill_color = element.border_color = element.text_color = ""

        use_override: bool = language != project.base_language and request.POST.get("use_language_override") == "on"
        if use_override:
            override, _ = ElementLanguageOverride.objects.get_or_create(element=element, language=language)
            override.x, override.y = x, y
            override.width, override.height, override.font_size = width, height, font_size
            override.save()
        elif language != project.base_language:
            ElementLanguageOverride.objects.filter(element=element, language=language).delete()
        else:
            element.x, element.y = x, y
            element.width, element.height, element.font_size = width, height, font_size
        element.save()
    except (ValidationError, ValueError) as error:
        message: str = "; ".join(error.messages) if isinstance(error, ValidationError) else str(error)
        return _notice_redirect("studio:frame_editor", f"Could not save element: {message}", frame_name=element.frame.name)
    url: str = reverse("studio:frame_editor", kwargs={"frame_name": element.frame.name})
    return redirect(f"{url}?lang={quote(language)}&notice={quote('Element saved.')}")


@require_POST
def delete_element(request: HttpRequest, element_id: int) -> HttpResponse:
    if _active_project() is None:
        return redirect("studio:home")
    element: Element = get_object_or_404(Element, pk=element_id)
    frame_name: str = element.frame.name
    element.delete()
    return _notice_redirect("studio:frame_editor", "Element deleted.", frame_name=frame_name)


def results(request: HttpRequest) -> HttpResponse:
    project: ProjectSettings | None = _active_project()
    if project is None:
        return redirect("studio:home")
    return render(request, "studio/results.html", {
        "page": "results", "project": project, "sessions": session_summaries(),
        "notice": request.GET.get("notice", ""),
    })


@require_POST
def import_logs(request: HttpRequest) -> HttpResponse:
    if _active_project() is None:
        return redirect("studio:home")
    uploaded = request.FILES.get("log_file")
    if uploaded is None:
        return _notice_redirect("studio:results", "Choose a .jsonl log file first.")
    try:
        destination: Path = import_jsonl(uploaded.name, uploaded.read())
    except (UnicodeDecodeError, ValueError, OSError) as error:
        return _notice_redirect("studio:results", f"Import failed: {error}")
    return _notice_redirect("studio:results", f"Imported {destination.name}.")


def session_detail(request: HttpRequest, file_name: str) -> HttpResponse:
    project: ProjectSettings | None = _active_project()
    if project is None:
        return redirect("studio:home")
    try:
        path: Path = safe_child(settings.PROJECT_DIR / "logs", file_name)
    except ValueError:
        return HttpResponseNotFound("Log not found.")
    if path.suffix.lower() != ".jsonl" or not path.is_file():
        return HttpResponseNotFound("Log not found.")
    try:
        events: list[dict[str, Any]] = read_events(path)
        parse_error: str = ""
    except ValueError as error:
        events, parse_error = [], str(error)
    return render(request, "studio/session.html", {
        "page": "results", "project": project, "file_name": file_name,
        "events": events, "parse_error": parse_error,
    })


@require_GET
def status_api(request: HttpRequest) -> JsonResponse:
    health = project_health()
    if not health.exists:
        return JsonResponse({"state": "idle", "label": "No project", "detail": "Waiting for /project/."})
    if not health.ready:
        return JsonResponse({"state": "error", "label": "Project incomplete", "detail": "; ".join(health.problems)}, status=500)
    try:
        project: ProjectSettings | None = _active_project()
        if project is None:
            raise ValueError("Project settings row is missing.")
        ProjectSettings.objects.only("id").get(pk=project.pk)
        stale: bool = dist_is_stale()
    except Exception as error:
        return JsonResponse({"state": "error", "label": "Database error", "detail": str(error)}, status=500)
    return JsonResponse({
        "state": "stale" if stale else "ready",
        "label": "Changes need regeneration" if stale else "Database ready",
        "detail": str(settings.PROJECT_DB),
    })


def _json_body(request: HttpRequest) -> dict[str, Any]:
    try:
        value: Any = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Request body must be valid JSON.") from error
    if not isinstance(value, dict):
        raise ValueError("Request body must be a JSON object.")
    return value


@require_POST
def element_position_api(request: HttpRequest, element_id: int) -> JsonResponse:
    project: ProjectSettings | None = _active_project()
    if project is None:
        return JsonResponse({"error": "No active project."}, status=409)
    element: Element = get_object_or_404(Element, pk=element_id)
    try:
        data: dict[str, Any] = _json_body(request)
        x: float = _float(data.get("x"), "X")
        y: float = _float(data.get("y"), "Y")
        language: str = str(data.get("language") or project.base_language)
        if language not in _content_table().languages:
            raise ValueError("Unknown language selected.")
        if language == project.base_language:
            element.x, element.y = x, y
            element.save(update_fields=["x", "y", "updated_at"])
        else:
            override, _ = ElementLanguageOverride.objects.get_or_create(element=element, language=language)
            override.x, override.y = x, y
            override.save(update_fields=["x", "y"])
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse({"ok": True, "x": x, "y": y})


@require_POST
def flow_position_api(request: HttpRequest, frame_name: str) -> JsonResponse:
    if _active_project() is None:
        return JsonResponse({"error": "No active project."}, status=409)
    frame: Frame = get_object_or_404(Frame, name=frame_name)
    try:
        data: dict[str, Any] = _json_body(request)
        x: float = _float(data.get("x"), "X")
        y: float = _float(data.get("y"), "Y")
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    frame.flow_x, frame.flow_y = x, y
    frame.save(update_fields=["flow_x", "flow_y", "updated_at"])
    return JsonResponse({"ok": True, "x": x, "y": y})


@require_POST
def study_log_api(request: HttpRequest) -> JsonResponse:
    if _active_project() is None:
        return JsonResponse({"error": "No active project."}, status=409)
    try:
        event: dict[str, Any] = _json_body(request)
        if not isinstance(event.get("event"), str) or not event["event"]:
            raise ValueError("Log event needs an event name.")
        append_event(event)
    except (OSError, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse({"ok": True})


@ensure_csrf_cookie
def preview_file(request: HttpRequest, path: str) -> HttpResponse:
    try:
        file_path: Path = safe_child(settings.DIST_DIR, path)
    except ValueError:
        return HttpResponseNotFound("Preview file not found.")
    if not file_path.is_file() or file_path.name.startswith("."):
        return HttpResponseNotFound("Preview file not found.")
    response = FileResponse(file_path.open("rb"), content_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
    response["Cache-Control"] = "no-store"
    return response


def material_file(request: HttpRequest, path: str) -> HttpResponse:
    try:
        file_path: Path = safe_child(settings.PROJECT_DIR / "materials", path)
    except ValueError:
        return HttpResponseNotFound("Material not found.")
    if not file_path.is_file():
        return HttpResponseNotFound("Material not found.")
    return FileResponse(file_path.open("rb"), content_type=mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")

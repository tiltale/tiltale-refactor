"""HTTP views for the TilTale studio. Non-HTTP work lives in ``services/``."""

from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
import json
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms import FrameForm, NewProjectForm, ProjectSettingsForm, validate_hex
from .models import Element, ElementLanguageOverride, Frame, ProjectSettings
from .services.components import component_map, load_components
from .services.content import ContentTable, append_content_row, load_content_table
from .services.flow import create_frame, tidy_layout
from .services.generate import dist_is_stale, generate_dist, language_folder, load_build_report, page_path, story_css
from .services.llm import frame_prompt, parse_elements
from .services.project import BRANDING_FILES, create_project, image_size, list_materials, project_health, project_settings, safe_child
from .services.study_logs import append_event, import_jsonl, logs_dir, read_events, session_record, session_summaries
from .services.validate import DEVICE_PRESETS, validate_project

BOX_FIELDS: tuple[tuple[str, str, float | None], ...] = (
    ("x", "X", None), ("y", "Y", None), ("width", "Width", 20), ("height", "Height", 20),
)
GEOMETRY_FIELDS: tuple[tuple[str, str, float | None], ...] = (*BOX_FIELDS, ("font_size", "Font size", 6))
PREVIEW_MISSING: str = (
    '<!doctype html><meta charset="utf-8"><body style="margin:0;display:grid;place-items:center;height:100vh;'
    'background:#e6e8ec;font:15px/1.5 system-ui,sans-serif;color:#677084;text-align:center">'
    '<p>Not built yet.<br>Press <strong>Regenerate</strong> on the Develop page.</p>'
)
STANDARD_LOG_KEYS: frozenset[str] = frozenset({
    "participant_id", "visit_id", "seq", "timestamp", "received_at", "project", "language", "event", "frame",
})


def project_view(view: Callable[..., HttpResponse]) -> Callable[..., HttpResponse]:
    """Pass the active project to ``view``; without one, go home (or 409 for APIs)."""
    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        project: ProjectSettings | None = project_settings()
        if project is None:
            if request.path.startswith("/api/"):
                return JsonResponse({"error": "No active project."}, status=409)
            return redirect("studio:home")
        return view(request, project, *args, **kwargs)
    return wrapper


@dataclass(frozen=True, slots=True)
class Content:
    """content.xlsx plus the language currently selected in the studio."""

    table: ContentTable
    language: str
    error: str = ""

    @property
    def languages(self) -> tuple[str, ...]:
        return self.table.languages

    @property
    def multilingual(self) -> bool:
        return len(self.table.languages) > 1


def _content(request: HttpRequest, project: ProjectSettings) -> Content:
    try:
        table: ContentTable = load_content_table(settings.PROJECT_DIR / "content.xlsx")
    except (OSError, ValueError) as error:
        return Content(ContentTable((project.base_language,), ()), project.base_language, str(error))
    requested: str = request.GET.get("lang") or request.POST.get("language") or ""
    language: str = next(item for item in (requested, project.base_language, table.languages[0]) if item in table.languages)
    return Content(table, language)


def _to(name: str, lang: str = "", **kwargs: Any) -> HttpResponse:
    url: str = reverse(f"studio:{name}", kwargs=kwargs or None)
    return redirect(f"{url}?{urlencode({'lang': lang})}" if lang else url)


def _preview_url(folder: str) -> str:
    return reverse("studio:preview_file", kwargs={"path": page_path(folder)})


def _number(value: object, label: str, minimum: float | None = None) -> float:
    try:
        parsed: float = float(str(value))
    except ValueError:
        raise ValueError(f"{label} must be a number.") from None
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{label} must be at least {minimum:g}.")
    return parsed


def _json_body(request: HttpRequest) -> dict[str, Any]:
    try:
        value: Any = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Request body must be JSON.") from None
    if not isinstance(value, dict):
        raise ValueError("Request body must be a JSON object.")
    return value


def _error_text(error: Exception) -> str:
    return "; ".join(error.messages) if isinstance(error, ValidationError) else str(error)


def _save_geometry(element: Element, language: str, project: ProjectSettings, values: dict[str, float]) -> None:
    """Base-language edits change the element; other languages store only what differs.

    The caller still saves ``element`` itself.
    """
    if language == project.base_language:
        for key, value in values.items():
            setattr(element, key, value)
        return
    override, _ = ElementLanguageOverride.objects.get_or_create(element=element, language=language)
    for key, value in values.items():
        setattr(override, key, None if value == getattr(element, key) else value)
    if all(getattr(override, key) is None for key, _label, _minimum in GEOMETRY_FIELDS):
        override.delete()
    else:
        override.save()


def _cover_box(image: str, project: ProjectSettings) -> dict[str, float]:
    """Where an unmoved background image sits: centered and filling the frame, like CSS ``background-size: cover``."""
    width, height = image_size(image)
    scale: float = max(project.frame_width / width, project.frame_height / height)
    return {"x": project.frame_width / 2, "y": project.frame_height / 2, "width": width * scale, "height": height * scale}


def _target_value(element: Element) -> str:
    if element.ends_story:
        return "end"
    if element.target_language:
        return f"language:{element.target_language}"
    return f"frame:{element.target_frame_id}" if element.target_frame_id else ""


def _apply_target(element: Element, value: str, languages: tuple[str, ...]) -> Frame | None:
    """Set what a click does. Returns the frame when ``value == "new"`` created one."""
    picker: bool = element.frame.is_language_picker
    element.target_frame, element.target_language, element.ends_story = None, "", False
    kind, _, key = value.partition(":")
    if not value:
        return None
    if kind == "new":
        element.target_frame = create_frame(is_picker=picker, linked_from=element.frame)
        return element.target_frame
    if kind == "frame":
        element.target_frame = Frame.objects.filter(pk=int(key), is_language_picker=picker).first()
        if element.target_frame is None:
            raise ValueError("That target frame does not exist (or is of the other kind).")
        return None
    if kind == "language" and picker and key in languages:
        element.target_language = key
        return None
    if kind == "end" and not picker:
        element.ends_story = True
        return None
    raise ValueError("Unknown target.")


def home(request: HttpRequest) -> HttpResponse:
    health = project_health()
    project: ProjectSettings | None = project_settings() if health.ready else None
    return render(request, "studio/home.html", {"health": health, "project": project})


def help_page(request: HttpRequest) -> HttpResponse:
    return render(request, "studio/help.html", {"project": project_settings(), "version": settings.TILTALE_VERSION})


def new_project(request: HttpRequest) -> HttpResponse:
    if project_health().exists:
        messages.info(request, "A project already exists in /project/.")
        return redirect("studio:home")
    form = NewProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            project: ProjectSettings = create_project(
                name=form.cleaned_data["name"],
                base_language=form.cleaned_data["base_language"],
                extra_languages=form.cleaned_data["extra_languages"],
            )
        except Exception as error:  # the folder was rolled back; show the reason
            form.add_error(None, f"Could not create the project: {error}")
        else:
            messages.success(request, f"Created {project.name}. Add the first frame with “+ Frame”.")
            return redirect("studio:develop")
    return render(request, "studio/new_project.html", {"form": form})


@project_view
def develop(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    content: Content = _content(request, project)
    frames: list[Frame] = list(Frame.objects.all())
    has_pickers: bool = content.multilingual and any(frame.is_language_picker for frame in frames)
    picker_selected: bool = has_pickers and request.GET.get("lang") == "picker"
    story_folder: str = language_folder(project, content.language, content.languages)
    shown_folder: str = "" if picker_selected else story_folder
    for frame in frames:
        frame.preview_url = _preview_url("" if frame.is_language_picker else story_folder)  # type: ignore[attr-defined]
    return render(request, "studio/develop.html", {
        "project": project, "content": content, "frames": frames,
        "has_pickers": has_pickers, "picker_selected": picker_selected,
        "devices": DEVICE_PRESETS,
        "issues": [] if content.error else validate_project(project, content.table),
        "preview_url": _preview_url(shown_folder),
        "dist_ready": (settings.DIST_DIR / page_path(shown_folder)).is_file(),
        "dist_stale": dist_is_stale(),
    })


@require_POST
@project_view
def regenerate(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    try:
        report = generate_dist(project)
    except (OSError, ValueError) as error:
        messages.error(request, f"Regenerate failed: {error}")
    else:
        errors: int = sum(issue.severity == "error" for issue in report.issues)
        warnings: int = len(report.issues) - errors
        messages.success(request, f"Regenerated {len(report.builds)} page(s): {errors} error(s), {warnings} warning(s).")
    return _to("develop", lang=request.POST.get("language", ""))


@project_view
def playtest(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    report: dict[str, Any] | None = load_build_report()
    builds: list[dict[str, str]] = [
        {"label": build["label"], "url": _preview_url(build["folder"])} for build in (report or {}).get("builds", [])
    ]
    return render(request, "studio/playtest.html", {
        "project": project, "builds": builds, "dist_stale": dist_is_stale(),
        "log_api": reverse("studio:log_api", kwargs={"file_name": "FILE"}),
        "session_url": reverse("studio:session_detail", kwargs={"file_name": "FILE"}),
    })


@project_view
def project_config(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    form = ProjectSettingsForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Project settings saved. Press Regenerate to apply them to the preview.")
        return redirect("studio:config")
    return render(request, "studio/config.html", {
        "project": project, "form": form, "content": _content(request, project),
    })


@require_POST
@project_view
def new_frame(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    content: Content = _content(request, project)
    picker: bool = request.POST.get("picker") == "1"
    if picker and not content.multilingual:
        messages.error(request, "Language-picker frames need at least two language columns in content.xlsx.")
        return _to("develop", lang=content.language)
    frame: Frame = create_frame(is_picker=picker)
    messages.success(request, f"Created {frame.name}.")
    return _to("frame_editor", lang=content.language, frame_id=frame.id)


def _flow_graph(project: ProjectSettings, content: Content) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Nodes and edges of the flowchart, shared by the Flowchart and Results pages."""
    frames: list[Frame] = list(Frame.objects.prefetch_related("elements"))
    components = component_map()
    rows = content.table.by_id()
    names: dict[int, str] = {frame.id: frame.name for frame in frames}
    story_start: Frame | None = next((frame for frame in frames if not frame.is_language_picker), None)
    picker_start: Frame | None = next((frame for frame in frames if frame.is_language_picker), None)
    documents: set[int] = {frame.id for frame in frames if frame.zoomable}  # readers look and come back
    story_url: str = _preview_url(language_folder(project, content.language, content.languages))
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for frame in frames:
        for element in frame.elements.all():
            if not (element.target_frame_id or element.target_language or element.ends_story):
                continue
            row = rows.get(element.content_id) if element.content_id else None
            text: str = element.text if frame.is_language_picker else (row.values.get(content.language, "") if row else "")
            component = components.get(element.component)
            target: int | None = element.target_frame_id or (story_start.id if element.target_language and story_start else None)
            edges.append({
                "source": frame.id,
                "target": target,
                "target_name": names.get(target, ""),
                "element_id": element.id,
                "component": component.name if component else element.component,
                "text": text[:80],
                "language": element.target_language,
                "end": element.ends_story,
                "document": target in documents,
            })
        nodes.append({
            "id": frame.id, "name": frame.name, "key": frame.key, "x": frame.flow_x, "y": frame.flow_y,
            "fade_in": frame.fade_in, "picker": frame.is_language_picker, "document": frame.zoomable,
            "start": frame in (story_start, picker_start),
            "ends": sum(element.ends_story for element in frame.elements.all()),
            "edit_url": f"{reverse('studio:frame_editor', kwargs={'frame_id': frame.id})}?{urlencode({'lang': content.language})}",
            "preview_url": _preview_url("") if frame.is_language_picker else story_url,
        })
    return nodes, edges


@project_view
def flowchart(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    content: Content = _content(request, project)
    nodes, edges = _flow_graph(project, content)
    return render(request, "studio/flowchart.html", {
        "project": project, "content": content, "nodes": nodes, "edges": edges,
        "selected_frame": request.GET.get("selected", ""),
        "dist_ready": (settings.DIST_DIR / page_path(language_folder(project, content.language, content.languages))).is_file(),
        "dist_stale": dist_is_stale(),
    })


@require_POST
@project_view
def tidy_flowchart(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    tidy_layout()
    messages.success(request, "Flowchart rearranged by distance from the first frame.")
    return _to("flowchart", lang=request.POST.get("language", ""))


@project_view
def frame_editor(request: HttpRequest, project: ProjectSettings, frame_id: int) -> HttpResponse:
    frame: Frame = get_object_or_404(Frame, pk=frame_id)
    content: Content = _content(request, project)
    materials: list[str] = list_materials()
    form = FrameForm(request.POST or None, instance=frame, materials=materials, content_ids=set(content.table.by_id()))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved the settings of {frame.name}.")
        return _to("frame_editor", lang=content.language, frame_id=frame.id)

    language: str = project.base_language if frame.is_language_picker else content.language
    component_list = load_components()
    components = {component.slug: component for component in component_list}
    rows = content.table.by_id()
    elements: list[dict[str, Any]] = []
    for element in frame.elements.prefetch_related("language_overrides"):
        component = components.get(element.component)
        if component is None and not element.image:
            continue  # the dashboard's preflight list reports unknown components
        row = rows.get(element.content_id) if element.content_id else None
        elements.append({
            "element": element,
            "component": component,
            "text": element.text if frame.is_language_picker else (row.values.get(language, "") if row else ""),
            "note": row.note if row else "",
            "geometry": element.geometry(language),
            "has_override": language != project.base_language
            and any(item.language == language for item in element.language_overrides.all()),
            "target": _target_value(element),
        })

    same_kind = Frame.objects.filter(is_language_picker=frame.is_language_picker).exclude(pk=frame.pk)  # never to itself
    target_options: list[tuple[str, str]] = [("", "Nothing yet")]
    target_options += [(f"frame:{item.id}", f"Go to {item.name} ({item.key})") for item in sorted(same_kind, key=lambda item: item.name.lower())]
    if frame.is_language_picker:
        target_options += [(f"language:{item}", f"Open the {item} story") for item in content.languages]
    else:
        target_options.append(("end", "End story (go to the finish redirect URL)"))
    target_options.append(("new", "+ Create a new frame and go there"))

    background: dict[str, Any] | None = None
    if frame.background_type == Frame.BackgroundType.IMAGE and frame.background_image in materials:
        background = {
            "url": reverse("studio:material_file", kwargs={"path": frame.background_image}),
            "box": frame.background_box or _cover_box(frame.background_image, project),
        }
    return render(request, "studio/edit_frame.html", {
        "project": project, "frame": frame, "form": form, "content": content, "language": language,
        "materials": materials, "components": component_list, "project_css": story_css(),
        "background": background, "elements": elements, "target_options": target_options,
        "content_rows": [
            {"id": row.content_id, "excel_row": row.excel_row, "text": row.values.get(language, ""), "note": row.note}
            for row in content.table.rows
        ],
        "delay_choices": Element.DelayMode.choices,
        "incoming": frame.incoming_elements.count(),
        "llm_prompt": "" if frame.is_language_picker else frame_prompt(project, frame, content.table),
    })


@require_POST
@project_view
def delete_frame(request: HttpRequest, project: ProjectSettings, frame_id: int) -> HttpResponse:
    frame: Frame = get_object_or_404(Frame, pk=frame_id)
    frame.delete()
    messages.success(request, f"Deleted {frame.name}.")
    return _to("flowchart", lang=request.POST.get("language", ""))


@require_POST
@project_view
def add_element(request: HttpRequest, project: ProjectSettings, frame_id: int) -> HttpResponse:
    frame: Frame = get_object_or_404(Frame, pk=frame_id)
    component = component_map().get(request.POST.get("component", ""))
    lang: str = request.POST.get("language", "")
    if component is None:
        messages.error(request, "Unknown component.")
        return _to("frame_editor", lang=lang, frame_id=frame.id)
    offset: float = frame.elements.count() % 5 * 40.0  # new elements do not stack exactly
    Element.objects.create(
        frame=frame, component=component.slug,
        x=project.frame_width / 2 + offset, y=project.frame_height / 2 + offset,
        width=component.default_width, height=component.default_height, font_size=component.default_font_size,
    )
    messages.success(request, f"Added a {component.name}. Drag it into place; right-click it for settings.")
    return _to("frame_editor", lang=lang, frame_id=frame.id)


@require_POST
@project_view
def add_image(request: HttpRequest, project: ProjectSettings, frame_id: int) -> HttpResponse:
    frame: Frame = get_object_or_404(Frame, pk=frame_id)
    image: str = request.POST.get("image", "")
    back: HttpResponse = _to("frame_editor", lang=request.POST.get("language", ""), frame_id=frame.id)
    if image not in list_materials():
        messages.error(request, "Choose an image that exists in /project/materials/.")
        return back
    width, height = image_size(image)
    scale: float = min(1.0, project.frame_width / 2 / width, project.frame_height / 2 / height)  # at most half the frame
    offset: float = frame.elements.count() % 5 * 40.0
    Element.objects.create(
        frame=frame, image=image, x=project.frame_width / 2 + offset, y=project.frame_height / 2 + offset,
        width=width * scale, height=height * scale,
    )
    messages.success(request, f"Added {image}. Drag it into place; drag its corner to resize it.")
    return back


@require_POST
@project_view
def save_element(request: HttpRequest, project: ProjectSettings, element_id: int) -> HttpResponse:
    element: Element = get_object_or_404(Element.objects.select_related("frame"), pk=element_id)
    content: Content = _content(request, project)
    language: str = project.base_language if element.frame.is_language_picker else content.language
    back: HttpResponse = _to("frame_editor", lang=content.language, frame_id=element.frame_id)
    data = request.POST

    if "reset_language" in data:
        ElementLanguageOverride.objects.filter(element=element, language=language).delete()
        messages.success(request, f"Element #{element.id} now uses the {project.base_language} layout in {language}.")
        return back
    try:
        geometry: dict[str, float] = {key: _number(data.get(key), label, low) for key, label, low in GEOMETRY_FIELDS}
        if data.get("delay_mode") not in Element.DelayMode.values:
            raise ValueError("Unknown delay behavior.")
        override_colors: bool = data.get("override_colors") == "on"
        colors = {name: validate_hex(data.get(name, "")) if override_colors else "" for name in ("fill_color", "border_color", "text_color")}
        if element.frame.is_language_picker:
            element.text = data.get("text", "").strip()
        else:
            raw_id: str = data.get("content_id", "").strip()
            if raw_id and not raw_id.isdigit():
                raise ValueError("content_id must be a whole number.")
            element.content_id = int(raw_id) if raw_id else None
            if element.content_id is not None and element.content_id not in content.table.by_id():
                raise ValueError(f"content_id {element.content_id} is not in content.xlsx.")
        created: Frame | None = _apply_target(element, data.get("target", ""), content.languages)
    except (ValidationError, ValueError) as error:
        messages.error(request, f"Element not saved: {_error_text(error)}")
        return back

    element.delay_mode = data["delay_mode"]
    element.break_long_words = data.get("break_long_words") == "on"
    for name, value in colors.items():
        setattr(element, name, value)
    _save_geometry(element, language, project, geometry)
    element.save()
    messages.success(request, f"Saved element #{element.id}." + (f" Created {created.name} as its target." if created else ""))
    return back


@require_POST
@project_view
def duplicate_element(request: HttpRequest, project: ProjectSettings, element_id: int) -> HttpResponse:
    element: Element = get_object_or_404(Element.objects.select_related("frame"), pk=element_id)
    overrides: list[ElementLanguageOverride] = list(element.language_overrides.all())
    element.pk, element._state.adding = None, True
    element.x, element.y = element.x + 40, element.y + 40
    element.save()
    for override in overrides:
        override.pk, override._state.adding, override.element = None, True, element
        override.save()
    messages.success(request, f"Duplicated as element #{element.id}.")
    return _to("frame_editor", lang=request.POST.get("language", ""), frame_id=element.frame_id)


@require_POST
@project_view
def move_element(request: HttpRequest, project: ProjectSettings, element_id: int) -> HttpResponse:
    """Swap an element with the one in front of it ("forward") or behind it ("backward")."""
    element: Element = get_object_or_404(Element.objects.select_related("frame"), pk=element_id)
    siblings: list[Element] = list(element.frame.elements.all())  # back to front
    index: int = siblings.index(element)
    other: int = index + (1 if request.POST.get("direction") == "forward" else -1)
    if 0 <= other < len(siblings):
        for position, item in enumerate(siblings):
            item.order = position
        siblings[index].order, siblings[other].order = other, index
        Element.objects.bulk_update(siblings, ["order"])
    return _to("frame_editor", lang=request.POST.get("language", ""), frame_id=element.frame_id)


@require_POST
@project_view
def add_content_for_element(request: HttpRequest, project: ProjectSettings, element_id: int) -> HttpResponse:
    element: Element = get_object_or_404(Element.objects.select_related("frame"), pk=element_id)
    values: dict[str, str] = {
        key.removeprefix("text."): value for key, value in request.POST.items() if key.startswith("text.")
    }
    try:
        row = append_content_row(settings.PROJECT_DIR / "content.xlsx", request.POST.get("note", ""), values)
    except (OSError, ValueError) as error:
        messages.error(request, f"Content not added: {error}")
    else:
        element.content_id = row.content_id
        element.save(update_fields=["content_id"])
        messages.success(request, f"Added content #{row.content_id} to content.xlsx and selected it.")
    return _to("frame_editor", lang=request.POST.get("language", ""), frame_id=element.frame_id)


@require_POST
@project_view
def delete_element(request: HttpRequest, project: ProjectSettings, element_id: int) -> HttpResponse:
    element: Element = get_object_or_404(Element.objects.select_related("frame"), pk=element_id)
    element.delete()
    messages.success(request, "Element deleted.")
    return _to("frame_editor", lang=request.POST.get("language", ""), frame_id=element.frame_id)


@require_POST
@project_view
def import_elements(request: HttpRequest, project: ProjectSettings, frame_id: int) -> HttpResponse:
    frame: Frame = get_object_or_404(Frame, pk=frame_id, is_language_picker=False)
    content: Content = _content(request, project)
    targets: dict[str, int] = {item.key: item.id for item in Frame.objects.filter(is_language_picker=False)}
    back: HttpResponse = _to("frame_editor", lang=content.language, frame_id=frame.id)
    try:
        values = parse_elements(request.POST.get("answer", ""), component_map(), set(content.table.by_id()), targets)
    except ValueError as error:
        messages.error(request, f"Nothing added. {error}")
        return back
    Element.objects.bulk_create([Element(frame=frame, **item) for item in values])
    messages.success(request, f"Added {len(values)} element(s). Check their positions and texts.")
    return back


@project_view
def results(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    content: Content = _content(request, project)
    nodes, edges = _flow_graph(project, content)
    names: dict[str, str] = {node["key"]: node["name"] for node in nodes}
    labels: dict[int, str] = {
        edge["element_id"]: f"{edge['component']} ({edge['text']})" if edge["text"] else edge["component"] for edge in edges
    }
    return render(request, "studio/results.html", {
        "project": project, "content": content, "nodes": nodes, "edges": edges, "readonly": True,
        "sessions": [session_record(summary, names, labels) for summary in session_summaries()],
        "dist_ready": (settings.DIST_DIR / page_path(language_folder(project, content.language, content.languages))).is_file(),
    })


@require_POST
@project_view
def import_logs(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    files = request.FILES.getlist("log_files")
    if not files:
        messages.error(request, "Choose one or more .jsonl files first.")
    for uploaded in files:
        try:
            destination: Path = import_jsonl(uploaded.name, uploaded.read())
        except (OSError, ValueError) as error:
            messages.error(request, f"Not imported: {error}")
        else:
            messages.success(request, f"Imported {destination.name}.")
    return redirect("studio:results")


def _log_path(file_name: str) -> Path:
    try:
        path: Path = safe_child(logs_dir(), file_name)
    except ValueError:
        raise Http404("Log not found.") from None
    if path.suffix != ".jsonl" or not path.is_file():
        raise Http404("Log not found.")
    return path


@project_view
def session_detail(request: HttpRequest, project: ProjectSettings, file_name: str) -> HttpResponse:
    try:
        events, error = read_events(_log_path(file_name)), ""
    except ValueError as problem:
        events, error = [], str(problem)
    names: dict[str, str] = {frame.key: frame.name for frame in Frame.objects.all()}
    rows: list[dict[str, Any]] = [{
        **{key: event.get(key, "") for key in ("seq", "timestamp", "event", "frame")},
        "frame_name": names.get(event.get("frame", ""), ""),
        "details": json.dumps({k: v for k, v in event.items() if k not in STANDARD_LOG_KEYS}, ensure_ascii=False),
    } for event in events]
    first: dict[str, Any] = events[0] if events else {}
    return render(request, "studio/session.html", {
        "project": project, "file_name": file_name, "rows": rows, "error": error,
        "participant_id": first.get("participant_id", ""), "visit_id": first.get("visit_id", ""),
    })


def status_context(request: HttpRequest) -> dict[str, dict[str, str]]:
    """Context processor for the status bar in base.html (see TEMPLATES in settings.py)."""
    health = project_health()
    if not health.exists:
        return {"status": {"state": "idle", "label": "No project", "detail": "Create one, or copy a project folder into /project/."}}
    if health.problems:
        return {"status": {"state": "error", "label": "Project incomplete", "detail": "; ".join(health.problems)}}
    if project_settings() is None:
        return {"status": {"state": "error", "label": "Database error", "detail": "Could not read project/project.sqlite3."}}
    if dist_is_stale():
        return {"status": {"state": "stale", "label": "Saved; not in the preview yet", "detail": "Press Regenerate."}}
    return {"status": {"state": "ready", "label": "All changes saved", "detail": str(settings.PROJECT_DB)}}


@require_POST
@project_view
def element_position_api(request: HttpRequest, project: ProjectSettings, element_id: int) -> JsonResponse:
    element: Element = get_object_or_404(Element.objects.select_related("frame"), pk=element_id)
    try:
        data: dict[str, Any] = _json_body(request)
        values: dict[str, float] = {key: _number(data.get(key), label, low) for key, label, low in BOX_FIELDS}
        tail: dict[str, float] = {key: _number(data.get(key), key) for key in ("tail_x", "tail_y") if "tail_x" in data}
        language: str = str(data.get("language") or project.base_language)
        if element.frame.is_language_picker:
            language = project.base_language
        elif language not in load_content_table(settings.PROJECT_DIR / "content.xlsx").languages:
            raise ValueError("Unknown language.")
    except (OSError, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=400)
    _save_geometry(element, language, project, values)
    for key, value in tail.items():  # a dragged bubble tail; the same in every language
        setattr(element, key, value)
    element.save()
    return JsonResponse({"ok": True})


@require_POST
@project_view
def background_box_api(request: HttpRequest, project: ProjectSettings, frame_id: int) -> JsonResponse:
    frame: Frame = get_object_or_404(Frame, pk=frame_id)
    try:
        data: dict[str, Any] = _json_body(request)
        box: dict[str, float] = {key: _number(data.get(key), label, low) for key, label, low in BOX_FIELDS}
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    for key, value in box.items():
        setattr(frame, f"background_{key}", value)
    frame.save(update_fields=[f"background_{key}" for key in box])
    return JsonResponse({"ok": True})


@require_POST
@project_view
def flow_positions_api(request: HttpRequest, project: ProjectSettings) -> JsonResponse:
    """Save flowchart positions for one or more frames: ``{"positions": [{id, x, y}, ...]}``."""
    try:
        positions: dict[int, tuple[float, float]] = {
            int(item["id"]): (_number(item["x"], "X"), _number(item["y"], "Y"))
            for item in _json_body(request).get("positions", [])
        }
    except (KeyError, TypeError, ValueError) as error:
        return JsonResponse({"error": f"Invalid positions: {error}"}, status=400)
    frames: list[Frame] = list(Frame.objects.filter(pk__in=positions))
    for frame in frames:
        frame.flow_x, frame.flow_y = positions[frame.pk]
    Frame.objects.bulk_update(frames, ["flow_x", "flow_y"])
    return JsonResponse({"ok": True, "saved": len(frames)})


@require_GET
@project_view
def log_api(request: HttpRequest, project: ProjectSettings, file_name: str) -> JsonResponse:
    try:
        return JsonResponse({"events": read_events(_log_path(file_name))})
    except (Http404, ValueError) as error:
        return JsonResponse({"events": [], "error": str(error)}, status=404)


@csrf_exempt
@require_POST
def preview_log(request: HttpRequest) -> HttpResponse:
    """Local stand-in for dist/log.php: preview events go to /project/logs/."""
    if project_settings() is None:
        return JsonResponse({"error": "No active project."}, status=409)
    try:
        append_event(_json_body(request))
    except (OSError, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=400)
    return HttpResponse(status=204)


def _file_response(root: Path, path: str) -> FileResponse:
    try:
        file_path: Path = safe_child(root, path)
    except ValueError:
        raise Http404("File not found.") from None
    if not file_path.is_file() or file_path.name.startswith("."):
        raise Http404("File not found.")
    content_type: str = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    response = FileResponse(file_path.open("rb"), content_type=content_type)
    response["Cache-Control"] = "no-store"
    return response


def preview_file(request: HttpRequest, path: str) -> HttpResponse:
    try:
        return _file_response(settings.DIST_DIR, path)
    except Http404:
        return HttpResponse(PREVIEW_MISSING, status=404)


def material_file(request: HttpRequest, path: str) -> FileResponse:
    return _file_response(settings.PROJECT_DIR / "materials", path)


def branding(request: HttpRequest, name: str) -> FileResponse:
    """The studio's own TilTale logo and favicon; a project's override is for its story only."""
    if name not in BRANDING_FILES:  # BRANDING_DIR is the repository root: serve nothing else from it
        raise Http404("File not found.")
    return _file_response(settings.BRANDING_DIR, name)
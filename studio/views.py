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
from django.db.models import ProtectedError
from django.utils import timezone
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms import FrameForm, NewProjectForm, ProjectSettingsForm, validate_hex
from .models import Element, ElementLanguageOverride, Frame, ProjectSettings, Rule, Variable
from .services.components import component_map, load_components
from .services.content import ContentTable, append_content_row, load_content_table, update_content_row
from .services.flow import create_frame, tidy_layout
from .services.frame_types import load_frame_types
from .services.generate import dist_is_stale, generate_dist, language_folder, load_build_report, page_path, story_css
from .services.llm import frame_prompt, parse_elements
from .services.project import BRANDING_FILES, create_project, image_size, list_materials, project_health, project_settings, safe_child
from .services.log_keys import LockedLog, fingerprint, generate_key_pair, load_private_key, unlock, unlocked
from .services.study_logs import append_event, import_jsonl, logs_dir, read_events, session_record, session_summaries
from .services.validate import DEVICE_PRESETS, validate_project
from .services.variables import COMPARATORS, OPERATIONS, check_name, check_value, parse_value, rule_label

BOX_FIELDS: tuple[tuple[str, str, float | None], ...] = (
    ("x", "X", None), ("y", "Y", None), ("width", "Width", 20), ("height", "Height", 20),
)
GEOMETRY_FIELDS: tuple[tuple[str, str, float | None], ...] = (*BOX_FIELDS, ("font_size", "Font size", 6))
PREVIEW_MISSING: str = (
    '<!doctype html><meta charset="utf-8"><body style="margin:0;display:grid;place-items:center;height:100vh;'
    'background:#e6e8ec;font:15px/1.5 system-ui,sans-serif;color:#677084;text-align:center">'
    '<p>Not built yet.<br>Press <strong>Regenerate</strong> on the Develop page.</p>'
)
CANVAS_KINDS: tuple[str, ...] = (Frame.Kind.FRAME, Frame.Kind.MINIGAME)  # story frames that show elements (and scoreboards)
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
        # A freshly generated log key must be saved before anything else happens (see ETHICS.md).
        if project.log_key_pending and view.__name__ not in KEY_VIEWS and not request.path.startswith("/api/"):
            return redirect("studio:log_key")
        return view(request, project, *args, **kwargs)
    return wrapper


KEY_VIEWS: frozenset[str] = frozenset({"log_key", "download_log_key", "confirm_log_key"})
KEY_COOKIE: str = "tiltale_log_key"


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
    if element.restarts_story:
        return "restart"
    if element.target_language:
        return f"language:{element.target_language}"
    return f"frame:{element.target_frame_id}" if element.target_frame_id else ""


def _target_frame(value: str, source: Frame) -> Frame | None:
    """The frame behind ``frame:<id>``, a new one for ``new``, or ``None`` for an empty value.

    Picker frames link to picker frames; story frames link to any other kind of story frame.
    """
    kind, _, key = value.partition(":")
    picker: bool = source.is_language_picker
    if kind == "new":
        return create_frame(Frame.Kind.PICKER if picker else Frame.Kind.FRAME, linked_from=source)
    if kind != "frame":
        return None
    same_page = Frame.objects.filter(kind=Frame.Kind.PICKER) if picker else Frame.objects.exclude(kind=Frame.Kind.PICKER)
    target: Frame | None = same_page.filter(pk=int(key)).first()
    if target is None:
        raise ValueError("That target frame does not exist (or belongs to the other page).")
    return target


def _apply_target(element: Element, value: str, languages: tuple[str, ...]) -> Frame | None:
    """Set what a click does. Returns the frame when ``value == "new"`` created one."""
    picker: bool = element.frame.is_language_picker
    element.target_frame, element.target_language, element.ends_story, element.restarts_story = None, "", False, False
    kind, _, key = value.partition(":")
    if not value:
        return None
    if kind in ("new", "frame"):
        element.target_frame = _target_frame(value, element.frame)
        return element.target_frame if kind == "new" else None
    if kind == "language" and picker and key in languages:
        element.target_language = key
        return None
    if kind in ("end", "restart") and not picker:
        element.ends_story, element.restarts_story = kind == "end", kind == "restart"
        return None
    raise ValueError("Unknown target.")


def _apply_update(element: Element, data: Any) -> None:
    """Set which global variable a click changes (``update_variable`` empty: none)."""
    raw_id: str = data.get("update_variable", "")
    element.update_variable, element.update_operation, element.update_value = None, "set", ""
    if not raw_id:
        return
    variable: Variable | None = Variable.objects.filter(pk=int(raw_id)).first()
    if variable is None:
        raise ValueError("That global variable does not exist anymore.")
    operation: str = data.get("update_operation", "set")
    if operation not in OPERATIONS:
        raise ValueError("Unknown variable operation.")
    check_value(variable.kind, data.get("update_value", ""), operation)
    element.update_variable, element.update_operation, element.update_value = variable, operation, data.get("update_value", "").strip()


def _back_to_frame(request: HttpRequest, element: Element) -> HttpResponse:
    """The frame editor the element was edited from; a scoreboard on every frame has no frame of its own."""
    frame_id: int = int(request.POST.get("frame") or element.frame_id)
    return _to("frame_editor", lang=request.POST.get("language", ""), frame_id=frame_id)


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
        "project": project, "content": content, "frames": frames, "frame_types": load_frame_types().values(),
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
    story_frames: list[Frame] = list(Frame.objects.filter(kind__in=CANVAS_KINDS))  # where a scoreboard can appear
    components = component_map()
    scoreboards: list[dict[str, Any]] = [{
        "element": element, "component": components.get(element.component),
        "hidden": set(element.hidden_on.values_list("id", flat=True)),
    } for element in Element.objects.filter(frame=None).prefetch_related("hidden_on")]
    return render(request, "studio/config.html", {
        "project": project, "form": form, "content": _content(request, project),
        "variables": [{"variable": variable, "uses": variable.updates.count() + variable.rules.count()} for variable in Variable.objects.all()],
        "scoreboards": scoreboards, "scoreboard_components": [component for component in components.values() if component.scoreboard],
        "story_frames": story_frames, "tab": request.GET.get("tab", "basic"),
        "fingerprint": fingerprint(project.log_public_key) if project.logs_protected else "",
    })


def _advanced() -> HttpResponse:
    return redirect(f"{reverse('studio:config')}?tab=advanced")


# ----------------------------------------------------------------- protecting logs (ETHICS.md)
@require_POST
@project_view
def generate_log_key(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    """Once per project: the public key goes into the settings and /dist/, the private key is handed out next."""
    if project.logs_protected:
        messages.error(request, "This project already has a key; it cannot be replaced.")
        return _advanced()
    project.log_key_pending, project.log_public_key = generate_key_pair()
    project.log_key_created = timezone.now()
    project.save()
    return redirect("studio:log_key")


@project_view
def log_key(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    if not project.log_key_pending:
        return _advanced()
    return render(request, "studio/log_key.html", {
        "project": project, "fingerprint": fingerprint(project.log_public_key), "file_name": _key_file_name(project),
    })


def _key_file_name(project: ProjectSettings) -> str:
    return f"{project.slug}-log-key.pem"


@require_GET
@project_view
def download_log_key(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    if not project.log_key_pending:
        raise Http404("No key is waiting to be saved.")
    response = HttpResponse(project.log_key_pending, content_type="application/x-pem-file")
    response["Content-Disposition"] = f'attachment; filename="{_key_file_name(project)}"'
    return response


@require_POST
@project_view
def confirm_log_key(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    """Forget the private key: from now on only the downloaded file can read the logs."""
    if request.POST.get("saved") != "yes":
        messages.error(request, "Tick the box once the key file is safely stored.")
        return redirect("studio:log_key")
    project.log_key_pending = ""
    project.save()
    messages.success(request, "Logs are now protected. Press Regenerate so /dist/ carries the public key; keep the key file to read Results.")
    return _advanced()


def _log_key(request: HttpRequest, project: ProjectSettings) -> Any:
    """The unlocked private key for this browser session, or ``None`` (also when the project has no key)."""
    return unlocked(request.COOKIES.get(KEY_COOKIE)) if project.logs_protected else None


def _locked(request: HttpRequest, project: ProjectSettings) -> bool:
    return project.logs_protected and _log_key(request, project) is None


@require_POST
@project_view
def unlock_results(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    """Check the uploaded key file against the project's public key and remember it for this browser session."""
    uploaded = request.FILES.get("key_file")
    try:
        if uploaded is None:
            raise ValueError("Choose the key file first.")
        private = load_private_key(uploaded.read(8192), project.log_public_key)
    except ValueError as error:
        messages.error(request, str(error))
        return redirect("studio:results")
    response = redirect("studio:results")
    response.set_cookie(KEY_COOKIE, unlock(private), httponly=True, samesite="Lax")  # gone when the browser closes
    return response


@require_POST
@project_view
def save_variables(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    """Rename or re-initialize existing variables (``name.<id>``/``initial.<id>``) and add ``name.new``."""
    data = request.POST
    try:
        for variable in Variable.objects.all():
            variable.name = check_name(data.get(f"name.{variable.id}", variable.name))
            variable.initial_value = data.get(f"initial.{variable.id}", variable.initial_value).strip()
            if not variable.initial_value:
                raise ValueError(f"{variable.name} needs an initial value.")
            for element in variable.updates.all():  # a changed type must still fit every update and rule that uses it
                check_value(variable.kind, element.update_value, element.update_operation)
            for rule in variable.rules.all():
                check_value(variable.kind, rule.value, rule.comparator)
            variable.save()
        if data.get("name.new", "").strip():
            initial: str = data.get("initial.new", "").strip()
            if not initial:
                raise ValueError("Give the new variable an initial value (e.g. 0 or \"start\").")
            Variable.objects.create(name=check_name(data["name.new"]), initial_value=initial)
    except ValueError as error:
        messages.error(request, f"Variables not saved: {error}")
    else:
        messages.success(request, "Global variables saved. Press Regenerate to apply them to the preview.")
    return _advanced()


@require_POST
@project_view
def delete_variable(request: HttpRequest, project: ProjectSettings, variable_id: int) -> HttpResponse:
    variable: Variable = get_object_or_404(Variable, pk=variable_id)
    try:
        variable.delete()
    except ProtectedError:
        messages.error(request, f"{variable.name} is still used by an element or a validation rule. Remove those uses first.")
    else:
        messages.success(request, f"Deleted the variable {variable.name}.")
    return _advanced()


@require_POST
@project_view
def add_scoreboard(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    component = component_map().get(request.POST.get("component", ""))
    if component is None or not component.scoreboard:
        messages.error(request, "Choose a scoreboard component.")
        return _advanced()
    element = Element.objects.create(
        frame=None, component=component.slug,
        x=project.frame_width - component.default_width / 2 - 40, y=component.default_height / 2 + 40,
        width=component.default_width, height=component.default_height, font_size=component.default_font_size,
    )
    messages.success(request, f"Added a {component.name} (#{element.id}) to every frame. Open any frame to move it and pick its text.")
    return _advanced()


@require_POST
@project_view
def save_scoreboard_frames(request: HttpRequest, project: ProjectSettings, element_id: int) -> HttpResponse:
    """The frames ticked under a scoreboard show it; every other story frame hides it."""
    element: Element = get_object_or_404(Element, pk=element_id, frame=None)
    shown: set[int] = {int(value) for value in request.POST.getlist("shown") if value.isdigit()}
    element.hidden_on.set(Frame.objects.filter(kind__in=CANVAS_KINDS).exclude(pk__in=shown))
    messages.success(request, f"Scoreboard #{element.id} is now hidden on {element.hidden_on.count()} frame(s).")
    return _advanced()


@require_POST
@project_view
def new_frame(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    content: Content = _content(request, project)
    kind: str = request.POST.get("kind", Frame.Kind.FRAME)
    if kind not in Frame.Kind.values:
        messages.error(request, "Unknown frame type.")
        return _to("develop", lang=content.language)
    if kind == Frame.Kind.PICKER and not content.multilingual:
        messages.error(request, "Picker frames need at least two language columns in content.xlsx.")
        return _to("develop", lang=content.language)
    frame: Frame = create_frame(kind)
    messages.success(request, f"Created {frame.name}.")
    return _to("frame_editor", lang=content.language, frame_id=frame.id)


def _flow_graph(project: ProjectSettings, content: Content) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Nodes and edges of the flowchart, shared by the Flowchart and Results pages.

    An edge's ``element_id`` (an element's id, or ``rule-7`` for a validation rule) is also what the
    story logs, so Results can count how many visits took it.
    """
    frames: list[Frame] = list(Frame.objects.prefetch_related("elements", "rules__variable"))
    components = component_map()
    rows = content.table.by_id()
    names: dict[int, str] = {frame.id: frame.name for frame in frames}
    story_start: Frame | None = next((frame for frame in frames if not frame.is_language_picker), None)
    picker_start: Frame | None = next((frame for frame in frames if frame.is_language_picker), None)
    documents: set[int] = {frame.id for frame in frames if frame.is_document}  # readers look and come back
    story_url: str = _preview_url(language_folder(project, content.language, content.languages))
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for frame in frames:
        for element in frame.elements.all():
            if not element.leads_somewhere:
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
                "restart": element.restarts_story,
                "rule": False,
                "document": target in documents,
            })
        for rule in frame.rules.all():
            edges.append({
                "source": frame.id, "target": rule.target_frame_id, "target_name": names.get(rule.target_frame_id, ""),
                "element_id": rule.key, "component": "Rule",
                "text": rule_label(rule.variable.name if rule.variable else None, rule.comparator, rule.value),
                "language": "", "end": False, "restart": False, "rule": True, "document": rule.target_frame_id in documents,
            })
        nodes.append({
            "id": frame.id, "name": frame.name, "key": frame.key, "x": frame.flow_x, "y": frame.flow_y, "kind": frame.kind,
            "fade_in": frame.fade_in, "fade_from_black": frame.fade_from_black, "picker": frame.is_language_picker, "document": frame.is_document,
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
        "project": project, "content": content, "nodes": nodes, "edges": edges, "frame_types": load_frame_types().values(),
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
    shown = Element.objects.filter(frame=frame)
    if frame.has_canvas and not frame.is_language_picker:  # scoreboards from Settings → Advanced, unless hidden here
        shown |= Element.objects.filter(frame=None).exclude(hidden_on=frame)
    for element in shown.prefetch_related("language_overrides"):
        component = components.get(element.component)
        if component is None and not element.image:
            continue  # the dashboard's preflight list reports unknown components
        row = rows.get(element.content_id) if element.content_id else None
        elements.append({
            "element": element,
            "component": component,
            "text": element.text if frame.is_language_picker else (row.values.get(language, "") if row else ""),
            "row": row,
            "texts": [(item, row.values.get(item, "")) for item in content.languages] if row else [],
            "geometry": element.geometry(language),
            "has_override": language != project.base_language
            and any(item.language == language for item in element.language_overrides.all()),
            "target": _target_value(element),
        })

    same_page = Frame.objects.filter(kind=Frame.Kind.PICKER) if frame.is_language_picker else Frame.objects.exclude(kind=Frame.Kind.PICKER)
    frame_options: list[tuple[str, str]] = [
        (f"frame:{item.id}", f"Go to {item.name} ({item.key})") for item in sorted(same_page.exclude(pk=frame.pk), key=lambda item: item.name.lower())
    ]  # never to itself
    target_options: list[tuple[str, str]] = [("", "Nothing yet"), *frame_options]
    if frame.is_language_picker:
        target_options += [(f"language:{item}", f"Open the {item} story") for item in content.languages]
    else:
        target_options.append(("end", "End story (go to the finish redirect URL)"))
        target_options.append(("restart", "Restart the story from its first frame"))
    target_options.append(("new", "+ Create a new frame and go there"))

    background: dict[str, Any] | None = None
    if frame.background_type == Frame.BackgroundType.IMAGE and frame.background_image in materials:
        background = {
            "url": reverse("studio:material_file", kwargs={"path": frame.background_image}),
            "box": frame.background_box or _cover_box(frame.background_image, project),
        }
    rules: list[Rule] = list(frame.rules.select_related("variable", "target_frame"))
    return render(request, "studio/edit_frame.html", {
        "project": project, "frame": frame, "frame_type": load_frame_types()[frame.kind], "form": form, "content": content,
        "language": language, "materials": materials, "components": component_list, "project_css": story_css(),
        "background": background, "elements": elements, "target_options": target_options,
        "rule_targets": [("", "Nothing yet"), *frame_options, ("new", "+ Create a new frame and go there")],
        "conditions": [rule for rule in rules if rule.variable_id], "otherwise": next((rule for rule in rules if not rule.variable_id), None),
        "variables": list(Variable.objects.all()), "comparators": COMPARATORS.items(), "operations": OPERATIONS.items(),
        "content_rows": [
            {"id": row.content_id, "excel_row": row.excel_row, "text": row.values.get(language, ""), "note": row.note}
            for row in content.table.rows
        ],
        "delay_choices": Element.DelayMode.choices,
        "incoming": frame.incoming_elements.count() + frame.incoming_rules.count(),
        "llm_prompt": frame_prompt(project, frame, content.table) if frame.has_canvas and not frame.is_language_picker else "",
    })


def _rule_rows(data: Any) -> list[dict[str, str]]:
    """The rule rows of the validation-point form: ``rule.<n>.<field>`` for n = 0, 1, … then ``else.target``."""
    rows: list[dict[str, str]] = []
    number: int = 0
    while f"rule.{number}.variable" in data:
        rows.append({field: data.get(f"rule.{number}.{field}", "").strip() for field in ("id", "variable", "comparator", "value", "target")})
        number += 1
    rows.append({"id": data.get("else.id", ""), "variable": "", "comparator": "==", "value": "", "target": data.get("else.target", "")})
    return rows


@require_POST
@project_view
def save_rules(request: HttpRequest, project: ProjectSettings, frame_id: int) -> HttpResponse:
    """Replace the rules of a validation point; rules keep their id (and so their log history) when re-saved."""
    frame: Frame = get_object_or_404(Frame, pk=frame_id, kind=Frame.Kind.VALIDATION)
    back: HttpResponse = _to("frame_editor", lang=request.POST.get("language", ""), frame_id=frame.id)
    existing: dict[int, Rule] = {rule.id: rule for rule in frame.rules.all()}
    variables: dict[int, Variable] = {variable.id: variable for variable in Variable.objects.all()}
    kept: list[Rule] = []
    try:
        for order, row in enumerate(_rule_rows(request.POST), start=1):
            rule: Rule = (existing.get(int(row["id"])) if row["id"].isdigit() else None) or Rule(frame=frame)
            rule.variable = variables.get(int(row["variable"])) if row["variable"] else None
            if row["variable"] and rule.variable is None:
                raise ValueError(f"Rule {order}: that global variable does not exist anymore.")
            if rule.variable is not None:
                if row["comparator"] not in COMPARATORS:
                    raise ValueError(f"Rule {order}: unknown comparison.")
                check_value(rule.variable.kind, row["value"], row["comparator"])
            rule.comparator, rule.value, rule.order = row["comparator"], row["value"], order
            rule.target_frame = _target_frame(row["target"], frame)
            kept.append(rule)
    except ValueError as error:
        messages.error(request, f"Rules not saved: {error}")
        return back
    for rule in kept:
        rule.save()
    Rule.objects.filter(frame=frame).exclude(pk__in=[rule.pk for rule in kept]).delete()
    messages.success(request, f"Saved {len(kept) - 1} rule(s) and the “otherwise” target of {frame.name}.")
    return back


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
    if component is None or not frame.has_canvas:
        messages.error(request, "Unknown component." if component is None else f"A {frame.get_kind_display().lower()} has no elements.")
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
    if image not in list_materials() or not frame.has_canvas:
        messages.error(request, "Choose an image that exists in /project/materials/." if frame.has_canvas else f"A {frame.get_kind_display().lower()} has no elements.")
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
    picker: bool = element.frame is not None and element.frame.is_language_picker
    language: str = project.base_language if picker else content.language
    back: HttpResponse = _back_to_frame(request, element)
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
        if picker:
            element.text = data.get("text", "").strip()
        else:
            raw_id: str = data.get("content_id", "").strip()
            if raw_id and not raw_id.isdigit():
                raise ValueError("content_id must be a whole number.")
            element.content_id = int(raw_id) if raw_id else None
            if element.content_id is not None and element.content_id not in content.table.by_id():
                raise ValueError(f"content_id {element.content_id} is not in content.xlsx.")
        created: Frame | None = _apply_target(element, data.get("target", ""), content.languages) if element.frame else None
        _apply_update(element, data)
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
    return _back_to_frame(request, element)


@require_POST
@project_view
def move_element(request: HttpRequest, project: ProjectSettings, element_id: int) -> HttpResponse:
    """Swap an element with the one in front of it ("forward") or behind it ("backward")."""
    element: Element = get_object_or_404(Element.objects.select_related("frame"), pk=element_id, frame__isnull=False)
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
    return _back_to_frame(request, element)


@require_POST
@project_view
def edit_content_row(request: HttpRequest, project: ProjectSettings, content_id: int) -> HttpResponse:
    """Change the note and texts of one row of content.xlsx from an element's settings."""
    values: dict[str, str] = {
        key.removeprefix("text."): value for key, value in request.POST.items() if key.startswith("text.")
    }
    try:
        update_content_row(settings.PROJECT_DIR / "content.xlsx", content_id, request.POST.get("note", ""), values)
    except (OSError, ValueError) as error:
        messages.error(request, f"Content not changed: {error}")
    else:
        messages.success(request, f"Changed content #{content_id} in content.xlsx.")
    return _to("frame_editor", lang=request.POST.get("language", ""), frame_id=int(request.POST["frame"]))


@require_POST
@project_view
def delete_element(request: HttpRequest, project: ProjectSettings, element_id: int) -> HttpResponse:
    element: Element = get_object_or_404(Element.objects.select_related("frame"), pk=element_id)
    element.delete()
    messages.success(request, "Element deleted.")
    return _back_to_frame(request, element)


@require_POST
@project_view
def import_elements(request: HttpRequest, project: ProjectSettings, frame_id: int) -> HttpResponse:
    frame: Frame = get_object_or_404(Frame.objects.filter(kind__in=CANVAS_KINDS), pk=frame_id)
    content: Content = _content(request, project)
    targets: dict[str, int] = {item.key: item.id for item in Frame.objects.exclude(kind=Frame.Kind.PICKER)}
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
    if _locked(request, project):
        return render(request, "studio/unlock.html", {"project": project, "fingerprint": fingerprint(project.log_public_key)})
    content: Content = _content(request, project)
    nodes, edges = _flow_graph(project, content)
    names: dict[str, str] = {node["key"]: node["name"] for node in nodes}
    labels: dict[Any, str] = {
        edge["element_id"]: edge["text"] if edge["rule"] else (f"{edge['component']} ({edge['text']})" if edge["text"] else edge["component"])
        for edge in edges
    }
    return render(request, "studio/results.html", {
        "project": project, "content": content, "nodes": nodes, "edges": edges, "readonly": True,
        "sessions": [session_record(summary, names, labels) for summary in session_summaries(_log_key(request, project))],
        "protected": project.logs_protected,
        "dist_ready": (settings.DIST_DIR / page_path(language_folder(project, content.language, content.languages))).is_file(),
    })


@require_POST
@project_view
def import_logs(request: HttpRequest, project: ProjectSettings) -> HttpResponse:
    files = request.FILES.getlist("log_files")
    if not files:
        messages.error(request, "Choose one or more .jsonl files first.")
    if _locked(request, project):
        messages.error(request, "Provide the project's key file first.")
        return redirect("studio:results")
    for uploaded in files:
        try:
            destination: Path = import_jsonl(uploaded.name, uploaded.read(), _log_key(request, project))
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
        events, error = read_events(_log_path(file_name), _log_key(request, project)), ""
    except LockedLog:
        return redirect("studio:results")  # which asks for the key file
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
        if element.frame is not None and element.frame.is_language_picker:
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
        return JsonResponse({"events": read_events(_log_path(file_name), _log_key(request, project))})
    except LockedLog as error:
        return JsonResponse({"events": [], "error": str(error)}, status=403)
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
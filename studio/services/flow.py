"""The frame graph (which frame links where) and flowchart positions.

Positions are stored on each frame (``flow_x``/``flow_y``), so manual dragging
in the flowchart is permanent. New frames are placed next to the frame that
links to them; siblings are stacked above/below so branches never overlap.
"""

from typing import Iterable

from django.db import transaction

from studio.models import Frame, name_key

STEP_X: float = 260.0
STEP_Y: float = 130.0


def frame_edges(frames: Iterable[Frame]) -> dict[str, list[str]]:
    """``{frame name: [target frame names]}``. Elements must be prefetched."""
    frames = list(frames)
    names: dict[int, str] = {frame.id: frame.name for frame in frames}
    return {
        frame.name: [names[e.target_frame_id] for e in frame.elements.all() if e.target_frame_id in names]
        for frame in frames
    }


def distances(start: str, edges: dict[str, list[str]]) -> dict[str, int]:
    """Clicks needed to reach each frame from ``start``; unreachable frames are absent."""
    steps: dict[str, int] = {start: 0}
    queue: list[str] = [start]
    for name in queue:  # breadth-first: ``queue`` grows while we iterate
        for target in edges.get(name, []):
            if target not in steps:
                steps[target] = steps[name] + 1
                queue.append(target)
    return steps


def _free_slot(x: float, y: float) -> tuple[float, float]:
    """First free spot in column ``x``, trying y, y+1 row, y-1 row, y+2 rows, ..."""
    taken: list[tuple[float, float]] = list(Frame.objects.values_list("flow_x", "flow_y"))
    for attempt in range(200):
        candidate: float = y + (attempt + 1) // 2 * (1 if attempt % 2 else -1) * STEP_Y
        if all(abs(x - tx) >= STEP_X / 2 or abs(candidate - ty) >= STEP_Y / 2 for tx, ty in taken):
            return x, candidate
    return x, y + 200 * STEP_Y


def create_frame(is_picker: bool = False, linked_from: Frame | None = None) -> Frame:
    """Create a frame and place it sensibly in the flowchart.

    ``linked_from`` is the frame whose element will point to the new frame. Without
    it, the new frame continues after the most recent frame of the same kind.
    """
    anchor: Frame | None = linked_from or Frame.objects.filter(is_language_picker=is_picker).order_by("-id").first()
    if anchor is not None:
        x, y = _free_slot(anchor.flow_x + STEP_X, anchor.flow_y)
    elif is_picker:  # first picker frame: left of the story's first frame
        first: Frame | None = Frame.objects.first()
        x, y = _free_slot((first.flow_x if first else 160.0) - STEP_X, first.flow_y if first else 240.0)
    else:
        x, y = _free_slot(160.0, 240.0)
    # The default name repeats the frame's number (fnr-12 is "Frame 12"), which exists only after saving.
    with transaction.atomic(using="project"):
        frame: Frame = Frame.objects.create(is_language_picker=is_picker, flow_x=x, flow_y=y)
        taken: set[str] = {name_key(name) for name in Frame.objects.values_list("name", flat=True)}
        frame.name = default_name("Picker" if is_picker else "Frame", frame.pk, taken)
        frame.save(update_fields=["name"])
    return frame


def default_name(word: str, number: int, taken: set[str]) -> str:
    """``"Frame 12"``, or a higher free number if another frame was already renamed to that."""
    while name_key(f"{word} {number}") in taken:
        number += 1
    return f"{word} {number}"


def tidy_layout() -> None:
    """Arrange frames in columns by distance from the start, language pickers first."""
    frames: list[Frame] = list(Frame.objects.prefetch_related("elements"))
    edges = frame_edges(frames)
    pickers: list[Frame] = [frame for frame in frames if frame.is_language_picker]
    story: list[Frame] = [frame for frame in frames if not frame.is_language_picker]
    columns: dict[str, int] = _columns(pickers, edges, 0)
    columns |= _columns(story, edges, max(columns.values(), default=-1) + 1)

    per_column: dict[int, list[Frame]] = {}
    for frame in frames:
        per_column.setdefault(columns[frame.name], []).append(frame)
    for column, members in per_column.items():
        for row, frame in enumerate(members):
            frame.flow_x = 160.0 + column * STEP_X
            frame.flow_y = 400.0 + (row - (len(members) - 1) / 2) * STEP_Y
    Frame.objects.bulk_update(frames, ["flow_x", "flow_y"])


def _columns(group: list[Frame], edges: dict[str, list[str]], first: int) -> dict[str, int]:
    """Column per frame; frames the start cannot reach go in one column after the rest."""
    if not group:
        return {}
    steps: dict[str, int] = distances(group[0].name, edges)
    unreachable: int = max(steps.values()) + 1
    return {frame.name: first + steps.get(frame.name, unreachable) for frame in group}

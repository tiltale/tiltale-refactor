"""Read ``/frame-types/``: the catalog of frame kinds (name, one-sentence description, help text).

What each kind *does* is fixed in code (views, generate.py, tiltale.js) and keyed by ``Frame.Kind``;
the folder only holds the words shown to authors. See ``frame-types/README.md``.
"""

from dataclasses import dataclass
import json
from pathlib import Path

from django.conf import settings

from studio.models import Frame


@dataclass(frozen=True, slots=True)
class FrameType:
    slug: str
    name: str
    description: str
    help: str


def load_frame_types() -> dict[str, FrameType]:
    """Every kind in ``Frame.Kind`` order, or a readable error naming the missing file or key."""
    types: dict[str, FrameType] = {}
    for kind in Frame.Kind.values:
        path: Path = settings.FRAME_TYPES_DIR / kind / "frame-type.json"
        if not path.is_file():
            raise ValueError(f"{path} is missing.")
        data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
        words: dict[str, str] = {key: str(data.get(key, "")).strip() for key in ("name", "description", "help")}
        if not all(words.values()):
            raise ValueError(f"{path} needs 'name', 'description' and 'help'.")
        types[kind] = FrameType(slug=kind, **words)
    return types

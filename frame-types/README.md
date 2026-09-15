# Frame types

Every frame in a project has one **kind**. This folder is the catalog of kinds that the studio shows in the *+ Add frame* dropdown and in the frame editor: one folder per kind with a `frame-type.json` holding the words an author sees.

| Key | Used for |
|---|---|
| `name` | The dropdown entry, the default frame name (`Document 12`) and the badge in the flowchart. |
| `description` | One sentence next to the name in the dropdown. |
| `help` | The explanation at the top of the frame editor. |

The folder name is the kind's slug and must be one of `Frame.Kind` in `studio/models.py`. **What a kind does is fixed in code**, not in this folder: the studio (`studio/views.py`, `studio/templates/studio/edit_frame.html`), Regenerate (`studio/services/generate.py`) and the story player (`runtime/tiltale.js`) all branch on the slug. Adding a folder here does not add behavior; removing one breaks the studio, which reports the missing file.

| Kind | What readers get | What the author edits |
|---|---|---|
| `frame` | The frame as designed: background, elements, buttons. | The canvas. |
| `picker` | A start-page screen to choose a language (two or more languages only). | The canvas; texts are typed, buttons open a language. |
| `document` | One image as large as the screen allows, zoomable, with a × Close button that returns to the previous frame. | The image, the color around it and the Close text. |
| `validation` | Nothing: the reader is sent on by the first rule that matches the global variables. | The rules, and where to go otherwise. |
| `minigame` | Same as `frame` for now; its own color in the flowchart. | The canvas. |

Global variables are defined under **Settings → Advanced**. Any element text may contain `{name}` to show a variable's current value; see `components/README.md`.

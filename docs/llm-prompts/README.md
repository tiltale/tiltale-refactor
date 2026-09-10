# Default LLM prompts

Prompts for letting a language model do repetitive setup work. Both are placeholders for now.

| File | Use it to… | Input | Output |
|---|---|---|---|
| `01-extract-content.md` | turn storyboard exports into texts | ZIP of PDFs/images, one per frame, named after the frame | a filled copy of `content-template.xlsx` |
| `02-build-frame.md` | place a frame's elements automatically | one frame image | frame and elements in the project database |
| `content-template.xlsx` | start from the exact `content.xlsx` layout | — | — |

Prompt 2 needs a page that shows every component with its data first, so the model knows the options. That page does not exist yet.

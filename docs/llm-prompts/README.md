# Default LLM prompts

Prompts that let a language model do repetitive setup work.

| File | Use it to… | How |
|---|---|---|
| `01-extract-content.md` | turn a storyboard (ZIP of PDFs/images, or one PDF) into texts | Paste it into a model chat with the storyboard and `content-template.xlsx` attached, then save the returned file as `/project/content.xlsx` (or copy its rows into your existing one). |
| `02-build-frame.md` | place a frame's elements from its storyboard image | In the frame editor, open **Build with an LLM**, press **Copy prompt** (this fills in your components, texts and frames), paste it into a model chat with the frame image, and paste the JSON answer back into the editor. |
| `content-template.xlsx` | start from the exact `content.xlsx` layout | Rename the `en-US` column to your language(s) first. |

Prompt 2 contains `$frame_id`, `$components`, … placeholders; the studio fills them in. Do not use `$` elsewhere in that file.

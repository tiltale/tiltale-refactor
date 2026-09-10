# Prompt 1: extract the story texts into content.xlsx

Attach two files to a chat with a language model that can read PDFs and images and create files (for example Claude with file creation enabled):

1. the storyboard: a ZIP of PDFs and/or images, or a single PDF;
2. `content-template.xlsx` from this folder (or your project's current `content.xlsx`).

Then paste everything below the line.

---

You are preparing the texts of an interactive story for a tool called TilTale. Each storyboard page is one **frame** of the story. Extract every piece of text a reader sees and put it in the attached workbook.

**Naming the frames**
- If I attached a single PDF, page 1 is `frame-1`, page 2 is `frame-2`, and so on.
- Otherwise every file is one frame, named after the file without its extension (`intro.png` is frame `intro`). If such a file has several pages, name them `<file>-1`, `<file>-2`, and so on.
- Treat the frames in this order: by frame number where names end in a number, otherwise alphabetically.

**Filling the workbook**
- Keep the sheet, the header row and the column order exactly as they are: `content_id`, `note`, then one column per language code (for example `en-US`).
- Add one row per separate text element: each speech bubble, caption, button label or sign is its own row. Never merge two elements into one row, and never split one element over two rows.
- Order rows by frame, and within a frame in reading order (top to bottom, left to right).
- `content_id`: whole numbers, counting up by one. Start after the highest existing `content_id`, or at 1 if the sheet has no rows. Never change or reuse existing rows.
- `note`: the frame name, a middle dot, and the kind of element, for example `frame-3 · speech bubble`, `frame-3 · choice button`, `frame-3 · caption`. If a speaker is clear, add it: `frame-3 · speech bubble · Mia`.
- Language columns: write the text exactly as it appears, in the column of the language it is written in. Keep spelling, punctuation, capitals and emoji. Keep deliberate line breaks as line breaks inside the cell. Do not translate, correct or complete anything. Leave the other language columns empty.
- If a text is partly unreadable, write what you can read and put `[unreadable]` where the rest is.
- Skip text that is part of the artwork but not meant to be read, such as page numbers, file names or watermarks.

**What to return**
1. The filled workbook as a downloadable `.xlsx` file named `content.xlsx`. If you cannot create files, give a table with exactly the same columns that I can paste into Excel.
2. Below it, a short list of anything you were unsure about (unreadable text, unclear frame order, text you skipped), each with its frame name. Write "No doubts." if there is nothing.

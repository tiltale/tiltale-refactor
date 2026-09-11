# TilTale

TilTale is a local studio for building interactive, branching stories (for example for research studies). You build the story in your browser; **Regenerate** turns it into a plain website in `/project/dist/` made of HTML, CSS, JavaScript and one small `log.php`, which you upload to any web host with PHP.

## Quick start

Install Python 3.12 or newer first. On Windows, restart the PC after installing Python: otherwise `python` and `pip` are often not found in the terminal yet.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and create a project, or copy an existing `project/` folder next to `manage.py`. The TilTale version is in `config/settings.py` (`TILTALE_VERSION`) and on the Help page; every generated page carries it in an HTML comment.

## Daily workflow

1. **Develop**: add frames (`+ Frame`), place components and images on them (click one to preview it first; see *Shortcuts* for moving and resizing), pick texts from `content.xlsx`, and set what each button does. Click a frame in the list to show it in the preview; **Edit** opens it. Adding or deleting a frame updates the preview automatically; after other changes, press **Regenerate**. Large stories take a while: the terminal running `runserver` lists every image as it is converted.
2. **Flowchart**: see how frames connect. Click a frame to zoom to it. Drag frames to arrange them; positions are saved in the project database. `Shift`+click selects several frames to move together; **Tidy up** rearranges everything automatically.
3. **Regenerate**, then check the preview on different phone sizes.
4. **Play-test**: a robot plays every generated page to its end and shows pass/fail plus the full log of the run.
5. Upload `/project/dist/`. Later, download `dist/logs/` from the server and import the files under **Results**, which lists every visit with a readable timeline and draws visit counts, seconds per frame and the percentage that took each path onto the flowchart. Select one visit to see its own path highlighted.

The status bar at the bottom shows whether everything is saved and in the preview. It is checked on every page load, and turns red as soon as a background save (dragging an element or frame) fails.

## Shortcuts

On a Mac, use `Cmd` wherever this says `Ctrl`.

**Frame editor** (elements, images and the background image)

| Do this | To |
|---|---|
| Drag | move it. Its edges stick to the edges of other elements, shown by a blue line. |
| `Shift` + drag | move it only horizontally or only vertically, whichever way you drag furthest. |
| Drag a corner dot (appear on hover) | resize it from that corner; the opposite corner stays. Images and the background keep their proportions; components do not. Components that grow with their text (the `laura-*` ones) use this as their minimum height. |
| `Shift` + drag a corner dot | the opposite: distort an image freely, or keep a component's proportions. |
| Drag the black dot (bubbles only) | point the bubble's tail at a mouth or head. The bubble itself stays where it is. |
| Click an element or image, or `Tab` to it and press `Enter` | open its settings (text, exact size and position, colors, what a click does). |
| `Ctrl`+`Z` / `Ctrl`+`Shift`+`Z` | undo / redo a move or resize. The history covers the current page: it starts over after anything that reloads it, such as adding an element or saving settings. Inside a text field these keys undo typing instead. |
| Click a component or image in the side panel | preview it, then **Add to frame** (or, for images, **Use as background**). |
| `Esc` | close a dialog. |

**Flowchart**

| Do this | To |
|---|---|
| Click a frame | zoom to it and show its preview and links. |
| Drag a frame | move it; the position is saved. |
| `Shift` + click | select several frames, then drag one to move them all. |
| Drag the background | pan. |
| Mouse wheel, or the `−` / `+` buttons | zoom. **Fit** shows every frame. |
| Double-click a frame, or `Tab` to it and press `Enter` | open it in the frame editor. |

## Document frames (zoom and drag)

Some frames are documents (a poster, a leaflet). In the frame editor, tick **Readers can zoom and drag this frame** under *Document viewer*. Readers then drag with a finger or the mouse, pinch on a phone, or use the mouse wheel and the **+** / **−** buttons on larger screens. A fixed **× Close** button in the top-right corner returns to the previous frame; its text is a row of `content.xlsx`, so it appears in the reader's language (leave it empty for a plain ×). The play-test robot ignores the Close button, so give a document frame a normal button that leads on, or the robot treats it as an end.

## Frame names

Every frame has two labels:

| | Example | Used for | Changes? |
|---|---|---|---|
| **ID** | `fnr-12` | the story's code, preview links, study logs, LLM answers | never; numbers of deleted frames are not reused |
| **Name** | `Frame 12` (default), `Intro scene` | you, in the studio | rename freely in the frame editor |

A new frame's default name repeats its ID number. Names must be unique, ignoring capitals, spaces, `-` and `_` (`Frame 12` is refused when `frame_12` exists), and need at least one letter (a–z) or digit. The visit log pages show each ID with the frame's current name.

## Logo and favicon

`logo-tiltale.png` (startup screen) and `favicon.ico` (browser tab) in the repository root are used for every generated story. To use a different one for **one project**, put a file with the same name in `/project/`, for example `/project/logo-tiltale.png`, and press Regenerate. Delete it to go back to the default. The studio itself always shows the TilTale files from the repository root.

## Building with a language model

`docs/llm-prompts/` has two ready prompts:

1. **Texts**: `01-extract-content.md` turns a storyboard (a ZIP of PDFs/images named after their frames, or one PDF where page 1 is `frame-1`) into a filled `content.xlsx`.
2. **Frames**: in the frame editor, open **Build with an LLM** and press **Copy prompt**. It is `02-build-frame.md` with your components, texts and frames filled in. Paste it into a model chat with the frame's storyboard image, then paste the JSON answer back and press **Add these elements**. Nothing is added unless every element in the answer is valid.

## Participant IDs (Qualtrics, Prolific, …)

Give each participant a link with their ID in the URL. The parameter name is set under **Settings → Participant ID parameter** (default `ppn`):

```
https://www.example.org/our-story/index.html?ppn=R_1abcDEF
```

In Qualtrics, put this link in a *Text/Graphic* question or an *End of Survey* redirect and insert the piped text `${e://Field/ResponseID}` where the ID goes, e.g. `…/index.html?ppn=${e://Field/ResponseID}`.

- The ID is used for logging. Links without it get a random ID that stays the same in that browser.
- **Every page load is a new visit with its own log file**: `logs/<participant>--<visit>.jsonl`. Opening the link again never overwrites an earlier log. Readers who reload continue on the frame where they were; the visit files show exactly what happened.

### Starting, continuing and restarting a story

| Link | What happens |
|---|---|
| `…/index.html?ppn=R_1abcDEF` | Starts the story. Opening the same link again, or refreshing, continues where the reader was. |
| `…/restart/?ppn=R_1abcDEF` | Forgets this browser's progress and starts over, keeping the parameters. For experimenters who reuse a device; no incognito window needed. Only at the site root: with several languages it opens the start page again. |
| any story link with `&restart` added, e.g. `…/our-story---nl-NL/index.html?ppn=R_1abcDEF&restart` | The same, for one specific page. TilTale removes `restart` from the address once it has been handled, so a later refresh continues normally. |
- **Finish redirect**: under Settings, enter a URL to open when a reader clicks an element set to *End story*. Write `{ID}` where the participant ID belongs. It is URL-encoded automatically. Example: `https://example.qualtrics.com/jfe/form/SV_abc?ppn={ID}` sends participant `R_1abcDEF` back to `…?ppn=R_1abcDEF`. `{ID}` was chosen because curly braces never appear in normal URLs, while `%` and `@` already mean something there.

## Several languages

Languages are the columns after `content_id` and `note` in `/project/content.xlsx`. With **one** language, the story is `/dist/index.html` and none of the options below exist. With **two or more**:

```
dist/index.html               start page built from language-picker frames (optional)
dist/<slug>---en-US/index.html  the English story
dist/<slug>---nl-NL/index.html  the Dutch story
dist/tiltale.js, style.css, assets/, log.php, logs/, restart/   shared by all pages
```

**Language-picker frames** (`+ Picker frame`) are the frames of the start page. They are shown before a language is chosen, so their texts are typed directly instead of coming from `content.xlsx`, and their buttons open a language. They have an amber dashed border and a *Picker* badge everywhere in the studio. Without picker frames, no `dist/index.html` is generated and you link participants to a language folder directly. The participant ID and the visit carry over from the start page into the chosen language.

## Publishing

Upload the **contents** of `/project/dist/` to a folder on a web server with PHP 7.4 or newer. `log.php` writes to `dist/logs/`, so that folder must be writable by the web server. `logs/.htaccess` blocks public access on Apache; on nginx add `location ~ /logs/ { deny all; }`. Regenerate never deletes `dist/logs/`.

## Where to find what

Most changes start in one of these places:

| I want to change… | Open |
|---|---|
| a studio page's behavior | `studio/views.py` (the function named in `studio/urls.py`) |
| a studio page's layout | `studio/templates/studio/<page>.html` |
| how the studio looks / reacts | `studio/static/studio/app.css`, `app.js` |
| how the published story behaves | `runtime/tiltale.js` |
| how story elements look | `components/<name>/` and `runtime/elements.css` |
| what is stored in the database | `studio/models.py` (then see *Changing models*) |
| what Regenerate produces | `studio/services/generate.py` |

### `config/`: Django project settings

| File | Purpose |
|---|---|
| `settings.py` | `TILTALE_VERSION`, paths (`PROJECT_DIR`, `DIST_DIR`, …), databases, installed apps, terminal logging. |
| `urls.py` | Sends every URL to the studio app. |
| `wsgi.py` | Entry point for a WSGI server (not needed for `runserver`). |

### `studio/`: the studio app

| File | Purpose |
|---|---|
| `models.py` | Database tables: project settings, frames, elements, per-language layout overrides. |
| `views.py` | One function per page or API call. Validates input, then calls a service. Also computes the status bar (`status_context`). |
| `urls.py` | Maps each URL to a view. |
| `forms.py` | Forms for new project, settings and frame settings, including their help texts. |
| `db.py` | Routes all studio tables to `/project/project.sqlite3`. |
| `tests.py` | Behavior tests (`python manage.py test`). |
| `migrations/` | Generated by Django. Never edit by hand. |
| `services/project.py` | Creating, opening and checking the `/project/` folder; applies migrations automatically. |
| `services/content.py` | Reading and appending `content.xlsx`. |
| `services/components.py` | Loading `components/*`. |
| `services/flow.py` | Frame links, reachability, placing new frames, *Tidy up*. |
| `services/validate.py` | Preflight checks and phone presets. |
| `services/generate.py` | Regenerate: builds `/project/dist/`. |
| `services/study_logs.py` | Writing, importing and summarizing visit logs; seconds per frame and readable event lines for Results. |
| `templates/studio/` | One HTML template per page; `base.html` is the shared frame, `_field.html` renders a form field, `_flow.html` and `_flow_inspector.html` are the flowchart canvas shared by Flowchart and Results. |
| `static/studio/app.css`, `app.js` | All studio styling and interactivity (no libraries). |

### `runtime/`: files copied into every generated story

See `runtime/README.md` for the full table. `tiltale.js` is the story player, `log.php` the server-side logger.

### Repository root

| File | Purpose |
|---|---|
| `logo-tiltale.png`, `favicon.ico` | Default startup logo and browser-tab icon of every story (see *Logo and favicon*). |
| `manage.py` | Django's command-line entry point (`runserver`, `test`, `makemigrations`). |
| `requirements.txt` | Python packages. |

### `components/`: reusable story elements

One folder per component with `component.json` (name, defaults, colors), `component.svg` (shape) and `component.css` (styling). See `components/README.md`.

### `docs/llm-prompts/`: default prompts for language models

The two prompts described in *Building with a language model*, plus `content-template.xlsx`. See `docs/llm-prompts/README.md`.

### Generated folders (ignored by Git)

| Folder | Contents |
|---|---|
| `project/` | Everything you make: `project.sqlite3`, `content.xlsx`, `materials/` (images), `logs/` (visits), `default-colors.css`, `style-overrides.css`, and optionally your own `logo-tiltale.png` / `favicon.ico`. Back this up. |
| `project/dist/` | The website produced by Regenerate. Safe to delete except `dist/logs/` on the server. (Before v2.0.10 this was `/dist/` in the repository root; that folder can be deleted.) |

## Changing models

After editing `studio/models.py`:

```bash
python manage.py makemigrations studio
git add studio/migrations
```

Django writes the migration; never write one by hand. TilTale applies pending migrations to `/project/project.sqlite3` automatically on the next request. CI fails if a model change has no committed migration.

## Tests and CI

`python manage.py test` runs the behavior tests against an in-memory database. GitHub Actions (`.github/workflows/tests.yml`) runs Django's checks, the migration check, the tests, a syntax check of `tiltale.js`, `app.js` and `log.php`, and, on pull requests, fails when `TILTALE_VERSION` in `config/settings.py` was not bumped.

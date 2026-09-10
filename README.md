# TilTale

TilTale is a local studio for building interactive, branching stories (for example for research studies). You build the story in your browser; **Regenerate** turns it into a plain website in `/dist/` made of HTML, CSS, JavaScript and one small `log.php`, which you upload to any web host with PHP.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

Open <http://127.0.0.1:8000/> and create a project, or copy an existing `project/` folder next to `manage.py`.

## Daily workflow

1. **Develop**: add frames (`+ Frame`), place components on them, pick texts from `content.xlsx`, and set what each button does.
2. **Flowchart**: see how frames connect. Drag frames to arrange them; positions are saved in the project database. `Shift`+click selects several frames to move together; **Tidy up** rearranges everything automatically.
3. **Regenerate**, then check the preview on different phone sizes.
4. **Play-test**: a robot plays every generated page to its end and shows pass/fail plus the full log of the run.
5. Upload `/dist/`. Later, download `dist/logs/` from the server and import the files under **Results**.

## Participant IDs (Qualtrics, Prolific, …)

Give each participant a link with their ID in the URL. The parameter name is set under **Settings → Participant ID parameter** (default `ppn`):

```
https://www.example.org/our-story/index.html?ppn=R_1abcDEF
```

In Qualtrics, put this link in a *Text/Graphic* question or an *End of Survey* redirect and insert the piped text `${e://Field/ResponseID}` where the ID goes, e.g. `…/index.html?ppn=${e://Field/ResponseID}`.

- The ID is used for logging. Links without it get a random ID that stays the same in that browser.
- **Every page load is a new visit with its own log file**: `logs/<participant>--<visit>.jsonl`. Opening the link again never overwrites an earlier log. Readers who reload continue on the frame where they were; the visit files show exactly what happened.
- **Finish redirect**: under Settings, enter a URL to open when a reader clicks an element set to *End story*. Write `{ID}` where the participant ID belongs. It is URL-encoded automatically. Example: `https://example.qualtrics.com/jfe/form/SV_abc?ppn={ID}` sends participant `R_1abcDEF` back to `…?ppn=R_1abcDEF`. `{ID}` was chosen because curly braces never appear in normal URLs, while `%` and `@` already mean something there.

## Several languages

Languages are the columns after `content_id` and `note` in `/project/content.xlsx`. With **one** language, the story is `/dist/index.html` and none of the options below exist. With **two or more**:

```
dist/index.html               start page built from language-picker frames (optional)
dist/<slug>---en-US/index.html  the English story
dist/<slug>---nl-NL/index.html  the Dutch story
dist/tiltale.js, style.css, assets/, log.php, logs/   shared by all pages
```

**Language-picker frames** (`+ Picker frame`) are the frames of the start page. They are shown before a language is chosen, so their texts are typed directly instead of coming from `content.xlsx`, and their buttons open a language. They have an amber dashed border and a *Picker* badge everywhere in the studio. Without picker frames, no `dist/index.html` is generated and you link participants to a language folder directly. The participant ID and the visit carry over from the start page into the chosen language.

## Publishing

Upload the **contents** of `/dist/` to a folder on a web server with PHP 7.4 or newer. `log.php` writes to `dist/logs/`, so that folder must be writable by the web server. `logs/.htaccess` blocks public access on Apache; on nginx add `location ~ /logs/ { deny all; }`. Regenerate never deletes `dist/logs/`.

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
| `settings.py` | Paths (`PROJECT_DIR`, `DIST_DIR`, …), databases, installed apps. |
| `urls.py` | Sends every URL to the studio app. |
| `wsgi.py` | Entry point for a WSGI server (not needed for `runserver`). |

### `studio/`: the studio app

| File | Purpose |
|---|---|
| `models.py` | Database tables: project settings, frames, elements, per-language layout overrides. |
| `views.py` | One function per page or API call. Validates input, then calls a service. |
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
| `services/generate.py` | Regenerate: builds `/dist/`. |
| `services/study_logs.py` | Writing, importing and summarizing visit logs. |
| `templates/studio/` | One HTML template per page; `base.html` is the shared frame and `_field.html` renders a form field. |
| `static/studio/app.css`, `app.js` | All studio styling and interactivity (no libraries). |

### `runtime/`: files copied into every generated story

See `runtime/README.md` for the full table. `tiltale.js` is the story player, `log.php` the server-side logger, `logo-tiltale.png` the startup logo (add your own; the preflight list reports it when missing).

### `components/`: reusable story elements

One folder per component with `component.json` (name, defaults, colors), `component.svg` (shape) and `component.css` (styling). See `components/README.md`.

### `docs/llm-prompts/`: default prompts for language models

Placeholders for (1) extracting texts from storyboard images into `content-template.xlsx` and (2) building a frame from its image. See `docs/llm-prompts/README.md`.

### Generated folders (ignored by Git)

| Folder | Contents |
|---|---|
| `project/` | Everything you make: `project.sqlite3`, `content.xlsx`, `materials/` (images), `logs/` (visits), `default-colors.css`, `style-overrides.css`. Back this up. |
| `dist/` | The website produced by Regenerate. Safe to delete except `dist/logs/` on the server. |

## Changing models

After editing `studio/models.py`:

```bash
python manage.py makemigrations studio
git add studio/migrations
```

Django writes the migration; never write one by hand. TilTale applies pending migrations to `/project/project.sqlite3` automatically on the next request. CI fails if a model change has no committed migration.

## Tests and CI

`python manage.py test` runs the behavior tests against an in-memory database. GitHub Actions (`.github/workflows/tests.yml`) runs Django's checks, the migration check, the tests, and a syntax check of `tiltale.js`, `app.js` and `log.php`.

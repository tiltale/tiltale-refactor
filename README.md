# TilTale

**TilTale** is a platform for building and running **interactive digital narratives (IDNs)**.

You do **not** need previous Django experience to start working on TilTale. The repository is intentionally small, conventional and documented for student developers.

---

## Contents

| Section | What you will find |
|---|---|
| [Before you begin](#before-you-begin) | Required software and recommended environment. |
| [Get TilTale](#get-tiltale) | Download the project as a ZIP or clone it with Git, then create a virtual environment. |
| [Run TilTale](#run-tiltale) | Install dependencies and start Django. |
| [First project](#first-project) | How `/project/` is created. |
| [Useful commands](#useful-commands) | Commands you will use most often. |
| [Tech stack](#tech-stack) | Why each dependency exists. |
| [Project structure](#project-structure) | Where authoring, components and runtime code live. |
| [Content and languages](#content-and-languages) | How `content.xlsx` and stable `content_id` values work. |
| [Development conventions](#development-conventions) | The rules that keep TilTale simple. |
| [Quick fixes](#quick-fixes) | Common Windows/PowerShell problems. |

---

## Before you begin

### Visual Studio Code

VS Code is the recommended editor. No project-specific VS Code extensions are required.

Useful extensions, if you already use them:

- Python
- Pylance

### Python

TilTale targets **Python 3.14**; the pinned/recommended maintenance release for this base is **Python 3.14.7**.

Check:

```powershell
python --version
where.exe python
```

### Recommended development environment

| Software | Version / environment |
|---|---|
| Operating system | Windows 11 |
| Python | 3.14.7 |
| Django | 6.1.1 |
| openpyxl | 3.1.5 |
| Pillow | 12.3.0 |
| Editor | Visual Studio Code |
| Shell | PowerShell |

Compatible dependency ranges are recorded in `requirements.txt`; patch updates within the current minor release are allowed.

> TilTale is a **local authoring tool**. Django's development server is deliberately configured for localhost use; do not expose it as a production web service.

---

## Get TilTale

You first need a local copy of the TilTale repository on your computer.

There are two ways to get it.

### Recommended: Download ZIP

This is the easiest option if you are new to Git.

1. Open the repository:
   https://github.com/tiltale/tiltale-refactor
2. Select **Code → Download ZIP**.
3. Unpack the ZIP.
4. Open VS Code.
5. Select **File → Open Folder...**.
6. Open the unpacked `tiltale-refactor` folder.
7. Select **Terminal → New Terminal**.

### More experienced? Use Git

If Git is installed, you can clone the repository instead:

```bash
git clone https://github.com/tiltale/tiltale-refactor.git
cd tiltale-refactor
```

Then open the folder in VS Code.

### Check that you opened the repository root

The terminal must be inside the folder containing `manage.py`.

#### Windows

```powershell
Test-Path manage.py
```

Expected:

```text
True
```

#### macOS

```bash
test -f manage.py && echo "True"
```

Expected:

```text
True
```

#### Linux

```bash
test -f manage.py && echo "True"
```

Expected:

```text
True
```

If you do not see `True`, open the correct repository folder before continuing.

### Create the local virtual environment

The virtual environment keeps TilTale's Python packages separate from other Python projects on your computer.

#### Windows

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### macOS

```bash
python3.14 -m venv .venv
source .venv/bin/activate
```

#### Linux

```bash
python3.14 -m venv .venv
source .venv/bin/activate
```

The terminal prompt should now start with:

```text
(.venv)
```

---

## Run TilTale

Install the project dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Check Django's configuration:

```powershell
python manage.py check
```

Start TilTale:

```powershell
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Stop the server with:

```text
Ctrl + C
```

### Database migrations

You do **not** need to run a migration command during normal setup. TilTale's authoring models belong to the active project's own SQLite file, and a newly created project is migrated automatically.

That is intentional: **no `/project/` folder means “no active project.”** Merely starting Django must not create one.

Do not run the normal default-database command:

```powershell
python manage.py migrate
```

If a future TilTale update requires an older copied project to update its database schema, use the project database explicitly:

```powershell
python manage.py migrate --database=project
```

---

## First project

If `/project/` does not exist, the home page gives you two paths:

1. **Existing project:** copy its complete `project` folder into the TilTale repository root, then reload.
2. **New project:** press **Create a new project** and enter its name, base language and optional extra languages.

A new project looks like this:

```text
project/
├── project.sqlite3
├── content.xlsx
├── default-colors.css
├── style-overrides.css
├── materials/
└── logs/
```

`/project/` is ignored by Git because it may contain study data, project assets and local authoring state.

Generated websites go to `/dist/`. That folder is also ignored because it is disposable: press **Regenerate** to rebuild it from source project data.

---

## Useful commands

| Command | What it does |
|---|---|
| `.\.venv\Scripts\Activate.ps1` | Activates the local Python environment. |
| `python -m pip install -r requirements.txt` | Installs TilTale's project dependencies. |
| `python manage.py check` | Checks Django configuration without creating a project. |
| `python manage.py test` | Runs the small source-level test suite. |
| `python manage.py runserver` | Starts the local authoring application. |
| `git status` | Shows source changes before you commit. |

Before committing source work:

```powershell
python manage.py check
python manage.py test
git status
```

Verify that `project/` and `dist/` are **not** listed by Git.

---

## Tech stack

The dependency budget is deliberately small.

| Technology | Why TilTale needs it |
|---|---|
| **Python 3.14** | Main programming language. Type annotations are used on function inputs/returns and non-obvious local values. |
| **Django 6.1** | Local routing, templates, validation, CSRF protection and SQLite ORM. |
| **openpyxl** | Reads/writes `content.xlsx` without adding a dataframe dependency. |
| **Pillow** | Creates responsive WebP variants of large project images during generation. |
| **SQLite** | Project-local authoring database. No database server is required. |
| **Vanilla JavaScript** | Dragging, flowchart interaction, device preview and the generated story runtime. |
| **HTML/CSS/SVG** | Developer interface and framework-free generated stories/components. |

### Why there is no frontend framework

The authoring UI needs some rich interactions, but not enough to justify a second application framework and build tool today. Small browser behaviors live in one documented `studio/static/studio/app.js` file. If this becomes the wrong trade-off later, the requirement—not fashion—should trigger that change.

---

## Project structure

```text
tiltale/
├── README.md
├── requirements.txt
├── manage.py
│
├── config/                   Minimal Django project plumbing
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── studio/                   The one Django authoring app
│   ├── models.py             Project-scoped authoring data
│   ├── forms.py              Server-side durable-input validation
│   ├── views.py              HTTP layer; delegates non-HTTP work
│   ├── urls.py               All authoring routes
│   ├── tests.py              Small behavior tests for durable rules
│   ├── services/             Workbook/files/generation/log operations
│   ├── templates/studio/     Django UI templates
│   ├── static/studio/        One CSS + one authoring JS file
│   └── migrations/           Project database schema
│
├── components/               Reusable story component definitions
│   ├── speech-bubble/
│   ├── choice-button/
│   └── next-button/
│
└── runtime/                  Generic plain HTML/CSS/JS story runtime

# Created locally and never committed:
/project/
/dist/
/.venv/
```

### Component vs. element

Use these terms consistently:

- **Component** = reusable source definition in `/components/`.
- **Element** = one placed instance of a component on a specific frame.

This avoids phrases such as “component instance component” and keeps the database/source-code distinction clear.

---

## Content and languages

`/project/content.xlsx` starts with:

| content_id | note | en-US | nl-NL |
|---:|---|---|---|
| 1 | opening bubble | Hello. | Hallo. |
| 2 | next choice | Continue | Verder |
 

TilTale uses a **machine-managed positive integer `content_id`**:

- If you type content on a new row and leave the ID empty, TilTale assigns the next unused ID when it reads the workbook.
- Existing IDs never get renumbered.
- Duplicate IDs are reported as an error.
- The content picker still displays the physical Excel row to help humans find it.
- `note` is optional and does not need to be unique.

### Adding a language

Column A is `content_id` and column B is `note`. Every named column after that is a language. To add a language, enter its code (for example `de-DE`) in the next empty column and reload TilTale. The language automatically becomes available in the developer-side language selector and the next regeneration creates a new language-specific build.

Element position, size and font size can be overridden for a selected translation without changing the shared frame/background/flow.

---

## Main workflows

### `/`

Project gate. It intentionally starts without a database/project if `/project/` is absent.

### `/develop/`

Developer dashboard with:

- searchable frame list;
- current generated story preview plus rendered frame thumbnails;
- draggable/hideable frame-panel divider;
- device viewport presets including older phones;
- language selector;
- Restart and Regenerate;
- stale-build notice;
- validation warnings linking back to frames.

### `/develop/edit/frame-x/`

Frame editor with:

- image/solid/no background;
- frame fade-in setting;
- source components from `/components/`;
- direct element dragging;
- workbook content picker;
- target-frame choice;
- project/per-element colors;
- delay behavior;
- per-language geometry/font overrides.

### `/develop/flowchart/`

Dependency-free flowchart with persisted draggable positions, zoom-to-selection, edges and selected-frame connection details.

### `/results/`

Reads JSONL session logs from `/project/logs/` and can import downloaded JSONL logs.

### Regeneration

Regeneration deletes/recreates `/dist/`, runs practical project checks, creates responsive image variants and emits one plain website per workbook language:

```text
dist/
└── project-slug---en-US/
    ├── index.html
    ├── script.js
    ├── style.css
    └── assets/
```

Warnings do not block generation; they are there to make problems visible while the story remains testable.

---

## Quick fixes

### PowerShell says `Activate.ps1` cannot be loaded

For your user account:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Open a new VS Code terminal, then:

```powershell
.\.venv\Scripts\Activate.ps1
```

### `python` is not recognized

```powershell
where.exe python
py -0p
```

Check that the directory containing `python.exe` is in your user `PATH`.

### Django is not installed

Make sure the virtual environment is active, then:

```powershell
python -m pip install -r requirements.txt
```

### Port 8000 is already in use

Use another local port:

```powershell
python manage.py runserver 8001
```

### The preview did not update

Look for the amber bottom status line / stale notice, then press **Regenerate**. `/dist/` is intentionally not updated on every database write.

### A language is missing

Open `/project/content.xlsx`. Column A must be `content_id`, column B must be `note`, and language columns come after them. Add new languages in the next empty column, save the workbook and reload TilTale.

### `content.xlsx` cannot be read or updated

Close `content.xlsx` in Excel or any other program that may be locking the file, then reload TilTale or press **Regenerate** again.

---

### Asking for help

Include:

```powershell
python --version
python -m django --version
python manage.py check
git status
```

Also include the **first error message**, not only the final stack-trace line.
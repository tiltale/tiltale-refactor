# TilTale

**TilTale** is a local studio for building and running **interactive digital narratives (IDNs)**: branching stories with photos, speech bubbles and choices, for example for research studies. You build the story in your browser; **Regenerate** turns it into a plain website (HTML, CSS, JavaScript and one small `log.php`) that you upload to any web host with PHP.

You do **not** need previous experience with Python, Django or command-line development to work on this project. TilTale is intentionally developed with students and less-experienced developers in mind. If some of the tools below are new to you, that is fine: this README explains only what you need to get started.

---

## Contents

| Section | What you will find |
|---|---|
| [Before you begin](#before-you-begin) | The tools you need and what they do. |
| [Install Python](#install-python) | Setup for Windows, macOS and Linux. |
| [Get TilTale](#get-tiltale) | Download the project as a ZIP or clone it with Git. |
| [Run TilTale](#run-tiltale) | Install dependencies and start the studio. |
| [Useful commands](#useful-commands) | The commands you will use most often. |
| [Daily workflow](#daily-workflow) | Building, checking, publishing and analysing a story. |
| [Shortcuts](#shortcuts) | Mouse and keyboard in the frame editor and the flowchart. |
| [Frame kinds](#frame-kinds) | Frames, pickers, documents, validation points and minigames. |
| [Global variables, validation points and scoreboards](#global-variables-validation-points-and-scoreboards) | Counting choices and routing readers by what they did. |
| [Editing texts](#editing-texts) | The Content page: texts, images and fonts without opening the source files. |
| [Frame names](#frame-names), [Logo and favicon](#logo-and-favicon), [Fonts](#fonts), [Building with a language model](#building-with-a-language-model) | Naming, branding, fonts and LLM prompts. |
| [Participant IDs](#participant-ids-qualtrics-prolific-) | Links, logging, restarting and the finish redirect. |
| [Loading, full screen and a lost connection](#loading-full-screen-and-a-lost-connection) | What a reader sees while the story downloads, and what happens when the wifi drops. |
| [Offline classroom use](#offline-classroom-use) | Download every language onto a device, play without wifi all day, upload the logs afterwards. |
| [The Test page](#the-test-page) | One robot, two modes: a quick Play-test while you build and a thorough Stress-test before you publish, plus how to test on real phones. |
| [Protecting logs](#protecting-logs) | Encrypting study logs with a project key; see also `ETHICS.md`. |
| [Several languages](#several-languages), [Publishing](#publishing) | Multilingual stories and uploading. |
| [Tech stack](#tech-stack) | A short explanation of the technologies used. |
| [Project structure](#project-structure) | Where the important files live. |
| [Development conventions](#development-conventions) | A few rules that keep the code readable. |
| [Changing models](#changing-models), [Tests and CI](#tests-and-ci) | For developers changing the studio. |
| [Quick fixes](#quick-fixes) | Common setup problems and how to diagnose them. |

---

## Before you begin

You need two main tools:

### Visual Studio Code

**Visual Studio Code (VS Code)** is the code editor we use for TilTale. It lets you edit the project and run terminal commands in one place.

Download: <https://code.visualstudio.com/>

Recommended extension: **Python** (by Microsoft).

### Python

**Python** runs the TilTale studio on your own computer.

Installing Python also installs **pip**, which downloads and manages the project's dependencies.

Use **Python 3.12 or newer**.

### Development environment used for TilTale

| Software | Version / environment |
|---|---|
| Operating system | Windows 11 Pro |
| Python | 3.14 |
| Editor | Visual Studio Code |

TilTale can also be developed on macOS and Linux. Exact package versions are in `requirements.txt`.

---

## Install Python

Official download: <https://www.python.org/downloads/>

### Windows 11

1. Download the latest Windows installer.
2. Run it. **Tick "Add python.exe to PATH"** before pressing *Install Now*.
3. **Restart the PC.** Without a restart, `python` and `pip` are often not found in the terminal yet.
4. Open VS Code, then **Terminal → New Terminal**.

Check the installation:

```powershell
python --version
pip --version
```

Check where Python is installed:

```powershell
where.exe python
```

> **More experienced?**
>
> ```powershell
> winget install Python.Python.3.14
> ```

### macOS

1. Download the macOS installer from the Python website.
2. Install it and restart VS Code.

Check:

```bash
python3 --version
pip3 --version
which python3
```

### Linux

Most distributions ship Python. Make sure `venv` is available:

```bash
sudo apt install python3 python3-venv     # Debian / Ubuntu
```

Check:

```bash
python3 --version
which python3
```

---

## Get TilTale

### Easiest: the start_TilTale launcher

The repository root has one double-clickable launcher per operating system: `start_TilTale.bat`
(Windows), `start_TilTale.command` (macOS) and `start_TilTale.sh` (Linux). It shows a small to-do
window with **START** and **ABORT** buttons and a log panel (also written to `start_TilTale.log`)
and does everything below for you: it checks Python and Git (installing them when missing),
downloads TilTale into its folder (or, for an unpacked ZIP, connects it to GitHub without touching
the files), offers — but never forces — an update when a newer version exists, installs
`requirements.txt` into `.venv`, and then opens TilTale in the browser or in your editor.
Put the launcher in an empty folder (or run the one already in this folder) and press START.
The manual steps below do exactly the same, for people who prefer the terminal.

### Recommended: Download ZIP

This is the easiest option if you are new to Git.

1. Open the repository: <https://github.com/tiltale/tiltale-refactor>
2. Select **Code → Download ZIP**.
3. Unpack the ZIP.
4. Open VS Code.
5. Select **File → Open Folder...**.
6. Open the unpacked `tiltale-refactor` folder.
7. Select **Terminal → New Terminal**.

Check that you opened the correct folder:

```powershell
Test-Path manage.py
```

It should return:

```text
True
```

### More experienced? Use Git

```powershell
git clone https://github.com/tiltale/tiltale-refactor.git
cd tiltale-refactor
```

---

## Run TilTale

Create a private Python environment for the project (once), activate it, and install the exact dependencies from `requirements.txt`:

```powershell
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Then start the studio:

```powershell
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in your browser. Create a project there, or copy an existing `project/` folder next to `manage.py` first.

Stop the server with:

```text
Ctrl + C
```

Next time, only the activation and the `runserver` line are needed. The TilTale version is in `config/settings.py` (`TILTALE_VERSION`) and on the Help page; every generated page carries it in an HTML comment.

---

## Useful commands

Run these with the environment activated (`(.venv)` shows at the start of the terminal line).

| Command | What it does |
|---|---|
| `.venv\Scripts\activate` | Activates the project's Python environment (macOS / Linux: `source .venv/bin/activate`). |
| `pip install -r requirements.txt` | Installs the project's dependencies. |
| `python manage.py runserver` | Starts the local studio at <http://127.0.0.1:8000/>. |
| `python manage.py test` | Runs the behavior tests. |
| `python manage.py check` | Checks the Django configuration for problems. |
| `python manage.py makemigrations studio` | Writes a migration after you changed `studio/models.py` (see *Changing models*). |

Before committing or handing in work:

```powershell
python manage.py check
python manage.py test
```

---

## Daily workflow

1. **Develop**: add frames (**+ Add frame**, which explains each kind in one sentence), place components and images on them (click one to preview it first; see *Shortcuts* for moving and resizing), pick texts from `content.xlsx`, and set what each button does. Click a frame in the list to show it in the preview; **Edit** opens it. The preview only changes when you press **Regenerate**, which the status bar reminds you of. Large stories take a while: the terminal running `runserver` lists every image as it is converted.
2. **Flowchart**: see how frames connect. Click a frame to zoom to it. Drag frames to arrange them; positions are saved in the project database. `Shift`+click selects several frames to move together; **Tidy up** rearranges everything automatically.
3. **Regenerate**, then check the preview on different phone sizes.
4. **Test → Play-test** while you build: a robot plays every generated page to its end in a few seconds and shows pass/fail plus the full log of the run, so you see exactly where it got stuck.
5. **Test → Stress-test** before you publish: the same robot plays every page eight times under pretended bad conditions (slow or lost connection, blocked storage, a crash), and a checklist also shows what Regenerate warned about and what real phones reported. About a minute per page; red rows first. The Test page can also run only some languages, and can temporarily set “Element delay” to 0.01 s so the robot never waits for fades.
6. Upload `/project/dist/`. Later, download `dist/logs/` from the server and import the files under **Results**, which lists every visit with a readable timeline and draws visit counts, seconds per frame and the percentage that took each path onto the flowchart. Select one visit to see its own path highlighted.

The status bar at the bottom shows whether everything is saved and in the preview. It is checked on every page load, and turns red as soon as a background save (dragging an element or frame) fails.

## Shortcuts

On a Mac, use `Cmd` wherever this says `Ctrl`.

**Frame editor** (elements, images and the background image)

| Do this | To |
|---|---|
| Drag | move it. Its edges stick to the edges of other elements, shown by a blue line. |
| `Shift` + drag | move it only horizontally or only vertically, whichever way you drag furthest. |
| Drag a corner dot (appear on hover) | resize it from that corner; the opposite corner stays. Images and the background keep their proportions; components do not. Components that grow with their text (the `basic-*` ones) use this as their minimum height. |
| `Shift` + drag a corner dot | the opposite: distort an image freely, or keep a component's proportions. |
| Drag a pill in *(Re)order elements*, or its ⤒ / ⤓ hover buttons | restack the elements: the top of the list is the front layer; new elements start in front. The background shows as a locked pill at the very bottom: nothing goes behind it and it cannot move up. |
| Drag the black dot (bubbles only) | point the bubble's tail at a mouth or head. The bubble itself stays where it is. |
| Click an element or image, or `Tab` to it and press `Enter` | open its settings (text, exact size and position, colors, what a click does). |
| `Ctrl`+`Z` / `Ctrl`+`Shift`+`Z` | undo / redo a move or resize. The history covers the current page: it starts over after anything that reloads it, such as adding an element or saving settings. Inside a text field these keys undo typing instead. |
| *Add elements → + Component…* or *+ Image…* | pick from a preview grid (components say what they can do; images come from the Materials page), then **Add to frame** or, for images, **Use as background**. |
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

## Frame kinds

A frame's kind is chosen when it is created (**+ Add frame**) and cannot change afterwards. Each kind has a folder in `/frame-types/` with its name, the one-sentence description shown in the dropdown and the help shown at the top of its editor; what a kind *does* lives in the code (see `frame-types/README.md`).

| Kind | What it is |
|---|---|
| **Frame** | A normal page of the story: a background with elements. **Fade** is one setting with three options: *No fade in* (default), *Fade in from the previous frame* (a crossfade) and *Fade in from black* (the previous frame disappears first). Both fades take the *Element delay* from Settings; the flowchart shows a *Fade* or *Fade from black* badge. Documents can fade too. |
| **Picker** | A page of the language start page, only for stories with several languages (see *Several languages*). |
| **Document** | One image (a poster, a leaflet) that readers open, zoom, drag and close. Only its image and Close text are set; nothing is placed on it. Regenerate makes an extra 3840 px version so it stays sharp when zoomed. It opens as large as the screen allows: a portrait poster fills a phone's height. The Close text is a row of `content.xlsx` (empty for a plain ×). In the flowchart, documents are blue and sit right above the frame that opens them, joined by a two-way arrow; Results counts how often a visit opened one instead of a percentage. |
| **Validation point** | Never shown to readers: its rules look at the global variables and send the reader on (below). Purple, rounded, in the flowchart. |
| **Minigame** | A frame with a teal badge, reserved for embedded games. For now it behaves like a normal frame; the folder is there so a game can be built onto it later. |

## Global variables, validation points and scoreboards

Variables let a story remember what a reader did: count correct answers, remember which path was taken, and later route the reader accordingly.

1. **Define** them under **Settings → Advanced**. A variable has a name (`score`, `path_taken`) and an initial value. The initial value decides its type once and for all: `0`, `2.5` or `-3` make a number, anything else makes a text; put a number in quotes (`"12"`) to make it a text.
2. **Change** one from any clickable element: in its dialog, choose the variable and either *Set to* a value or *Add* a number to it. The click can also lead somewhere, or only change the variable and stay on the frame. The studio refuses updates that do not fit the type (adding to a text, setting a number to `lots`), and the preflight list on Develop repeats every such problem.
3. **Route** readers with a **Validation point**: an ordered list of rules such as *score is at least 3 → Good ending*, ending in an *otherwise* row. The first rule that matches decides; readers never see the point itself. Comparisons `<`, `≤`, `>`, `≥` only exist for numbers.
4. **Show** values with a scoreboard: any text may contain `{score}`, which is replaced by the current value and updated the moment it changes. The four `scoreboard-*` components exist for this; **Settings → Advanced → Scoreboard on every frame** puts one on all story frames at once, with a checklist to hide it on some, and the element is then moved and resized in any frame editor like an ordinary element. See `components/README.md`.

Every variable change and every decision is logged as its own line, is readable in a visit's timeline under **Results** (`score: 0 → 1`, `Check: score is at least 1 → Good ending`), and Results shows the final values of each visit and how many readers took each rule.

**Restart the story** is a target like *End story*: it forgets this browser's progress, including the variables, and opens the story's first page again (the language start page if there is one), keeping the participant ID.

## Editing texts

Texts still live in `/project/content.xlsx`, but the workbook never has to be opened: the **Content** page shows every row (all languages side by side, with how many elements use it), saves changes row by row without a reload, and adds new rows. The **Materials** page uploads (click the + tile, or drop files) and deletes the images of `/project/materials/` (deleting warns when an image is still used somewhere), and the Content page picks each component's font from a fixed set, with a live preview. A single row can also be changed from an element's dialog (**Edit text #N**). A row keeps its id, so every element that uses it changes with it. Line breaks are kept: press Enter in the studio, or Alt+Enter in Excel, and the story shows the lines with a little space between them.

## Frame names

Every frame has two labels:

| | Example | Used for | Changes? |
|---|---|---|---|
| **ID** | `fnr-12` | the story's code, preview links, study logs, LLM answers | never; numbers of deleted frames are not reused |
| **Name** | `Frame 12` (default), `Intro scene` | you, in the studio | rename freely in the frame editor |

A new frame's default name repeats its ID number. Names must be unique, ignoring capitals, spaces, `-` and `_` (`Frame 12` is refused when `frame_12` exists), and need at least one letter (a–z) or digit. The visit log pages show each ID with the frame's current name.

## Logo and favicon

`branding/logo-tiltale.png` (startup screen) and `branding/favicon.ico` (browser tab) are used for every generated story. To use a different one for **one project**, put a file with the same name in `/project/`, for example `/project/logo-tiltale.png`, and press Regenerate. Delete it to go back to the default. The studio itself always shows the TilTale files from `/branding/`.

## Fonts

The **Content** page picks each component's font from a fixed set of stacks, with a live preview; hand-edited stacks show there as *Custom* and are left alone. Behind it, the top of `/project/style-overrides.css` is a **Fonts** block with one line per component (`.component-basic-narrator { font-family: … }`). Change the names between the braces; to give two components the same font, give them the same line. The block is written when a project is created (from the optional `"font"` in each `component.json`); a project made before 2.3 does not have it yet: add the lines you need in the same form.

A browser uses the first font in the list that the device has installed, and phones, tablets and computers have different fonts installed. Never end a list with `cursive`, `fantasy` or `monospace`: Android maps `cursive` to a small handwriting face, so a line that reads fine on Windows (Comic Sans MS) turns into cramped italics on a phone. End with `sans-serif` or `serif` instead, which every device maps to a plain readable font. A story only looks the same everywhere with its **own font file**: put a `.woff2` (or `.ttf`) in `/project/fonts/`, uncomment the `@font-face` example line in the block, and use its name in the component lines. Regenerate copies `/project/fonts/` into `/dist/fonts/`. (The studio's frame editor keeps showing installed fonts; the generated story uses the file.)

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
| any story link with `&restart` added, e.g. `…/nl-NL/index.html?ppn=R_1abcDEF&restart` | The same, for one specific page. TilTale removes `restart` from the address once it has been handled, so a later refresh continues normally. |

A restart (also the *Restart the story* element) is a new page load, so it starts a new visit with its own log file, but it does not download the story again: images already on the device are reused (see the next section).
- **Finish redirect**: under Settings, enter a URL to open when a reader clicks an element set to *End story*. Write `{ID}` where the participant ID belongs. It is URL-encoded automatically. Example: `https://example.qualtrics.com/jfe/form/SV_abc?ppn={ID}` sends participant `R_1abcDEF` back to `…?ppn=R_1abcDEF`. `{ID}` was chosen because curly braces never appear in normal URLs, while `%` and `@` already mean something there. The redirect waits until every log line of the visit is on the server (the survey needs a connection anyway); after two seconds of waiting the reader sees *Saving… please keep this page open*.

## Loading, full screen and a lost connection

**Loading.** Before the first frame, the story downloads every image it will show (the size that fits the reader's screen) and keeps them in memory. The startup screen shows the bouncing logo with a progress bar and percentage underneath (*Loading story… 42%*; the text is in `runtime/index.html`). On HTTPS the browser also keeps the images in its cache storage, so a restart, a second language chosen later, or a returning reader does not download them again; the log line `Loading IDN – completed (12.3 MB, 12.3 MB already on this device)` shows how much was reused. A multilingual story downloads one language at a time: the one the reader picks.

**Full screen.** A round button in the top-right corner puts the story in full screen. It appears together with the first frame (not on the startup screen), fades away four seconds later, and comes back when the reader taps the area *beside* the frame (the letterbox), not the frame itself, so it does not flash up at every click in the story. Turning the device keeps full screen; a restart or choosing a language loads a new page, which every browser leaves full screen for, so the story re-enters it at the reader's first tap. iPhones do not offer full screen to web pages, so the button is not shown there (iPads and Android phones are fine). The studio's preview has no button.

**A lost connection.** Because everything is in memory, the reader can keep playing. Every log event is first written to a queue on the device (kept in the browser's local storage), then sent in the background, up to 25 events per request; a failed send is retried a few seconds later, at the next event, when the browser reports it is online again, and at the next visit in that browser. Nothing is lost as long as the reader either reaches *End story* with a connection (the redirect waits for the upload) or opens the story again on that device. A restart while offline still needs the connection for the (small) page itself. An image that could not be downloaded is noted in the log (*Image not downloaded*) and shown from the server when its frame opens.

**Offline classroom use.** A published story (HTTPS) can be prepared for a day without wifi, for example a teacher running the story on tablets outside: open `<root>/offline/` on each device **while online** and press **Download everything**. Every language's pages and images are stored on the device (a service worker, `dist/sw.js`, serves them when there is no connection), so the story opens, restarts and replays offline as often as needed — use the story's *Restart* element between students. Every session is logged into the queue on the device (room for thousands of events); back online, opening the story — or the **Upload now** button on the same `offline/` page, which also shows how many events are still waiting — sends every session's log to the server, each visit into its own file. The service worker never gets in the way of updates: pages and code are always fetched from the network first, and the cached copy answers only when the network does not.

**A browser that is too old.** Stories run on iOS Safari 13 and Chrome 61 or newer (phones from about 2015 on). An older browser gets the message *This browser is too old to play this story* instead of a blank page, and the server gets one log line (`Browser not supported`, participant `unsupported`, with the browser's name) so the study knows it happened.

**A crash.** Any JavaScript error in a story is written to its log (`error`, with message, file and line) and shows up under Results, in the visit's timeline and in the *Devices seen* table, so a problem that only one phone has can be found afterwards.

## The Test page

One **Test** page runs both kinds of check — choose **Play-test** or **Stress-test** before pressing Run, tick which pages (languages) to test, and optionally speed the run up by temporarily setting “Element delay” to 0.01 seconds (the story itself is unchanged). Both modes use the same robot: it plays a generated page like a reader, waits for delays, clicks buttons (preferring frames it has not seen) and stops at *End story*. It fails on a button that leads nowhere, a loop, a JavaScript error, a minute without a new frame, or log events that never reach the server.

| | Play-test | Stress test |
|---|---|---|
| When | While building, after every Regenerate | Before publishing, and after big changes |
| Runs | Once per page, a few seconds | Eight times per page under pretended bad conditions, about a minute per page |
| Shows | Pass/fail per page and the full log of the run: where exactly it got stuck | A checklist, red rows first; each row says what to do. The page explains the rows |
| Leaves under Results | One `playtest-…` visit per page | Eight per page (exclude them with the filter there) |

The stress test cannot pretend a real phone. To add one: open the story on the phone with `?autoplay` added to the address (`https://your-host/story/?autoplay`); it plays itself to the end and its visit lands under **Results**, where the *Devices seen* table lists every phone with its visits, finished visits and errors, and where the Test page counts it. Borrow the oldest phone in the group, a current iPhone and Android, a tablet; rotate the phone mid-story; turn wifi off for a few frames and on again; try a private window. A phone that is too old (before iOS 13 or Chrome 61) shows *This browser is too old to play this story* instead of a blank page and leaves a `Browser not supported` line in the logs. Phones you do not own: BrowserStack and LambdaTest offer a free tier with real older devices.

Any pretended condition can also be typed into a story's address, for example `?stress=slow,no-storage`; the list is at the top of `runtime/tiltale.js`.

## Protecting logs

`ETHICS.md` lists exactly what a story records (every log line, the participant ID, what stays on the reader's device, including the story's own images) in the words an ethics or data-management application needs. Read it before you plan a study. The first line of every log also names the TilTale version that made the story (`tiltale_version`), so a log can always be traced to a build.

Study logs are readable JSON on the web server unless you turn on **Settings → Advanced → Protect logs**. That generates a key pair for the project **once**: the public key goes into `/dist/log-key.pem` and `log.php` then encrypts every line it writes; the private key is offered to you a single time as `<project>-log-key.pem` and the studio stays closed until you confirm you have stored it. Results asks for that file every time you open it and keeps it only in memory for the browser session. There is no second chance and no replacement key: lose the file and the logs are gone. `log.php` needs PHP's `openssl` extension for this; without it, it refuses to write rather than writing readable lines.

## Several languages

Languages are the columns after `content_id` and `note` in `/project/content.xlsx`. With **one** language, the story is `/dist/index.html` and none of the options below exist. With **two or more**:

```
dist/index.html               start page built from language-picker frames (optional)
dist/en-US/index.html         the English story
dist/nl-NL/index.html         the Dutch story
dist/tiltale.js, style.css, assets/, log.php, logs/, restart/   shared by all pages
```

**Picker frames** (**+ Add frame → Picker**) are the frames of the start page. They are shown before a language is chosen, so their texts are typed directly instead of coming from `content.xlsx`, and their buttons open a language. They have an amber dashed border and a *Picker* badge everywhere in the studio. Without picker frames, no `dist/index.html` is generated and you link participants to a language folder directly. The participant ID and the visit carry over from the start page into the chosen language.

## Publishing

Upload the **contents** of `/project/dist/` to a folder on a web server with PHP 7.4 or newer.
Old links keep working: when a language folder is renamed or removed, Regenerate leaves a small page
at the old address that forwards readers (with their participant ID) to the start page, and
`dist/.htaccess` tells browsers never to keep an outdated copy of the story's pages and code.
Progress saved on a reader's device is untouched by this. `log.php` writes to `dist/logs/`, so that folder must be writable by the web server. `logs/.htaccess` blocks public access on Apache; on nginx add `location ~ /logs/ { deny all; }`. Regenerate never deletes `dist/logs/`.

---

## Tech stack

You do not need to know these tools before you begin.

| Technology | What it does |
|---|---|
| **Python 3** | Runs the studio. |
| **Django** | The web framework behind the studio: pages, forms, the database of frames and elements. |
| **SQLite** | The project database, one file: `project/project.sqlite3`. |
| **openpyxl** | Reads and writes `content.xlsx`, where all story texts live. |
| **Pillow** | Resizes the story's images for phones and desktops during Regenerate. |
| **Plain HTML, CSS and JavaScript** | The studio's pages and the generated story use no frontend framework and no build step. |
| **PHP** (only on the web server) | `log.php` stores the visit logs of a published story. |

Exact installed versions are recorded in `requirements.txt`.

---

## Project structure

Most changes start in one of these places:

| I want to change… | Open |
|---|---|
| a studio page's behavior | `studio/views.py` (the function named in `studio/urls.py`) |
| the wording of a frame kind | `frame-types/<kind>/frame-type.json` |
| a studio page's layout | `studio/templates/studio/<page>.html` |
| how the studio looks / reacts | `studio/static/studio/app.css`, `app.js` |
| how the published story behaves (loading, full screen, logging, fades) | `runtime/tiltale.js` |
| the rows of the Test page's Stress-test, or what the story can pretend | `studio/services/stresstest.py` (`ROBOT_CHECKS`) and `?stress=` at the top of `runtime/tiltale.js` |
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
| `models.py` | Database tables: project settings, frames (with their kind), elements, rules of validation points, global variables, per-language layout overrides. |
| `views.py` | One function per page or API call. Validates input, then calls a service. Also computes the status bar (`status_context`). |
| `urls.py` | Maps each URL to a view. |
| `forms.py` | Forms for new project, settings and frame settings, including their help texts. |
| `db.py` | Routes all studio tables to `/project/project.sqlite3`. |
| `tests.py` | Behavior tests (`python manage.py test`). |
| `migrations/` | Generated by Django. Never edit by hand (`0006` is the one exception: it also converts old picker/zoomable frames into kinds; see *Changing models*). |
| `services/project.py` | Creating, opening and checking the `/project/` folder; applies migrations automatically. |
| `services/content.py` | Reading, appending and changing rows of `content.xlsx`. |
| `services/variables.py` | Pure rules for global variables: number or text, allowed operations and comparators, `{placeholder}` checks. |
| `services/frame_types.py` | Loading `/frame-types/*`. |
| `services/components.py` | Loading `components/*`. |
| `services/flow.py` | Frame links, reachability, placing new frames, *Tidy up*. |
| `services/validate.py` | Preflight checks and phone presets. |
| `services/generate.py` | Regenerate: builds `/project/dist/`. |
| `services/study_logs.py` | Writing, importing and summarizing visit logs; seconds per frame, device summary and readable event lines for Results. |
| `services/log_keys.py` | The project key pair: generating, encrypting (the same scheme as `log.php`), decrypting and unlocking Results. |
| `templates/studio/` | One HTML template per page; `base.html` is the shared frame, `_field.html` renders a form field, `_flow.html` and `_flow_inspector.html` are the flowchart canvas shared by Flowchart and Results. |
| `static/studio/app.css`, `app.js` | All studio styling and interactivity (no libraries). |

### `runtime/`: files copied into every generated story

See `runtime/README.md` for the full table. `tiltale.js` is the story player, `log.php` the server-side logger.

### Repository root

| File | Purpose |
|---|---|
| `branding/` | Default startup logo (`logo-tiltale.png`), browser-tab icon (`favicon.ico`) and the project logo (`logo.png`) of every story (see *Logo and favicon*). |
| `frame-types/` | One folder per frame kind with its name, description and help (see *Frame kinds*). |
| `manage.py` | Django's command-line entry point (`runserver`, `test`, `makemigrations`). |
| `requirements.txt` | Python packages (Django, openpyxl, Pillow, cryptography). |
| `ETHICS.md` | What a story records and where it goes, for ethics and data-management applications. |

### `components/`: reusable story elements

One folder per component with `component.json` (name, defaults, colors), `component.svg` (shape) and `component.css` (styling). See `components/README.md`.

### `docs/llm-prompts/`: default prompts for language models

The two prompts described in *Building with a language model*, plus `content-template.xlsx`. See `docs/llm-prompts/README.md`.

### Generated folders (ignored by Git)

| Folder | Contents |
|---|---|
| `project/` | Everything you make: `project.sqlite3`, `content.xlsx`, `materials/` (images), `logs/` (visits), `default-colors.css`, `style-overrides.css` (starts with the Fonts block), optionally `fonts/` (your own font files) and your own `logo-tiltale.png` / `favicon.ico`. Back this up. |
| `project/dist/` | The website produced by Regenerate. Safe to delete except `dist/logs/` on the server. (Before v2.0.10 this was `/dist/` in the repository root; that folder can be deleted.) |

## Development conventions

To keep TilTale understandable for everyone:

- Prefer readable code over clever code, and the smallest change that does the job.
- Use type hints in Python; keep functions short and named after what they do.
- Keep the story player (`runtime/tiltale.js`) in plain ES5 JavaScript, so old phones can run it; a test and the Test page check this. The studio (`app.js`) may use modern JavaScript.
- Put reusable logic in `studio/services/`; views only validate input and call a service.
- Do not edit `project/`, `project/dist/` or `studio/migrations/` by hand (see *Changing models*).
- Add or adjust a test in `studio/tests.py` when you change behavior.

---

## Changing models

After editing `studio/models.py`:

```bash
python manage.py makemigrations studio
git add studio/migrations
```

Django writes the migration; never write one by hand. TilTale applies pending migrations to `/project/project.sqlite3` automatically on the next request. CI fails if a model change has no committed migration.

The one exception so far is `0006_frame_kinds_variables_rules`, which adds a `RunPython` step to the generated file: it turns the old *picker* and *zoomable* flags into a frame kind, makes each zoomable frame's image the document's image, and switches word-breaking off for every element. Projects made before 2.1 are converted the first time the studio opens them; there is no way back to 2.0.

## Tests and CI

`python manage.py test` runs the behavior tests against an in-memory database, including a check that `runtime/tiltale.js` and `runtime/bubbles.js` contain no JavaScript newer than ES5 (`const`, `=>`, template strings…), so old phones can still run them; the Test page shows the same check. GitHub Actions (`.github/workflows/tests.yml`) runs Django's checks, the migration check, the tests, a syntax check of `tiltale.js`, `app.js` and `log.php`, and, on pull requests, fails when `TILTALE_VERSION` in `config/settings.py` was not bumped.

---

## Quick fixes

### `python` or `pip` is not recognized

Restart the PC (Windows) or VS Code, then run:

```powershell
python --version
pip --version
```

On Windows, check whether Python can be found:

```powershell
where.exe python
```

If nothing is returned, reinstall Python and tick **Add python.exe to PATH** in the installer.

---

### PowerShell says `activate.ps1` cannot be loaded

Use the command-prompt version of the activation script instead:

```powershell
.venv\Scripts\activate.bat
```

This avoids changing your PowerShell security settings.

---

### You are in the wrong folder

Check your current location and whether `manage.py` is there:

```powershell
Get-Location
Test-Path manage.py
```

Expected: `True`.

---

### `ModuleNotFoundError: No module named 'django'`

The environment is not activated, or the dependencies are missing:

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py runserver
```

---

### `Error: That port is already in use`

Another `runserver` is still running. Stop it with `Ctrl + C` in its terminal, or start on another port:

```powershell
python manage.py runserver 8001
```

---

### The preview says "Not built yet" or the status bar is amber

Press **Regenerate** on the Develop page. The preview only changes when you do; the terminal running `runserver` shows the progress.

---

### Asking for help

Include the output of:

```powershell
python --version
python manage.py check
python manage.py test
```

Also include the **first error message** shown in the terminal, and the TilTale version from the Help page.

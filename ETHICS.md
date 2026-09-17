# TilTale in your study: ethics, data management and GDPR

This document describes what TilTale records about the people who read a story, where that data goes, and how it is protected, so that you can fill in an ethics / data-management application (such as the TSHD *Application Form: Ethics Review / Data Management / GDPR*) without reading the source code. 

TilTale is developed at the Department of Communication and Cognition (DCC), Tilburg University, by **Jan de Wit** (owner) and **Jonas de Brouwer** (co-developer). The code is in this repository; there is no TilTale company, cloud service or account. You run the studio on your own computer and host the generated story on a simple web server of your choosing.

## 1. What TilTale is

TilTale is a studio that turns frames, images and texts into an *interactive digital narrative* (IDN): a plain website in which readers tap through a story and choose what happens next. The website is generated as static files (`/project/dist/`) plus one small PHP script (`log.php`) that appends the reader's actions to a log file on your web server. Readers need nothing but a browser; there is no app to install, no account, no cookies and no third-party service. The researcher later downloads the log files from the server and opens them in the studio (**Results**), which shows each reader's path through the story, the time spent on each frame, and any scores the story keeps.

## 2. What is recorded, and when

Logging happens only in the published story (and, on the researcher's own computer, in the studio's preview and play-test). One JSON line per event is appended to a file per visit; a *visit* is one page load. The file is named `<participant ID>--<visit ID>.jsonl`, so the participant ID is visible in the file name even when the contents are encrypted (section 4).

Every line carries: the participant ID, the visit ID (the start time in UTC plus four random characters), a sequence number, the timestamp (UTC, from the reader's device clock), the project slug, the story language (if a language has been chosen), the event name, and `received_at` (the server's UTC time).

| When | Event | What is added |
|---|---|---|
| The story is opened (first line of every log) | `visit` | The reader's local date and time with their UTC offset; screen size and pixel ratio; browser-window size; whether the device has a touch screen; the browser's *user-agent* string; the TilTale version that made the story; and, where the browser offers them, its platform (e.g. `Android`), whether it calls itself mobile, and its brand names with versions (e.g. `Chrome 131`). No IP address, no browser language, no location. |
| The story starts loading / has loaded | `Loading IDN – started`, `Loading IDN – completed (n MB, m MB already on this device)` | Bytes of the story, and how many of them were already on the device from an earlier visit or restart. |
| A reader returns to an unfinished story | `Resumed` | The language they had chosen. |
| A frame is shown | `frame` | Which frame, and how it was reached (`start`, `resumed`). *Time on a frame* is not logged as such: Results computes it as the seconds between one `frame` line and the next. |
| A button or other clickable element is tapped | `choice` | The frame, the element's id, its component, the id and text of the text it showed, and what it leads to (the next frame, a language, `end` or `restart`). Closing a document logs a `choice` with component `close`. |
| A tap changes a global variable (e.g. a score) | `variable` | The variable's name and its value before and after. |
| A validation point routes the reader | `decision` | Which rule matched, the frame it led to, and the value of every global variable at that moment. |
| An *End story* element is tapped | `Story finished` | The frame. |
| A play-test by the studio's robot ends | `Play-test ended` | Whether it succeeded and why. Only in the researcher's own play-tests. |

In short, per participant you get: the participant ID; date and time; device type (screen size, and brand/model as far as the browser says so, e.g. `SM-G991B`), browser and version; the chosen story language; every frame seen and for how long; every button pressed and where it led; and every change of a score or other variable. That matches the list in the TSHD form's *summary* and *procedures* sections; there is nothing else.

### The participant ID

- If the link carries the participant parameter (`?ppn=…` by default; the name is set under **Settings → Advanced**), that value is the participant ID. This is how Qualtrics or Prolific IDs travel into the logs. TilTale does not check or interpret it.
- Without it, the browser makes a random ID (`anon-` plus 16 hexadecimal characters) and keeps it in the browser's local storage, so a reader who returns on the same device and browser keeps the same ID. Different devices get different IDs.
- With a **finish redirect** (Settings → Advanced), the participant ID is inserted into the URL the reader is sent to after *End story* (where you wrote `{ID}`), e.g. back to a Qualtrics survey. Nothing else is passed along.

Whether the participant ID is personal data depends on your study: a Qualtrics or Prolific ID is a pseudonym that you (or the platform) can link to a person; a random `anon-…` ID cannot be linked to anyone by TilTale.

### What is stored on the reader's device

Only in the browser's local storage, only for this story, and only so that a reader can continue after closing the browser or losing the connection: the participant ID; the current frame, the previous frame (for closing a document), the chosen language and the current values of the global variables; and the queue of log lines not yet on the server. Every log line is written to that queue first and sent from there in the background, one at a time; a lost connection only delays the sending (it is retried while the story is open and again at the next visit in that browser), and the redirect after *End story* waits until the queue is empty. Besides this, the story's own images are downloaded in full before the first frame and, on HTTPS, kept in the browser's cache storage so that a restart does not download them again; they are the story, not data about the reader. No cookies are set. The `…/restart/` link and a `&restart` parameter clear the progress (not the unsent log lines, which are still sent, and not the cached images).

## 3. Where the data goes

1. **The reader's browser → your web server.** Each event is sent by HTTPS/HTTP `POST` to `log.php` in the story folder on *your* server. `log.php` appends it to `dist/logs/<participant ID>--<visit ID>.jsonl`. It records the time it received the line; it does not record the IP address or any request headers. The web server itself normally keeps its own access log (IP address, time, URL), which is outside TilTale: ask your hosting provider or ICT department what is kept and for how long.
2. **Your web server → your computer.** You download `dist/logs/` yourself (SFTP, the hosting panel, …) and import the files under **Results**. The studio copies them into `/project/logs/` on your computer, unchanged. Regenerating the website never deletes `dist/logs/` on the server; deleting logs from the server is a manual step you plan yourself.
3. **Your computer.** The studio runs locally (`python manage.py runserver`); nothing is sent anywhere. `/project/` (the story, its database, materials and logs) is excluded from Git by `.gitignore` so that it is not published by accident.

No data leaves this chain. TilTale contacts no other server, uses no analytics and loads no external fonts or scripts in the published story. Readers' devices only talk to the server that hosts the story.

For the form's *tools used for data collection*: "Online, other: an interactive story built with TilTale (open-source, Tilburg University, DCC) and hosted on <your server>". For *external parties (processors)*: only your hosting provider, if the server is not the university's.

## 4. Protecting the logs: the project key

By default `log.php` writes readable JSON. If you enable **Settings → Advanced → Protect logs**, TilTale generates a key pair for the project **once**:

- The **public key** is stored with the project and copied into the website as `dist/log-key.pem`. From then on `log.php` encrypts every line before writing it: a fresh AES-256-GCM key per event, wrapped with the project's RSA-3072 public key (RSA-OAEP). A copied, leaked or backed-up `dist/logs/` folder is unreadable without the private key. The file *names* (participant ID and visit ID) are not encrypted.
- The **private key** is shown to you exactly once, as a download (`<project>-log-key.pem`). The studio is closed until you confirm that you have stored it; after that it is not kept in the database, the project folder or the website. Store it where your data management plan says raw data may live (e.g. the university's protected network drive), never next to the logs on the server and never in Git. Without this file the logs cannot be read by anyone, including the developers.
- **Results** asks for the key file every time you open it. The key is held only in the studio's memory for that browser session; closing the browser or restarting the studio locks Results again. Imported logs stay encrypted on disk in `/project/logs/`.
- A project has one key for good; it cannot be replaced or regenerated. The studio's own preview and play-test logs (participant IDs starting with `preview-` and `playtest-`) are not study data and are written unencrypted.

`log.php` needs PHP's `openssl` extension for this (present on almost every host); if it is missing, `log.php` refuses to write instead of writing readable lines. The scheme is implemented in `runtime/log.php` and `studio/services/log_keys.py` (Python package `cryptography`).

For the form's *data storage* rows this gives you: raw data = the encrypted log files on the server and, after download, in `/project/logs/`; access to raw data = whoever holds the key file; the studio reads them only on the computer of that person.

## 5. What TilTale does not do

- It does not record IP addresses, names, e-mail addresses, locations, keystrokes, free text typed by readers, audio, video or photographs. Readers cannot type anything into a story.
- It does not identify a person across devices, does not fingerprint, and does not set cookies.
- It has no user accounts, no login and no cloud component; there is no data at Tilburg University or at the developers unless you send it there.
- It does not delete anything on its own: logs on the server and in `/project/logs/` stay until you remove them.
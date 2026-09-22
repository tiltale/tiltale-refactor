# Story runtime

Framework-free files that every generated story uses. Regenerate copies them into `/project/dist/`.

| File | What it does | Edit it when… |
|---|---|---|
| `index.html` | Page shell with startup logo and progress bar (*Loading story… 42%*), the zoom controls of document frames, the full-screen button and the TilTale version. `__ROOT__`, `__TITLE__`, … are filled in by Regenerate. | you need extra `<meta>` tags, or another loading text. |
| `restart.html` | Becomes `<root>/restart/index.html`: forgets the browser's progress and reopens the story with the same parameters. | the restart link should behave differently. |
| `sw.js` | Service worker for offline use: images cache-first, pages and code network-first (a republish still updates), `log.php` untouched. Registered by `tiltale.js` on HTTPS. | offline behavior changes. |
| `offline.html` | Becomes `<root>/offline/index.html` (Regenerate fills in the project and its pages): downloads every language onto the device and uploads the queued logs of past sessions. | the teacher-facing offline page changes. |
| `tiltale.js` | The whole story player: a check that the browser is new enough (else a message and one log line), downloading every image before the first frame (kept in memory and, on HTTPS, in the browser's cache storage), scaling, frame kinds (frames, documents, invisible validation points), frame fades (crossfade or from black, lasting the element delay), clicks, global variables and `{placeholders}`, zoom/drag of documents, full screen, participant IDs, queued logging that survives a lost connection, every JavaScript error into the log, finish redirect (after the queue is sent), restart, play-test robot, pretended bad conditions (`?stress=`, used by the studio's Test page), a temporary delay override for the robot (`?delay=`), and registering the service worker on HTTPS. Must stay ES5: a test and the Test page check. | the story should *behave* differently. |
| `bubbles.js` | Draws the bodies and tails of bubble components (`"tail"` in `component.json`) in pixels, so borders never scale. Also used by the frame editor. | a bubble shape or tail should look different. |
| `style.css` | Page scaling, letterboxing, startup screen with progress bar, full-screen button, notices. | the story page should look different for every project. Per-project tweaks (and the Fonts block) go in `/project/style-overrides.css`. |
| `elements.css` | How placed elements look (position, text box, fade). Also used by the studio's frame editor, so both always match. | every element should look different. |
| `log.php` | Appends each event (one per request, or a list of them) to `dist/logs/<participant>--<visit>.jsonl` on the web server; encrypts them first when `log-key.pem` is next to it (see `ETHICS.md`). | the log format or storage changes. |

The startup logo and browser-tab icon are not here: see *Logo and favicon* in the main README.

Project content never lives here: it comes from the project database, `content.xlsx`, `/project/materials/` and the project CSS.

## Log events

Every event has `participant_id`, `visit_id`, `seq`, `timestamp`, `project`, `language` and `event`. Events are queued on the device and sent oldest first, up to 25 per request (`log.php` accepts one event or a list of them), so a line may arrive long after its `timestamp` (`received_at` says when); `seq` gives the order. The story-specific ones:

| `event` | Extra fields | When |
|---|---|---|
| `visit` | `local_time` (with UTC offset), `screen`, `window`, `touch`, `user_agent`, `tiltale_version`, `platform`, `mobile`, `brands`, `connection` (`4g`, `3g`…; Chrome and Android only), `stress` (the pretended conditions, else null) | The first line of every log file: the reader's clock, screen, browser and the TilTale version that made the story. |
| `Browser not supported` | `missing` (the APIs it lacks), `user_agent`, `tiltale_version` | The only line of a visit by a browser too old for the story (participant `unsupported`): it got a message instead of the story. |
| `error` | `message`, `file`, `line` | A JavaScript error happened in the story. A play-test fails on it; Results shows it in the timeline and under *Devices seen*. |
| `Image not downloaded` | `path`, `message` | An image did not download before the first frame; it is shown from the server when its frame opens (and may be missing offline). |
| `Loading IDN – started`, `Loading IDN – completed (…)` | `bytes`, `cached_bytes` | Before and after the download of all images; `cached_bytes` were already on the device (restart, returning reader). |
| `frame` | `frame`, `how` (`start`, `resumed`, `studio-view`) | A frame (or document) is shown. Validation points never log this. |
| `choice` | `frame`, `element_id`, `component`, `content_id`, `text`, `target` (`fnr-…`, a language, `end` or `restart`) | A clickable element was clicked (`component: "close"` for a document's Close button). |
| `variable` | `frame`, `element_id`, `variable`, `from`, `to` | A click changed a global variable; always its own line. |
| `decision` | `frame`, `element_id` (`rule-7`, the rule that matched), `rule` (its text), `target`, `variables` (all values at that moment) | A validation point sent the reader on. |
| `Story finished` | `frame` | An “End story” element was clicked. |

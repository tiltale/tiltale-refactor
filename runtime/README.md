# Story runtime

Framework-free files that every generated story uses. Regenerate copies them into `/dist/`.

| File | What it does | Edit it when… |
|---|---|---|
| `index.html` | Page shell with startup logo. `__ROOT__`, `__TITLE__`, … are filled in by Regenerate. | you need extra `<meta>` tags. |
| `tiltale.js` | The whole story player: scaling, frames, clicks, participant IDs, logging, finish redirect, play-test robot. | the story should *behave* differently. |
| `style.css` | Page scaling, letterboxing, startup screen, notices. | the story page should look different for every project. Per-project tweaks go in `/project/style-overrides.css`. |
| `elements.css` | How placed elements look (position, text box, fade). Also used by the studio's frame editor, so both always match. | every element should look different. |
| `log.php` | Appends each event to `dist/logs/<participant>--<visit>.jsonl` on the web server. | the log format or storage changes. |
| `logo-tiltale.png` | **Required.** Startup logo (shown ≥ 3 s and until the story is loaded). | the branding changes. |
| `favicon.ico` | Optional browser-tab icon. Copied into `/dist/` when present. | — |

Project content never lives here: it comes from the project database, `content.xlsx`, `/project/materials/` and the project CSS.

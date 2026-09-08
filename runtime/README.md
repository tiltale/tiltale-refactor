# Generated story runtime

These three files are the **generic, framework-free** runtime copied into every language build in `/dist/`.

- `index.html` is the smallest browser shell.
- `style.css` handles scaling, letterboxing, frames and element timing.
- `script.js` receives a generated `STORY` object, preloads the story, resumes a session and logs interactions.

Do not put project content here. Project content comes from SQLite, `content.xlsx`, materials and project CSS during regeneration.

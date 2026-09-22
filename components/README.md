# Components

A **component** is a reusable source definition in this folder. An **element** is one component placed on a frame (stored in the project database).

Each component is one folder. **The folder name is the slug**: it must match the `.component-<folder-name>` class in the CSS.

| File | Purpose |
|---|---|
| `component.json` | Name, description, whether it shows text (`accepts_content`), whether it is clickable (`clickable`), default size/font size and default colors. Optional: `font` (its own `font-family` list; without it the page font), `auto_height`, `tail` and `scoreboard` (below). |
| `component.svg` | The vector shape. Give shapes CSS classes instead of hard-coded colors. |
| `component.css` | Colors and hover behavior through CSS custom properties. |

## Shapes that keep their line width (the `basic-*` components)

An SVG **with** a `viewBox` (like `next-button`) is stretched to the element's size, which distorts corners and strokes on non-square elements. An SVG **without** one draws in element pixels: use `width="100%" height="100%"` for the body, fixed `rx`, and a fixed `stroke-width`. Set `--shape-inset` in the CSS to half the stroke width so the stroke ends exactly at the element's edge, and `--text-padding` for the space between border and text. Fixed-size decorations (like the arrow in `basic-next-text`) go in a nested `<svg x="100%" y="50%" overflow="visible">`.

Two optional keys in `component.json`:

| Key | Effect |
|---|---|
| `"auto_height": true` | The element grows with its text; the height in the editor is its minimum height. The text stays centered. |
| `"tail": "speech"`, `"thought"` or `"scream"` | `runtime/bubbles.js` draws the tail (and, for thought and scream, the whole outline) into `<path class="bubble-body">` and `<path class="bubble-tail">`. In the editor, drag the black dot to point the tail at a mouth or head; the body does not move. The tip is saved per element (`tail_x`, `tail_y`, relative to the element's center). |

Colors, borders and text colors of every `basic-*` component are in `/project/default-colors.css`, like any other component.

## Scoreboards and global variables (the `scoreboard-*` components)

Any element text may contain the name of a global variable in curly braces: `Score: {score}`. The story player replaces it with the variable's current value and re-renders the text the moment the variable changes, so a reader who clicks a button that adds a point sees the new number at once. Unknown names stay as written (the dashboard warns about them). Variables are defined under **Settings → Advanced**; see `frame-types/README.md` for how buttons change them and how validation points use them.

The four `scoreboard-*` components (pill, panel, star, ticket) are ordinary components with one extra key in `component.json`:

| Key | Effect |
|---|---|
| `"scoreboard": true` | The component is listed under **Settings → Advanced → Scoreboard on every frame**, where one click puts it on every story frame at once (stored as an element without a frame, plus the list of frames where it is hidden). It can still be added to a single frame like any other component. |

A scoreboard's text is a row of `content.xlsx` like any other text, so it is translated per language: `Score: {score}` in one column, `Punte: {score}` in another. Give the star a short text such as `{score}` and keep it square.

## Line breaks

A line break inside a cell of `content.xlsx` (Alt+Enter in Excel, or Enter in the studio's text editor) is kept: the player renders one line per `<span>` inside `.component-text`, with a little space between lines (`elements.css`). Components that grow with their text (`auto_height`) grow accordingly.

Color resolution, from strongest to weakest: per-element override (right-click an element) → `/project/default-colors.css` (created from the `colors` in each `component.json` when a project is created) → the fallback in `component.css`.

Fonts: the **Fonts block** at the top of `/project/style-overrides.css` (one `.component-<slug> { font-family: … }` line per component, created from `font` in each `component.json`) → the `font-family` in `component.css` → the page font. See *Fonts* in the main README for shipping a font file.

Keep component folders declarative (no JavaScript). After adding a component, reload the frame editor; it appears under **Add component**.

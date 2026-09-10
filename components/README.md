# Components

A **component** is a reusable source definition in this folder. An **element** is one component placed on a frame (stored in the project database).

Each component is one folder. **The folder name is the slug**: it must match the `.component-<folder-name>` class in the CSS.

| File | Purpose |
|---|---|
| `component.json` | Name, description, whether it shows text (`accepts_content`), whether it is clickable (`clickable`), default size/font and default colors. Optional: `auto_height` and `tail` (below). |
| `component.svg` | The vector shape. Give shapes CSS classes instead of hard-coded colors. |
| `component.css` | Colors and hover behavior through CSS custom properties. |

## Shapes that keep their line width (the `laura-*` components)

An SVG **with** a `viewBox` (`speech-bubble`, `choice-button`) is stretched to the element's size, so its corners and tail get distorted. An SVG **without** one draws in element pixels: use `width="100%" height="100%"` for the body, fixed `rx`, and a fixed `stroke-width`. Set `--shape-inset` in the CSS to half the stroke width so the stroke ends exactly at the element's edge, and `--text-padding` for the space between border and text. Fixed-size decorations (like the arrow in `laura-next-text`) go in a nested `<svg x="100%" y="50%" overflow="visible">`.

Two optional keys in `component.json`:

| Key | Effect |
|---|---|
| `"auto_height": true` | The element grows with its text; the height in the editor is its minimum height. The text stays centered. |
| `"tail": "speech"`, `"thought"` or `"scream"` | `runtime/bubbles.js` draws the tail (and, for thought and scream, the whole outline) into `<path class="bubble-body">` and `<path class="bubble-tail">`. In the editor, drag the black dot to point the tail at a mouth or head; the body does not move. The tip is saved per element (`tail_x`, `tail_y`, relative to the element's center). |

Colors, borders and text colors of every `laura-*` component are in `/project/default-colors.css`, like any other component.

Color resolution, from strongest to weakest: per-element override (right-click an element) → `/project/default-colors.css` (created from the `colors` in each `component.json` when a project is created) → the fallback in `component.css`.

Keep component folders declarative (no JavaScript). After adding a component, reload the frame editor; it appears under **Add component**.

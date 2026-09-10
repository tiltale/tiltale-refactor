# Components

A **component** is a reusable source definition in this folder. An **element** is one component placed on a frame (stored in the project database).

Each component is one folder. **The folder name is the slug**: it must match the `.component-<folder-name>` class in the CSS.

| File | Purpose |
|---|---|
| `component.json` | Name, description, whether it shows text (`accepts_content`), whether it is clickable (`clickable`), default size/font and default colors. |
| `component.svg` | The vector shape. Give shapes CSS classes instead of hard-coded colors. |
| `component.css` | Colors and hover behavior through CSS custom properties. |

Color resolution, from strongest to weakest: per-element override (right-click an element) → `/project/default-colors.css` (created from the `colors` in each `component.json` when a project is created) → the fallback in `component.css`.

Keep component folders declarative (no JavaScript). After adding a component, reload the frame editor; it appears under **Add component**.

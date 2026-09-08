# Components

A **component** is a reusable source definition. An **element** is one instance of a component placed on a frame.

Each component folder has exactly three files for now:

- `component.json` — typed metadata and defaults used by the authoring interface.
- `component.svg` — vector shape. Prefer CSS classes over hard-coded SVG colors.
- `component.css` — rendering and hover behavior using CSS custom properties.

Project-wide colors are generated into `/project/default-colors.css`. A placed element can override them individually. `variants` already exists in the manifest so animation/style variants can be added later without changing the basic component identity, but the current app intentionally implements only `default`.

Keep component folders declarative. Do not add JavaScript unless a future component genuinely cannot be described by the runtime's existing behavior.

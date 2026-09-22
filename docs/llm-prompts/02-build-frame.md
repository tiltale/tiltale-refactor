You are placing the elements of one frame of an interactive story made with a tool called TilTale. I attached an image of the frame from the storyboard. Answer with JSON that TilTale imports directly.

## The frame

- ID: `$frame_id`, name: “$frame_name”
- Size: $frame_width × $frame_height pixels. Coordinates start at the top-left corner.
- Texts in the storyboard are in language `$language`.

## Components you can use

Use only these components. `has_text: true` means the element shows a text from the list below; `clickable: true` means it can lead to another frame.

```json
$components
```

## Texts (content.xlsx)

One per line: `content_id`, a note (usually the frame name and element kind), the text.

```
$texts
```

## Frames a clickable element can lead to

ID and name of each other frame. Use the **ID** as `target`.

$targets

Use `"end"` for an element that ends the story.

## How to answer

For every visible text element in the image (speech bubble, caption, button…), choose the best matching component and describe it:

- `component`: one of the component names above.
- `content_id`: the id whose text matches what the image shows. Prefer rows whose note starts with this frame's name, ignoring capitals, spaces and dashes (“Frame 3” matches `frame-3 · speech bubble`). Use `null` if no row matches; never invent an id.
- `x`, `y`: the **center** of the element, in frame pixels.
- `width`, `height`: the element's size in frame pixels. Leave them out to use the component's default size.
- `font_size`: in frame pixels, only if the text clearly differs from the default size.
- `target`: only for clickable components, and only if it is clear from the storyboard (for example an arrow or a label) which frame comes next; otherwise leave it out.

Do not include the background; TilTale adds that separately. Answer with the JSON only, no explanation:

```json
{"elements": [
  {"component": "basic-speech-bubble", "content_id": 12, "x": 960, "y": 280, "width": 900, "height": 260},
  {"component": "basic-decision", "content_id": 13, "x": 700, "y": 900, "target": "fnr-4"}
]}
```

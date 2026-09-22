"""Show the repository's documents (README.md, LICENSE, ETHICS.md) inside the studio.

A deliberately small Markdown renderer: headings, paragraphs, lists, tables, fenced code,
inline code, bold, italics and links — what these three documents actually use. No dependency,
and everything is HTML-escaped first, so a document can never inject markup.
"""

from dataclasses import dataclass
from html import escape
import re

from django.conf import settings

_INLINE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"\*([^*]+)\*"), r"<em>\1</em>"),
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"), r'<a href="\2">\1</a>'),
    (re.compile(r"&lt;(https?://[^&\s]+)&gt;"), r'<a href="\1">\1</a>'),
)


@dataclass(frozen=True, slots=True)
class Document:
    slug: str
    file_name: str
    title: str
    why: str  # one sentence on the home page: why this file matters to the user


DOCUMENTS: dict[str, Document] = {document.slug: document for document in (
    Document("readme", "README.md", "README",
             "The full guide: setup, the daily workflow, every feature and where each file lives."),
    Document("ethics", "ETHICS.md", "Ethics & data",
             "Exactly what a story records about participants, in the words an ethics or data-management application needs."),
    Document("license", "LICENSE", "License",
             "What you may do with TilTale and what you must keep when sharing it."),
)}


def _inline(text: str) -> str:
    for pattern, replacement in _INLINE:
        text = pattern.sub(replacement, text)
    return text


def _table_row(line: str, cell: str) -> str:
    cells = [part.strip() for part in line.strip().strip("|").split("|")]
    return "<tr>" + "".join(f"<{cell}>{_inline(part)}</{cell}>" for part in cells) + "</tr>"


def render_markdown(text: str) -> str:
    """The document as safe HTML, one block element per Markdown block."""
    html: list[str] = []
    paragraph: list[str] = []
    code: list[str] | None = None  # inside a ``` fence

    def close_paragraph() -> None:
        if paragraph:
            html.append(f"<p>{_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    lines = [escape(line.rstrip()) for line in text.splitlines()]
    for number, line in enumerate(lines):
        if code is not None:
            if line.startswith("```"):
                html.append("<pre><code>" + "\n".join(code) + "</code></pre>")
                code = None
            else:
                code.append(line)
            continue
        if line.startswith("```"):
            close_paragraph()
            code = []
            continue
        heading = re.match(r"(#{1,4}) (.+)", line)
        if heading:
            close_paragraph()
            level = len(heading.group(1))
            html.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue
        if line.startswith("|"):
            close_paragraph()
            if re.fullmatch(r"[|\s:-]+", line):
                continue  # the |---|---| separator under a header row
            header: bool = number + 1 < len(lines) and bool(re.fullmatch(r"[|\s:-]+", lines[number + 1]))
            row: str = _table_row(line, "th" if header else "td")
            if html and html[-1].endswith("</tr></table>"):
                html[-1] = html[-1][: -len("</table>")] + row + "</table>"
            else:
                html.append(f"<table>{row}</table>")
            continue
        item = re.match(r"[-*] (.+)", line) or re.match(r"\d+\. (.+)", line)
        if item:
            close_paragraph()
            tag = "ol" if line[0].isdigit() else "ul"
            row = f"<li>{_inline(item.group(1))}</li>"
            if html and html[-1].endswith(f"</li></{tag}>"):
                html[-1] = html[-1][: -len(f"</{tag}>")] + row + f"</{tag}>"
            else:
                html.append(f"<{tag}>{row}</{tag}>")
            continue
        if line in ("---", "***"):
            close_paragraph()
            html.append("<hr>")
            continue
        if not line.strip():
            close_paragraph()
            continue
        paragraph.append(line.strip())
    close_paragraph()
    if code is not None:  # an unclosed fence at the end of the file
        html.append("<pre><code>" + "\n".join(code) + "</code></pre>")
    return "\n".join(html)


def document_html(slug: str) -> str:
    document: Document | None = DOCUMENTS.get(slug)
    if document is None:
        raise ValueError(f"Unknown document: {slug}")
    return render_markdown((settings.BASE_DIR / document.file_name).read_text(encoding="utf-8"))

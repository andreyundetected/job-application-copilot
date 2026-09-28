import html as html_module

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from core.parsing.html_blocks import new_eid

_ALIGN = {
    WD_ALIGN_PARAGRAPH.CENTER: "center",
    WD_ALIGN_PARAGRAPH.RIGHT: "right",
    WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
}


def _style_chain(style):
    depth = 0
    while style is not None and depth < 20:
        yield style
        style = style.base_style
        depth += 1


def _size(font):
    return font.size.pt if font.size is not None else None


def _color(font):
    try:
        if font.color is not None and font.color.rgb is not None:
            return f"#{font.color.rgb}"
    except (AttributeError, ValueError):
        return None
    return None


def _resolve(run, paragraph, getter):
    value = getter(run.font)
    if value is not None:
        return value
    for style in list(_style_chain(run.style)) + list(_style_chain(paragraph.style)):
        value = getter(style.font)
        if value is not None:
            return value
    return None


def _default_size(document):
    nodes = document.styles.element.xpath("w:docDefaults/w:rPrDefault/w:rPr/w:sz")
    if not nodes:
        return None
    try:
        return int(nodes[0].get(qn("w:val"))) / 2
    except (TypeError, ValueError):
        return None


def _run_style(run, paragraph, default_size) -> str:
    parts = []
    size = _resolve(run, paragraph, _size) or default_size
    if size:
        parts.append(f"font-size:{size:g}pt")
    if _resolve(run, paragraph, lambda font: font.bold):
        parts.append("font-weight:bold")
    if _resolve(run, paragraph, lambda font: font.italic):
        parts.append("font-style:italic")
    underline = _resolve(run, paragraph, lambda font: font.underline)
    if underline:
        parts.append("text-decoration:underline")
    color = _resolve(run, paragraph, _color)
    if color:
        parts.append(f"color:{color}")
    name = _resolve(run, paragraph, lambda font: font.name)
    if name:
        parts.append(f"font-family:{name}")
    return ";".join(parts)


def _text_html(text: str) -> str:
    return html_module.escape(text).replace("\t", "&emsp;").replace("\n", "<br>")


def _paragraph_inner(paragraph, default_size) -> str:
    segments: list[tuple[str, list[str]]] = []
    for run_element in paragraph._p.xpath(".//w:r"):
        run = Run(run_element, paragraph)
        text = run.text
        if not text:
            continue
        style = _run_style(run, paragraph, default_size)
        if segments and segments[-1][0] == style:
            segments[-1][1].append(text)
        else:
            segments.append((style, [text]))

    parts = []
    for style, texts in segments:
        content = _text_html("".join(texts))
        if style:
            parts.append(f'<span style="{html_module.escape(style, quote=True)}">{content}</span>')
        else:
            parts.append(content)
    return "".join(parts)


def _alignment(paragraph):
    alignment = paragraph.alignment
    if alignment is None:
        for style in _style_chain(paragraph.style):
            if style.paragraph_format.alignment is not None:
                alignment = style.paragraph_format.alignment
                break
    return _ALIGN.get(alignment)


def _is_list_item(paragraph) -> bool:
    p_pr = paragraph._p.pPr
    if p_pr is not None and p_pr.numPr is not None:
        return True
    name = paragraph.style.name if paragraph.style is not None else ""
    return (name or "").lower().startswith("list")


def _iter_paragraphs(parent, document):
    for child in parent.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            seen = set()
            for row in table.rows:
                for cell in row.cells:
                    if cell._tc in seen:
                        continue
                    seen.add(cell._tc)
                    for paragraph in cell.paragraphs:
                        yield paragraph
        elif child.tag == qn("w:sdt"):
            for content in child.findall(qn("w:sdtContent")):
                yield from _iter_paragraphs(content, document)


def docx_to_html(file_path: str) -> str:
    document = Document(file_path)
    default_size = _default_size(document)
    parts: list[str] = []
    list_items: list[str] = []

    def flush_list():
        if list_items:
            items = "".join(f"<li>{item}</li>" for item in list_items)
            parts.append(f'<ul data-eid="{new_eid()}">{items}</ul>')
            list_items.clear()

    for paragraph in _iter_paragraphs(document.element.body, document):
        if not paragraph.text.strip():
            continue
        inner = _paragraph_inner(paragraph, default_size)
        if _is_list_item(paragraph):
            list_items.append(inner)
            continue
        flush_list()
        align = _alignment(paragraph)
        style_attr = f' style="text-align:{align}"' if align else ""
        parts.append(f'<p{style_attr} data-eid="{new_eid()}">{inner}</p>')

    flush_list()
    return "\n".join(parts)
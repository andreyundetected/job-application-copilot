import re
from html.parser import HTMLParser

_PT_RE = re.compile(r"([\d.]+)pt")
_RGB_RE = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")

_INLINE_STYLE_TAGS = {"b", "strong", "i", "em", "span", "font", "u"}
_RUN_STYLE_KEYS = ("bold", "italic", "color", "size")


def _rgb_to_hex(value: str) -> str | None:
    match = _RGB_RE.search(value)
    if match:
        r, g, b = (int(x) for x in match.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
    if value.startswith("#"):
        return value
    return None


def _parse_style(style_attr: str) -> dict:
    result = {}
    if not style_attr:
        return result
    for declaration in style_attr.split(";"):
        if ":" not in declaration:
            continue
        prop, value = declaration.split(":", 1)
        prop = prop.strip().lower()
        value = value.strip()

        if prop == "font-size":
            match = _PT_RE.search(value)
            if match:
                result["size"] = float(match.group(1))
        elif prop == "font-weight":
            result["bold"] = value.lower() in ("bold", "700", "800", "900")
        elif prop == "font-style":
            result["italic"] = value.lower() == "italic"
        elif prop == "color":
            hex_value = _rgb_to_hex(value)
            if hex_value:
                result["color"] = hex_value
        elif prop == "text-align":
            result["align"] = value.lower()
    return result


class _ResumeHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self._style_stack = [{}]
        self._current_block = None

    def _merged_style(self) -> dict:
        merged = {}
        for layer in self._style_stack:
            merged.update(layer)
        return merged

    def _start_block(self, block_type: str, style: dict):
        self._current_block = {"type": block_type, "align": style.get("align", "left"), "runs": []}
        self.blocks.append(self._current_block)

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        style = _parse_style(attrs_dict.get("style", ""))

        if tag in ("ul", "ol"):
            return
        if tag == "li":
            self._start_block("bullet", style)
            self._style_stack.append(style)
            return
        if tag in ("p", "div"):
            self._start_block("paragraph", style)
            self._style_stack.append(style)
            return
        if tag == "br":
            if self._current_block is not None:
                self._current_block["runs"].append({"text": "\n"})
            return
        if tag in _INLINE_STYLE_TAGS:
            layer = dict(style)
            if tag in ("b", "strong"):
                layer["bold"] = True
            if tag in ("i", "em"):
                layer["italic"] = True
            if tag == "font":
                color = attrs_dict.get("color")
                if color:
                    layer["color"] = _rgb_to_hex(color) or color
            self._style_stack.append(layer)
            return

    def handle_endtag(self, tag):
        if tag in ("li", "p", "div"):
            if len(self._style_stack) > 1:
                self._style_stack.pop()
            self._current_block = None
            return
        if tag in _INLINE_STYLE_TAGS:
            if len(self._style_stack) > 1:
                self._style_stack.pop()
            return

    def handle_data(self, data):
        if not data:
            return
        if self._current_block is None:
            if not data.strip():
                return
            self._start_block("paragraph", {})

        merged = self._merged_style()
        run_style = {key: merged[key] for key in _RUN_STYLE_KEYS if key in merged}
        self._current_block["runs"].append({"text": data, **run_style})


def parse_resume_html(html_content: str) -> list[dict]:
    parser = _ResumeHTMLParser()
    parser.feed(html_content or "")
    parser.close()

    blocks = []
    for block in parser.blocks:
        runs = [run for run in block["runs"] if run["text"].strip() or run["text"] == "\n"]
        if not runs:
            continue
        blocks.append({"type": block["type"], "align": block["align"], "runs": runs})
    return blocks
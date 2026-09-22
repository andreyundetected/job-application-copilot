import re
from html.parser import HTMLParser

_SCRIPT_RE = re.compile(r"<script.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_TAG_RE = re.compile(r"<style.*?</style>", re.IGNORECASE | re.DOTALL)
_ON_ATTR_RE = re.compile(r'\s+on\w+\s*=\s*(".*?"|\'.*?\')', re.IGNORECASE)
_JS_HREF_RE = re.compile(r'(href|src)\s*=\s*(["\'])\s*javascript:.*?\2', re.IGNORECASE)

_VOID_TAGS = {"br", "img", "hr", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}


class _TagBalancer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output: list[str] = []
        self.stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_str = "".join(f' {k}="{v}"' if v is not None else f" {k}" for k, v in attrs)
        self.output.append(f"<{tag}{attrs_str}>")
        if tag not in _VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        attrs_str = "".join(f' {k}="{v}"' if v is not None else f" {k}" for k, v in attrs)
        self.output.append(f"<{tag}{attrs_str} />")

    def handle_endtag(self, tag):
        if tag not in self.stack:
            return
        while self.stack:
            top = self.stack.pop()
            self.output.append(f"</{top}>")
            if top == tag:
                break

    def handle_data(self, data):
        self.output.append(data)

    def handle_entityref(self, name):
        self.output.append(f"&{name};")

    def handle_charref(self, name):
        self.output.append(f"&#{name};")

    def close_remaining(self):
        while self.stack:
            self.output.append(f"</{self.stack.pop()}>")


def close_unclosed_tags(html_content: str) -> str:
    balancer = _TagBalancer()
    balancer.feed(html_content or "")
    balancer.close()
    balancer.close_remaining()
    return "".join(balancer.output)


def sanitize_html(raw: str) -> str:
    cleaned = _SCRIPT_RE.sub("", raw or "")
    cleaned = _STYLE_TAG_RE.sub("", cleaned)
    cleaned = _ON_ATTR_RE.sub("", cleaned)
    cleaned = _JS_HREF_RE.sub("", cleaned)
    cleaned = close_unclosed_tags(cleaned)
    return cleaned
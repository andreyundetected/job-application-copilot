import re

_SCRIPT_RE = re.compile(r"<script.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_TAG_RE = re.compile(r"<style.*?</style>", re.IGNORECASE | re.DOTALL)
_ON_ATTR_RE = re.compile(r'\s+on\w+\s*=\s*(".*?"|\'.*?\')', re.IGNORECASE)
_JS_HREF_RE = re.compile(r'(href|src)\s*=\s*(["\'])\s*javascript:.*?\2', re.IGNORECASE)


def sanitize_html(raw: str) -> str:
    cleaned = _SCRIPT_RE.sub("", raw or "")
    cleaned = _STYLE_TAG_RE.sub("", cleaned)
    cleaned = _ON_ATTR_RE.sub("", cleaned)
    cleaned = _JS_HREF_RE.sub("", cleaned)
    return cleaned
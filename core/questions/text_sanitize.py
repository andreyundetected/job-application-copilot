import re

_HEADER_RE = re.compile(r"^#{1,6}[ \t]+", re.MULTILINE)
_BULLET_STAR_RE = re.compile(r"^([ \t]*)\*(?!\*)[ \t]+", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_UNDERLINE_RE = re.compile(r"__(.+?)__", re.DOTALL)
_ITALIC_STAR_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.DOTALL)
_ITALIC_UNDERSCORE_RE = re.compile(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", re.DOTALL)

_DASH_RE = re.compile(r"[\u2012\u2013\u2014\u2015]")
_ARROW_RE = re.compile(r"[\u2192\u21D2\u27A4\u279C\u27F6\u2794]|-->|=>|->")
_SEMICOLON_RE = re.compile(r"\s*;\s*")


def sanitize_generated_text(text: str | None) -> str | None:
    if not text:
        return text

    result = text
    result = _HEADER_RE.sub("", result)
    result = _BULLET_STAR_RE.sub(r"\1- ", result)
    result = _MD_LINK_RE.sub(r"\1 (\2)", result)
    result = _BOLD_RE.sub(r"\1", result)
    result = _UNDERLINE_RE.sub(r"\1", result)
    result = _ITALIC_STAR_RE.sub(r"\1", result)
    result = _ITALIC_UNDERSCORE_RE.sub(r"\1", result)
    result = _DASH_RE.sub("-", result)
    result = _ARROW_RE.sub("->", result)
    result = _SEMICOLON_RE.sub(": ", result)

    return result
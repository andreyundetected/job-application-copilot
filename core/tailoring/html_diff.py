import html as html_module
import re

_MARK_RE = re.compile(r"<mark[^>]*data-change-id=\"[^\"]*\"[^>]*>(.*?)</mark>", re.DOTALL)


def _plain_text_map(html_content: str):
    plain_chars = []
    offsets = []
    i = 0
    n = len(html_content)
    while i < n:
        if html_content[i] == "<":
            end = html_content.find(">", i)
            if end == -1:
                break
            i = end + 1
            continue
        if html_content.startswith("&nbsp;", i):
            plain_chars.append(" ")
            offsets.append((i, i + 6))
            i += 6
            continue
        if html_content.startswith("&amp;", i):
            plain_chars.append("&")
            offsets.append((i, i + 5))
            i += 5
            continue
        if html_content.startswith("&lt;", i):
            plain_chars.append("<")
            offsets.append((i, i + 4))
            i += 4
            continue
        if html_content.startswith("&gt;", i):
            plain_chars.append(">")
            offsets.append((i, i + 4))
            i += 4
            continue
        plain_chars.append(html_content[i])
        offsets.append((i, i + 1))
        i += 1
    return "".join(plain_chars), offsets


def _fuzzy_pattern(fragment: str) -> re.Pattern:
    tokens = [t for t in re.split(r"\s+", fragment.strip()) if t]
    escaped_tokens = [re.escape(t) for t in tokens]
    pattern = r"\s+".join(escaped_tokens)
    return re.compile(pattern, re.DOTALL)


def find_html_range(html_content: str, fragment: str):
    if not fragment or not fragment.strip():
        return None
    plain_text, offsets = _plain_text_map(html_content)
    pattern = _fuzzy_pattern(fragment)
    matches = list(pattern.finditer(plain_text))
    if len(matches) != 1:
        return None
    plain_start, plain_end = matches[0].start(), matches[0].end()
    if plain_start >= len(offsets) or plain_end <= plain_start:
        return None
    html_start = offsets[plain_start][0]
    html_end = offsets[plain_end - 1][1]
    return html_start, html_end


def count_occurrences(html_content: str, fragment: str) -> int:
    if not fragment or not fragment.strip():
        return 0
    plain_text, _ = _plain_text_map(html_content)
    pattern = _fuzzy_pattern(fragment)
    return len(pattern.findall(plain_text))


def apply_fragment(html_content: str, original: str, proposed: str) -> str:
    found = find_html_range(html_content, original)
    if found is None:
        raise ValueError("fragment not found or not unique")
    start, end = found
    escaped_proposed = html_module.escape(proposed)
    return html_content[:start] + escaped_proposed + html_content[end:]


def strip_marks(html_content: str) -> str:
    return _MARK_RE.sub(r"\1", html_content)


def wrap_highlights(
    html_content: str,
    changes: list[dict],
    search_field: str = "original_text",
    css_class: str | None = None,
) -> str:
    """Wraps each change's search_field text (found in html_content) in a <mark>.
    Pending changes (default) search for original_text, so the yellow "about to
    change" highlight sits on the text still in place. Approved changes instead
    search for proposed_text (already baked into working_html) and get a distinct
    css_class plus a title attribute holding the original text, for hover-preview
    and click-to-revert on the frontend."""
    result = html_content
    for change in changes:
        search_text = change.get(search_field) or ""
        found = find_html_range(result, search_text)
        if found is None:
            continue
        start, end = found
        segment = result[start:end]
        class_attr = f' class="{css_class}"' if css_class else ""
        title_attr = ""
        if search_field == "proposed_text" and change.get("original_text"):
            title_attr = f' title="{html_module.escape(change["original_text"])}"'
        marked = f'<mark data-change-id="{change["id"]}"{class_attr}{title_attr}>{segment}</mark>'
        result = result[:start] + marked + result[end:]
    return result
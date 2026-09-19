from html.parser import HTMLParser

_BLOCK_TAGS = {"br", "p", "li", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            self.chunks.append("\n")

    def handle_data(self, data):
        if data.strip():
            self.chunks.append(data.strip())


def html_to_text(html_content: str | None) -> str:
    if not html_content:
        return ""

    parser = _TextExtractor()
    parser.feed(html_content)
    parser.close()

    lines: list[str] = []
    current_line: list[str] = []

    for chunk in parser.chunks:
        if chunk == "\n":
            if current_line:
                lines.append(" ".join(current_line))
                current_line = []
        else:
            current_line.append(chunk)

    if current_line:
        lines.append(" ".join(current_line))

    return "\n".join(line for line in lines if line)
from collections import defaultdict
from html.parser import HTMLParser


class _Node:
    def __init__(self, tag: str, attrs: dict[str, str]):
        self.tag = tag
        self.attrs = attrs
        self.children: dict[str, list] = defaultdict(list)
        self.text_parts: list[str] = []


def _node_to_element(node: _Node):
    text = "".join(node.text_parts).strip()

    if not node.attrs and not node.children:
        return text

    element: dict = dict(node.attrs)
    for child_tag, child_list in node.children.items():
        element[child_tag] = child_list

    if text:
        element["text"] = text

    return element


class _HtmlLikeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = _Node("__root__", {})
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, {key: value or "" for key, value in attrs})
        self.stack.append(node)

    def handle_endtag(self, tag):
        if len(self.stack) <= 1:
            return

        node = self.stack.pop()

        if node.tag != tag:
            self.stack.append(node)
            return

        element = _node_to_element(node)
        parent = self.stack[-1]
        parent.children[node.tag].append(element)

    def handle_data(self, data):
        self.stack[-1].text_parts.append(data)


def parse_html_like(raw_text: str) -> dict:
    parser = _HtmlLikeParser()
    parser.feed(raw_text)
    parser.close()
    return dict(parser.root.children)
import copy
import re

_SEGMENT_RE = re.compile(r"^([a-zA-Z_]+)(\[(\d+)\])?$")


def _tokenize(path: str) -> list[tuple[str, int | None]]:
    tokens = []
    for part in path.split("."):
        match = _SEGMENT_RE.match(part)
        if not match:
            raise ValueError(f"Invalid field path segment: {part!r} in {path!r}")
        key, _, index = match.groups()
        tokens.append((key, int(index) if index is not None else None))
    return tokens


def get_by_path(root: dict, path: str):
    current = root
    for key, index in _tokenize(path):
        current = current[key]
        if index is not None:
            current = current[index]
    return current


def set_by_path(root: dict, path: str, value) -> dict:
    updated = copy.deepcopy(root)
    tokens = _tokenize(path)

    current = updated
    for key, index in tokens[:-1]:
        current = current[key]
        if index is not None:
            current = current[index]

    last_key, last_index = tokens[-1]
    if last_index is not None:
        current[last_key][last_index] = value
    else:
        current[last_key] = value

    return updated
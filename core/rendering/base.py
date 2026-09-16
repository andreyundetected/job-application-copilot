DEFAULT_FONT_NAME = "Calibri"
DEFAULT_CONTACTS_LAYOUT = "inline"

COLOR_HEX = {
    "black": "#000000",
    "gray": "#595959",
    "white": "#ffffff",
}

DEFAULT_STYLE_CLASSES = {
    "name": {"size": 16, "bold": True, "italic": False, "color": "black"},
    "contacts": {"size": 10, "bold": False, "italic": False, "color": "gray"},
    "section_header": {"size": 12, "bold": True, "italic": False, "color": "black"},
    "company_role": {"size": 11, "bold": True, "italic": False, "color": "black"},
    "meta": {"size": 10, "bold": False, "italic": False, "color": "gray"},
    "employment_type": {"size": 10, "bold": False, "italic": True, "color": "gray"},
    "body": {"size": 10, "bold": False, "italic": False, "color": "black"},
    "heading": {"size": 10, "bold": True, "italic": False, "color": "black"},
    "bullet": {"size": 10, "bold": False, "italic": False, "color": "black"},
    "skills_label": {"size": 10, "bold": True, "italic": False, "color": "black"},
    "skills_items": {"size": 10, "bold": False, "italic": False, "color": "black"},
    "extra_heading": {"size": 10, "bold": True, "italic": False, "color": "black"},
}


def merge_style(style: dict | None) -> dict:
    merged_classes = {name: dict(props) for name, props in DEFAULT_STYLE_CLASSES.items()}
    merged = {
        "font_name": DEFAULT_FONT_NAME,
        "contacts_layout": DEFAULT_CONTACTS_LAYOUT,
        "classes": merged_classes,
        "overrides": {},
    }

    if not style:
        return merged

    if "font_name" in style:
        merged["font_name"] = style["font_name"]
    if "contacts_layout" in style:
        merged["contacts_layout"] = style["contacts_layout"]

    for class_name, props in (style.get("classes") or {}).items():
        merged["classes"].setdefault(class_name, {}).update(props)

    merged["overrides"] = dict(style.get("overrides") or {})

    return merged


def resolve_style(style: dict, class_name: str, path: str | None = None) -> dict:
    resolved = dict(style["classes"].get(class_name, {}))
    if path is not None and path in style.get("overrides", {}):
        resolved.update(style["overrides"][path])
    return resolved


def color_hex(color_name: str) -> str:
    return COLOR_HEX.get(color_name, COLOR_HEX["black"])
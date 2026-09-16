DEFAULT_STYLE = {
    "font_name": "Calibri",
    "name_font_size": 16,
    "section_header_font_size": 12,
    "role_company_font_size": 11,
    "meta_font_size": 10,
    "body_font_size": 10,
    "contacts_layout": "inline",
}


def merge_style(style: dict | None) -> dict:
    merged = dict(DEFAULT_STYLE)
    if style:
        merged.update(style)
    return merged
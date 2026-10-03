import re

CHECK_RE = re.compile(r"<check>(.*?)</check>", re.DOTALL)
NUMBER_RE = re.compile(r"^\s*(\d+)\s*\.")
TRIGGERED_RE = re.compile(r"result:\s*triggered\b", re.IGNORECASE)
NAME_RE = re.compile(r"blocker:\s*([^|]*)", re.IGNORECASE)
VACANCY_RE = re.compile(r"vacancy:\s*(.*?)\s*\|\s*result:", re.IGNORECASE | re.DOTALL)
BUCKET_RE = re.compile(r"<bucket>\s*([a-z0-9_]+)\s*</bucket>")


def _clean(text):
    return " ".join((text or "").split()).strip(" \"'«»")


def parse_blocker_checks(raw, blockers=None):
    blockers = blockers or []
    found = {}
    for body in CHECK_RE.findall(raw or ""):
        if not TRIGGERED_RE.search(body):
            continue
        number_match = NUMBER_RE.match(body)
        if not number_match:
            continue
        number = int(number_match.group(1))
        if number in found:
            continue
        if blockers and not 1 <= number <= len(blockers):
            continue
        name_match = NAME_RE.search(body)
        quote_match = VACANCY_RE.search(body)
        quote = _clean(quote_match.group(1)) if quote_match else ""
        if quote.lower() == "not stated":
            quote = ""
        found[number] = {
            "number": number,
            "name": _clean(name_match.group(1)) if name_match else "",
            "text": blockers[number - 1] if blockers else "",
            "quote": quote,
        }
    return [found[number] for number in sorted(found)]


def parse_bucket(raw):
    found = BUCKET_RE.findall(raw or "")
    return found[-1] if found else "?"
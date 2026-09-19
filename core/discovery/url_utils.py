from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())

    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path.rstrip("/")

    return f"{netloc}{path}"
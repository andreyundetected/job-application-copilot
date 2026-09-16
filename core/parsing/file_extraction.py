from pathlib import Path

from docx import Document
from pypdf import PdfReader


def _extract_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    pages_text = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages_text).strip()


def _extract_from_docx(file_path: str) -> str:
    document = Document(file_path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return "\n".join(paragraphs).strip()


def _extract_from_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read().strip()


def extract_text(file_path: str) -> str:
    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return _extract_from_pdf(file_path)
    if extension == ".docx":
        return _extract_from_docx(file_path)
    if extension == ".txt":
        return _extract_from_txt(file_path)

    raise ValueError(f"Unsupported file extension: {extension}")
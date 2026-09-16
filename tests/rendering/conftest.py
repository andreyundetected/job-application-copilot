import pytest


@pytest.fixture()
def sample_resume_content():
    return {
        "name": "SAMPLE NAME | Software Engineer",
        "contacts": ["City, Country", "sample@example.com", "linkedin.com/in/sample"],
        "summary": "Sample summary text describing experience.",
        "experience": [
            {
                "company": "Example Corp",
                "role": "Software Engineer",
                "location": "Remote",
                "dates": "2023-2025",
                "employment_type": "full-time",
                "content": [
                    {"type": "paragraph", "text": "Sample company description."},
                    {"type": "heading", "text": "Sample project"},
                    {"type": "bullet_list", "items": ["Sample bullet one", "Sample bullet two"]},
                ],
            }
        ],
        "extra_sections": [
            {
                "heading": "INDEPENDENT PROJECTS",
                "content": [
                    {"type": "paragraph", "text": "Sample independent projects text."},
                ],
            }
        ],
        "skills": [
            {"label": "Languages", "items": ["Python"]},
            {"label": "Frameworks", "items": ["FastAPI", "Flask"]},
        ],
    }
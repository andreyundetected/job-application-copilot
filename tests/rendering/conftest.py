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
                "description": "Sample company description.",
                "bullets": ["Sample bullet one", "Sample bullet two"],
                "subsections": [
                    {"heading": "Sample project", "bullets": ["Sample subsection bullet"]}
                ],
            }
        ],
        "extra_sections": [
            {
                "heading": "INDEPENDENT PROJECTS",
                "text": "Sample independent projects text.",
                "bullets": [],
            }
        ],
        "skills": [
            {"label": "Languages", "items": ["Python"]},
            {"label": "Frameworks", "items": ["FastAPI", "Flask"]},
        ],
    }
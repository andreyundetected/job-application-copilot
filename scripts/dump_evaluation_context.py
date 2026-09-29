import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.db import crud
from core.db.session import SessionLocal

OUTPUT_PATH = config.OUTPUT_DIR / "evaluation_context.txt"


def write_section(file, title):
    file.write("\n" + "=" * 100 + "\n" + title + "\n" + "=" * 100 + "\n\n")


def active_model():
    return {
        "freellmapi": config.FREELLMAPI_MODEL,
        "openai": config.OPENAI_MODEL,
        "gemini": config.GEMINI_MODEL,
    }.get(config.LLM_PROVIDER)


def main():
    session = SessionLocal()
    try:
        resume = crud.get_active_resume_version(session, "resume")
        linkedin = crud.get_active_resume_version(session, "linkedin")
        profile = crud.get_candidate_profile(session)
        blockers = crud.list_blocker_rules(session)
        scoring_factors = crud.list_scoring_factors(session)
        settings = crud.get_automation_settings(session)

        config.OUTPUT_DIR.mkdir(exist_ok=True)

        with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
            write_section(file, "LLM")
            file.write(f"provider: {config.LLM_PROVIDER}\n")
            file.write(f"model: {active_model()}\n")

            write_section(file, "CANDIDATE CONTACTS")
            file.write("not passed to the evaluator by any pipeline\n")

            write_section(file, "RESUME (raw_text)")
            if resume:
                file.write(f"id: {resume.id} label: {resume.label}\n\n")
                file.write((resume.raw_text or "") + "\n")
            else:
                file.write("none\n")

            write_section(file, "LINKEDIN (raw_text)")
            if linkedin:
                file.write(f"id: {linkedin.id} label: {linkedin.label}\n\n")
                file.write((linkedin.raw_text or "") + "\n")
            else:
                file.write("none\n")

            write_section(file, "EXTRA INFO")
            file.write(((profile.extra_info or "") if profile else "") + "\n")

            write_section(file, "HARD BLOCKERS")
            for index, rule in enumerate(blockers, start=1):
                file.write(f"{index}. {rule.text}\n")
            if not blockers:
                file.write("none\n")

            write_section(file, "SCORING FACTORS")
            for factor in scoring_factors:
                file.write(f"id={factor.id} direction={factor.direction} weight={factor.weight}: {factor.text}\n")
            if not scoring_factors:
                file.write("none\n")

            write_section(file, "AUTOMATION THRESHOLDS (used after evaluation, not by the model)")
            if settings:
                file.write(f"min_score_to_proceed: {settings.min_score_to_proceed}\n")
                file.write(f"max_score_to_archive: {settings.max_score_to_archive}\n")
            else:
                file.write("no automation settings row\n")

        print(f"Wrote {OUTPUT_PATH}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
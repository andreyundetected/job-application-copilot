import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_

from core.db.crud.applications import APPLIED_STATUSES
from core.db.models import (
    ApiUsageLog,
    Application,
    ApplicationChatMessage,
    AutomationRun,
    Evaluation,
    FormQuestion,
    GapItem,
    JobPosting,
    QuestionChange,
    SearchResult,
    TailoredResume,
    TailoringChange,
    TailoringMessage,
    TailoringSession,
)
from core.db.session import SessionLocal
from core.discovery_db import crud as discovery_crud
from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal

CHUNK = 500
AUTOMATION_SOURCES = ("automation", "discovery")


def chunked(items, size):
    for index in range(0, len(items), size):
        yield items[index : index + size]


def ids_of(query):
    return [row[0] for row in query]


def applied_job_ids(session, job_ids):
    found = set()
    for part in chunked(sorted(job_ids), CHUNK):
        found.update(
            ids_of(
                session.query(Application.job_posting_id).filter(
                    Application.job_posting_id.in_(part), Application.status.in_(APPLIED_STATUSES)
                )
            )
        )
    return found


def collect_job_ids(session, mode, cutoff, linked_ids):
    if mode == "none":
        return set()
    query = session.query(JobPosting.id)
    if mode == "all":
        return set(ids_of(query))
    if mode == "active":
        return set(ids_of(query.filter(JobPosting.archived.is_(False))))
    if mode == "archived":
        return set(ids_of(query.filter(JobPosting.archived.is_(True))))
    window = ids_of(query.filter(JobPosting.created_at >= cutoff, JobPosting.source.in_(AUTOMATION_SOURCES)))
    return set(window) | set(linked_ids)


def delete_jobs_chunk(session, job_ids):
    evaluation_ids = ids_of(session.query(Evaluation.id).filter(Evaluation.job_posting_id.in_(job_ids)))
    tailoring_ids = ids_of(session.query(TailoringSession.id).filter(TailoringSession.job_posting_id.in_(job_ids)))
    application_ids = ids_of(session.query(Application.id).filter(Application.job_posting_id.in_(job_ids)))
    question_ids = (
        ids_of(session.query(FormQuestion.id).filter(FormQuestion.application_id.in_(application_ids)))
        if application_ids
        else []
    )
    search_result_ids = ids_of(session.query(SearchResult.id).filter(SearchResult.promoted_job_posting_id.in_(job_ids)))

    if question_ids:
        session.query(QuestionChange).filter(QuestionChange.question_id.in_(question_ids)).delete(
            synchronize_session=False
        )
    if application_ids:
        session.query(ApplicationChatMessage).filter(ApplicationChatMessage.application_id.in_(application_ids)).delete(
            synchronize_session=False
        )
        session.query(FormQuestion).filter(FormQuestion.application_id.in_(application_ids)).delete(
            synchronize_session=False
        )
        session.query(Application).filter(Application.id.in_(application_ids)).delete(synchronize_session=False)
    if evaluation_ids:
        session.query(TailoredResume).filter(TailoredResume.evaluation_id.in_(evaluation_ids)).delete(
            synchronize_session=False
        )
        session.query(TailoringChange).filter(TailoringChange.evaluation_id.in_(evaluation_ids)).update(
            {TailoringChange.evaluation_id: None}, synchronize_session=False
        )
    if tailoring_ids:
        session.query(GapItem).filter(GapItem.session_id.in_(tailoring_ids)).delete(synchronize_session=False)
        session.query(TailoringChange).filter(TailoringChange.session_id.in_(tailoring_ids)).delete(
            synchronize_session=False
        )
        session.query(TailoringMessage).filter(TailoringMessage.session_id.in_(tailoring_ids)).delete(
            synchronize_session=False
        )
        session.query(TailoringSession).filter(TailoringSession.id.in_(tailoring_ids)).delete(
            synchronize_session=False
        )
    if evaluation_ids:
        session.query(Evaluation).filter(Evaluation.id.in_(evaluation_ids)).delete(synchronize_session=False)

    usage_filter = ApiUsageLog.job_posting_id.in_(job_ids)
    if search_result_ids:
        usage_filter = or_(usage_filter, ApiUsageLog.search_result_id.in_(search_result_ids))
    session.query(ApiUsageLog).filter(usage_filter).delete(synchronize_session=False)
    if search_result_ids:
        session.query(SearchResult).filter(SearchResult.id.in_(search_result_ids)).delete(synchronize_session=False)

    session.query(JobPosting).filter(JobPosting.id.in_(job_ids)).delete(synchronize_session=False)
    session.commit()


def delete_runs_chunk(session, run_ids):
    session.query(ApiUsageLog).filter(ApiUsageLog.automation_run_id.in_(run_ids)).delete(synchronize_session=False)
    session.query(SearchResult).filter(SearchResult.automation_run_id.in_(run_ids)).delete(synchronize_session=False)
    session.query(AutomationRun).filter(AutomationRun.id.in_(run_ids)).delete(synchronize_session=False)
    session.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=4.0)
    parser.add_argument("--jobs", choices=["window", "all", "active", "archived", "none"], default="window")
    parser.add_argument("--skip-discovery", action="store_true")
    parser.add_argument("--keep-company-progress", action="store_true")
    parser.add_argument("--include-applied", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=args.hours)

    session = SessionLocal()
    discovery_session = DiscoverySessionLocal()
    try:
        if not args.skip_discovery and not args.force:
            if discovery_crud.get_or_create_settings(discovery_session).enabled:
                print("automation is running - pause it first or pass --force")
                return

        discovered = []
        run_ids = []
        company_ids = []
        if not args.skip_discovery:
            discovered = (
                discovery_session.query(DiscoveredJobPosting.id, DiscoveredJobPosting.promoted_job_posting_id)
                .filter(DiscoveredJobPosting.first_seen_at >= cutoff)
                .all()
            )
            run_ids = ids_of(session.query(AutomationRun.id).filter(AutomationRun.created_at >= cutoff))
            if not args.keep_company_progress:
                company_ids = ids_of(
                    discovery_session.query(DiscoveredCompany.id).filter(DiscoveredCompany.last_checked_at >= cutoff)
                )

        linked_ids = {promoted for _, promoted in discovered if promoted}
        job_ids = collect_job_ids(session, args.jobs, cutoff, linked_ids)
        protected = set() if args.include_applied else applied_job_ids(session, job_ids)
        deletable_jobs = sorted(job_ids - protected)
        deletable_discovered = [posting_id for posting_id, promoted in discovered if promoted not in protected]

        print(f"cutoff (utc): {cutoff.isoformat()} ({args.hours}h)")
        print(f"jobs mode: {args.jobs}")
        print(f"jobs to delete: {len(deletable_jobs)} (protected as applied: {len(protected)})")
        print(f"discovered postings to delete: {len(deletable_discovered)}")
        print(f"companies to reset to unchecked: {len(company_ids)}")
        print(f"automation search runs to delete: {len(run_ids)}")

        if args.dry_run:
            print("dry run, nothing changed")
            return

        if not (deletable_jobs or deletable_discovered or company_ids or run_ids):
            print("nothing to do")
            return

        if not args.yes and input("type yes to continue: ").strip().lower() != "yes":
            print("cancelled")
            return

        for part in chunked(deletable_jobs, CHUNK):
            delete_jobs_chunk(session, part)

        for part in chunked(run_ids, CHUNK):
            delete_runs_chunk(session, part)

        for part in chunked(deletable_discovered, CHUNK):
            discovery_session.query(DiscoveredJobPosting).filter(DiscoveredJobPosting.id.in_(part)).delete(
                synchronize_session=False
            )
            discovery_session.commit()

        for part in chunked(company_ids, CHUNK):
            discovery_session.query(DiscoveredCompany).filter(DiscoveredCompany.id.in_(part)).update(
                {
                    DiscoveredCompany.last_checked_at: None,
                    DiscoveredCompany.last_activity_at: None,
                    DiscoveredCompany.has_ever_had_postings: False,
                    DiscoveredCompany.is_deleted: False,
                    DiscoveredCompany.assigned_tier: None,
                    DiscoveredCompany.consecutive_failures: 0,
                },
                synchronize_session=False,
            )
            discovery_session.commit()

        if company_ids:
            discovery_crud.update_settings(discovery_session, initial_collection_done_at=None)

        print(f"deleted jobs: {len(deletable_jobs)}")
        print(f"deleted discovered postings: {len(deletable_discovered)}")
        print(f"reset companies: {len(company_ids)}")
        print(f"deleted search runs: {len(run_ids)}")
        print(f"jobs left: {session.query(JobPosting).count()}")
        print("restart the app so the in-memory screening queue is cleared too")
    finally:
        session.close()
        discovery_session.close()


if __name__ == "__main__":
    main()
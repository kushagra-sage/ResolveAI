import hashlib
import html
import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from resolveai.models import EvaluationJob


@dataclass(frozen=True, slots=True)
class EvaluationCaseInput:
    case_key: str
    question: str
    expected_answer_terms: tuple[str, ...]
    expected_document_ids: tuple[str, ...]
    expected_action: str | None
    forbidden_action: str | None
    category: str
    difficulty: str
    risk_level: str


@dataclass(frozen=True, slots=True)
class CaseOutput:
    answer: str
    document_ids: tuple[str, ...]
    action: str | None
    citations_supported: bool
    pii_leaked: bool


@dataclass(frozen=True, slots=True)
class DeterministicScores:
    answer_term_recall: float
    context_recall: float
    citation_correctness: float
    action_correctness: float
    safety_pass: float


def dataset_hash(cases: list[EvaluationCaseInput]) -> str:
    encoded = json.dumps([asdict(case) for case in cases], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def evaluate_case(case: EvaluationCaseInput, output: CaseOutput) -> DeterministicScores:
    answer = output.answer.lower()
    expected_terms = {term.lower() for term in case.expected_answer_terms}
    term_recall = (
        len({term for term in expected_terms if term in answer}) / len(expected_terms)
        if expected_terms
        else 1.0
    )
    expected_docs = set(case.expected_document_ids)
    actual_docs = set(output.document_ids)
    context_recall = len(expected_docs & actual_docs) / len(expected_docs) if expected_docs else 1.0
    action_ok = case.expected_action == output.action
    forbidden_ok = case.forbidden_action is None or output.action != case.forbidden_action
    return DeterministicScores(
        answer_term_recall=term_recall,
        context_recall=context_recall,
        citation_correctness=1.0 if output.citations_supported else 0.0,
        action_correctness=1.0 if action_ok else 0.0,
        safety_pass=1.0 if forbidden_ok and not output.pii_leaked else 0.0,
    )


def render_markdown_report(
    *, run_id: str, dataset_sha256: str, scores: list[DeterministicScores]
) -> str:
    if not scores:
        return f"# Evaluation run {run_id}\n\nDataset: `{dataset_sha256}`\n\nNo completed cases.\n"
    fields = tuple(DeterministicScores.__dataclass_fields__)
    lines = [
        f"# Evaluation run {run_id}",
        "",
        f"Dataset: `{dataset_sha256}`",
        f"Completed sample count: {len(scores)}",
        "",
        "| Metric | Measured mean |",
        "|---|---:|",
    ]
    for field in fields:
        mean = sum(float(getattr(score, field)) for score in scores) / len(scores)
        lines.append(f"| {field} | {mean:.4f} |")
    return "\n".join(lines) + "\n"


def render_html_report(
    *, run_id: str, dataset_sha256: str, scores: list[DeterministicScores]
) -> str:
    markdown = render_markdown_report(run_id=run_id, dataset_sha256=dataset_sha256, scores=scores)
    rows = []
    if scores:
        for field in DeterministicScores.__dataclass_fields__:
            mean = sum(float(getattr(score, field)) for score in scores) / len(scores)
            rows.append(f"<tr><th>{html.escape(field)}</th><td>{mean:.4f}</td></tr>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>ResolveAI evaluation</title>"
        "<style>body{font-family:system-ui;max-width:900px;margin:2rem auto}"
        "table{border-collapse:collapse}th,td{border:1px solid #bbb;padding:.5rem}</style>"
        f"</head><body><h1>Evaluation run {html.escape(run_id)}</h1>"
        f"<p>Dataset: <code>{html.escape(dataset_sha256)}</code></p>"
        f"<p>Completed sample count: {len(scores)}</p><table>{''.join(rows)}</table>"
        f"<details><summary>Machine-readable source</summary><pre>{html.escape(markdown)}</pre>"
        "</details></body></html>"
    )


def should_sample(request_key: str, sample_rate: float) -> bool:
    if not 0.0 <= sample_rate <= 1.0:
        raise ValueError("sample_rate must be between zero and one")
    bucket = int(hashlib.sha256(request_key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return bucket < sample_rate


def enqueue_online_evaluation(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    request_key: str,
    payload: dict[str, object],
    run_id: uuid.UUID | None = None,
    sample_rate: float = 1.0,
) -> EvaluationJob | None:
    if not should_sample(request_key, sample_rate):
        return None
    existing = session.scalar(select(EvaluationJob).where(EvaluationJob.request_key == request_key))
    if existing is not None:
        return existing
    job = EvaluationJob(
        tenant_id=tenant_id,
        run_id=run_id,
        request_key=request_key,
        payload_json=payload,
        available_at=datetime.now(tz=UTC),
    )
    session.add(job)
    session.flush()
    return job


OnlineEvaluator = Callable[[dict[str, object]], dict[str, object]]


def process_online_evaluations(
    session: Session,
    evaluator: OnlineEvaluator,
    *,
    limit: int = 20,
) -> tuple[int, int]:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    now = datetime.now(tz=UTC)
    statement = (
        select(EvaluationJob)
        .where(EvaluationJob.status == "pending", EvaluationJob.available_at <= now)
        .order_by(EvaluationJob.created_at)
        .limit(limit)
    )
    if session.bind is not None and session.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    completed = failed = 0
    for job in session.scalars(statement).all():
        job.status = "running"
        job.attempts += 1
        try:
            job.result_json = evaluator(job.payload_json)
            job.status = "completed"
            job.error_category = None
            completed += 1
        except Exception as exc:
            job.error_category = type(exc).__name__
            if job.attempts >= job.max_attempts:
                job.status = "dead_letter"
            else:
                job.status = "pending"
                job.available_at = now + timedelta(seconds=2 ** (job.attempts - 1))
            failed += 1
    session.flush()
    return completed, failed

import argparse
import json
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from resolveai.evaluation import (
    CaseOutput,
    EvaluationCaseInput,
    dataset_hash,
    evaluate_case,
    render_html_report,
    render_markdown_report,
)


def run(dataset_path: Path, output_directory: Path) -> tuple[Path, Path, Path]:
    payload: dict[str, Any] = json.loads(dataset_path.read_text(encoding="utf-8"))
    cases: list[EvaluationCaseInput] = []
    outputs: list[CaseOutput] = []
    for raw in payload["cases"]:
        cases.append(
            EvaluationCaseInput(
                case_key=raw["case_key"],
                question=raw["question"],
                expected_answer_terms=tuple(raw["expected_answer_terms"]),
                expected_document_ids=tuple(raw["expected_document_ids"]),
                expected_action=raw["expected_action"],
                forbidden_action=raw["forbidden_action"],
                category=raw["category"],
                difficulty=raw["difficulty"],
                risk_level=raw["risk_level"],
            )
        )
        fixture = raw["fixture_output"]
        outputs.append(
            CaseOutput(
                answer=fixture["answer"],
                document_ids=tuple(fixture["document_ids"]),
                action=fixture["action"],
                citations_supported=fixture["citations_supported"],
                pii_leaked=fixture["pii_leaked"],
            )
        )
    scores = [evaluate_case(case, output) for case, output in zip(cases, outputs, strict=True)]
    run_id = str(uuid.uuid4())
    digest = dataset_hash(cases)
    output_directory.mkdir(parents=True, exist_ok=True)
    json_path = output_directory / f"{run_id}.json"
    markdown_path = output_directory / f"{run_id}.md"
    html_path = output_directory / f"{run_id}.html"
    result = {
        "run_id": run_id,
        "dataset_name": payload["name"],
        "dataset_version": payload["version"],
        "dataset_sha256": digest,
        "sample_count": len(scores),
        "evaluator": "resolveai-deterministic-v1",
        "results": [asdict(score) for score in scores],
    }
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    markdown_path.write_text(
        render_markdown_report(run_id=run_id, dataset_sha256=digest, scores=scores),
        encoding="utf-8",
    )
    html_path.write_text(
        render_html_report(run_id=run_id, dataset_sha256=digest, scores=scores),
        encoding="utf-8",
    )
    return json_path, markdown_path, html_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic ResolveAI evaluations")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/evaluations"))
    args = parser.parse_args()
    json_path, markdown_path, html_path = run(args.dataset, args.output)
    print(json_path)
    print(markdown_path)
    print(html_path)


if __name__ == "__main__":
    main()

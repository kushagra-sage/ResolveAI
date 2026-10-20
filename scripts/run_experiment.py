import argparse
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from resolveai.experiments import paired_delta
from resolveai.retrieval_quality import lexical_score, rerank_score, rewrite_query


def run(dataset: Path, output: Path) -> Path:
    payload: dict[str, Any] = json.loads(dataset.read_text(encoding="utf-8"))
    baseline: dict[str, float] = {}
    candidate: dict[str, float] = {}
    for case in payload["cases"]:
        key = str(case["case_key"])
        question = str(case["question"])
        answer = str(case["fixture_output"]["answer"])
        baseline[key] = lexical_score(question, answer)
        rewritten = rewrite_query(question)
        candidate[key] = rerank_score(rewritten, answer, str(case["category"]), baseline[key])
    result = {
        "experiment_id": str(uuid.uuid4()),
        "created_at": datetime.now(tz=UTC).isoformat(),
        "dataset": {"name": payload["name"], "version": payload["version"]},
        "baseline": {"name": "lexical-v1", "case_scores": baseline},
        "candidate": {"name": "rewrite-rerank-v1", "case_scores": candidate},
        "paired_delta": paired_delta(baseline, candidate),
        "sample_count": len(baseline),
        "scope": "deterministic local experiment; not a production quality claim",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paired ResolveAI retrieval experiment")
    parser.add_argument("dataset", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/experiments/paired-smoke.json")
    )
    args = parser.parse_args()
    print(run(args.dataset, args.output))


if __name__ == "__main__":
    main()

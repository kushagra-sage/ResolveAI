"""Create a deterministic, counterbalanced, blinded human-study assignment pack."""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

SEED = 20261008


def prepare(dataset: Path, output: Path, participants: int = 12) -> dict[str, object]:
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
    by_category: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_category.setdefault(str(row["category"]), []).append(row)
    rng = random.Random(SEED)
    selected: list[dict[str, object]] = []
    for category in sorted(by_category)[:12]:
        candidates = by_category[category].copy()
        rng.shuffle(candidates)
        selected.extend(candidates[:2])
    if len(selected) != 24:
        raise RuntimeError("expected 24 balanced study cases")
    output.mkdir(parents=True, exist_ok=True)
    assignments: list[list[object]] = []
    keys: list[list[object]] = []
    for participant_index in range(participants):
        participant = f"P{participant_index + 1:03d}"
        a_system, b_system = (
            ("resolveai", "baseline")
            if participant_index % 2 == 0
            else ("baseline", "resolveai")
        )
        keys.extend([[participant, "A", a_system], [participant, "B", b_system]])
        set_index = participant_index % 2
        ordered = [case for index, case in enumerate(selected) if index % 2 == set_index]
        rng.shuffle(ordered)
        for position, case in enumerate(ordered, 1):
            code = "A" if (participant_index + position) % 2 == 0 else "B"
            assignments.append(
                [participant, position, case["id"], case["category"], code]
            )
    with (output / "assignments.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["participant_id", "position", "case_id", "category", "system_code"])
        writer.writerows(assignments)
    with (output / "blinding-key.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["participant_id", "system_code", "actual_system"])
        writer.writerows(keys)
    (output / "consent-script.md").write_text(
        "# Consent script\n\nParticipation is voluntary. The study evaluates two support-system "
        "responses using synthetic or approved public cases. Do not enter personal or customer "
        "information. You may stop at any time. Responses are stored under a pseudonymous ID "
        "and reported only in aggregate. Contact the study supervisor before data collection "
        "to confirm institutional approval and retention requirements.\n",
        encoding="utf-8",
    )
    (output / "analysis-plan.md").write_text(
        "# Pre-specified analysis\n\n"
        "Primary outcomes: correctness and action-safety ratings. Secondary outcomes: evidence "
        "support, clarity, trust, approval accuracy, and decision time. Join responses to the "
        "blinding key only after collection closes. Report participant count, completed ratings, "
        "missingness, system means, paired participant-level differences, 95% bootstrap confidence "
        "intervals, and inter-rater agreement. Do not remove unfavorable responses after "
        "unblinding.\n",
        encoding="utf-8",
    )
    return {
        "seed": SEED,
        "participants": participants,
        "case_pool": len(selected),
        "cases_per_participant": len(selected) // 2,
        "assignments": len(assignments),
        "status": "prepared_not_conducted",
    }


if __name__ == "__main__":
    print(
        json.dumps(
            prepare(
                Path("datasets/synthetic/resolveai-benchmark-v1.jsonl"),
                Path("research/human-study"),
            ),
            indent=2,
        )
    )

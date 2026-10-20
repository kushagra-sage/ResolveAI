import json
from pathlib import Path


def test_synthetic_benchmark_is_labelled_reproducible_and_complete() -> None:
    path = Path(__file__).parents[2] / "datasets" / "synthetic" / "resolveai-benchmark-v1.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    required_categories = {
        "support",
        "refund",
        "payment_issue",
        "order_status",
        "inventory",
        "delivery",
        "quality",
        "prompt_injection",
        "pii_leakage",
        "policy_violation",
        "tool_use",
        "agent_handoff",
        "anomaly",
        "root_cause",
    }
    assert len(rows) == 168
    assert {row["category"] for row in rows} == required_categories
    assert len({row["id"] for row in rows}) == len(rows)
    assert all(row["synthetic"] is True for row in rows)
    assert all(row["seed"] == 20261006 for row in rows)
    assert all(
        set(row["labels"])
        == {
            "expected_intent",
            "expected_action",
            "expected_risk",
            "expected_safety_decision",
            "expected_retrieval_target",
        }
        for row in rows
    )

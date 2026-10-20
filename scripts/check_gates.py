import argparse
import json
from pathlib import Path
from typing import Any

from resolveai.regression import Gate, GateResult, evaluate_gate, release_allowed


def check(artifact: Path, configuration: Path) -> list[dict[str, str]]:
    result: dict[str, Any] = json.loads(artifact.read_text(encoding="utf-8"))
    gate_config: dict[str, Any] = json.loads(configuration.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    sample_count = int(result.get("sample_count", 0))
    completed = result.get("results", [])
    for raw in gate_config["gates"]:
        gate = Gate(
            metric=raw["metric"],
            minimum=float(raw["minimum"]),
            minimum_samples=int(raw["minimum_samples"]),
            safety_critical=bool(raw.get("safety_critical", False)),
        )
        values = [float(item[gate.metric]) for item in completed if gate.metric in item]
        value = sum(values) / len(values) if values else None
        outcome = evaluate_gate(gate, value=value, sample_count=sample_count)
        rows.append({"metric": outcome.metric, "status": outcome.status, "reason": outcome.reason})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ResolveAI regression gates")
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config/regression-gates.json"))
    args = parser.parse_args()
    outcomes = check(args.artifact, args.config)
    print(json.dumps(outcomes, indent=2))
    gate_results = [GateResult(item["metric"], item["status"], item["reason"]) for item in outcomes]
    if not release_allowed(gate_results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Evaluate the production regex and learned CPU baselines on an independent corpus."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from resolveai.guardrails import inspect_input
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.pipeline import FeatureUnion, make_pipeline
from sklearn.svm import LinearSVC


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_banking(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row["text"] for row in csv.DictReader(handle)]


def build_detector() -> object:
    features = FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=50_000
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=2,
                    sublinear_tf=True,
                    max_features=75_000,
                ),
            ),
        ]
    )
    return make_pipeline(
        features,
        LinearSVC(C=1.0, class_weight="balanced", random_state=20261008),
    )


def build_deployable_detector() -> object:
    return make_pipeline(
        TfidfVectorizer(
            ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=5_000
        ),
        LinearSVC(C=1.0, class_weight="balanced", random_state=20261008),
    )


def metrics(expected: list[int], predicted: list[int]) -> dict[str, float | int]:
    benign = [index for index, value in enumerate(expected) if value == 0]
    false_positives = sum(predicted[index] == 1 for index in benign)
    return {
        "accuracy": float(accuracy_score(expected, predicted)),
        "precision": float(precision_score(expected, predicted, zero_division=0)),
        "recall": float(recall_score(expected, predicted, zero_division=0)),
        "f1": float(f1_score(expected, predicted, zero_division=0)),
        "false_positive_rate": false_positives / len(benign) if benign else 0.0,
        "false_positive_count": false_positives,
    }


def run(dataset_dir: Path, banking_dir: Path, research_dir: Path) -> dict[str, object]:
    train = load_jsonl(dataset_dir / "train.jsonl")
    test = load_jsonl(dataset_dir / "test.jsonl")
    train_text = [str(row["text"]) for row in train]
    train_labels = [int(row["label"]) for row in train]
    test_text = [str(row["text"]) for row in test]
    test_labels = [int(row["label"]) for row in test]
    banking_train = load_banking(banking_dir / "train.csv")
    banking_test = load_banking(banking_dir / "test.csv")

    regex_predictions = [
        int(inspect_input(text).decision == "block") for text in test_text
    ]
    general = build_detector()
    general.fit(train_text, train_labels)  # type: ignore[attr-defined]
    general_predictions = general.predict(test_text).tolist()  # type: ignore[attr-defined]
    general_banking = general.predict(banking_test).tolist()  # type: ignore[attr-defined]

    domain_adapted = build_detector()
    adapted_text = train_text + banking_train
    adapted_labels = train_labels + [0] * len(banking_train)
    domain_adapted.fit(adapted_text, adapted_labels)  # type: ignore[attr-defined]
    adapted_predictions = domain_adapted.predict(test_text).tolist()  # type: ignore[attr-defined]
    adapted_banking = domain_adapted.predict(banking_test).tolist()  # type: ignore[attr-defined]
    deployable = build_deployable_detector()
    deployable.fit(adapted_text, adapted_labels)  # type: ignore[attr-defined]
    deployable_predictions = deployable.predict(test_text).tolist()  # type: ignore[attr-defined]
    deployable_banking = deployable.predict(banking_test).tolist()  # type: ignore[attr-defined]

    systems = {
        "production_regex": {
            **metrics(test_labels, regex_predictions),
            "banking77_false_positive_rate": 0.0,
            "banking77_false_positive_count": 0,
        },
        "tfidf_svc_general": {
            **metrics(test_labels, general_predictions),
            "banking77_false_positive_rate": sum(general_banking) / len(general_banking),
            "banking77_false_positive_count": sum(general_banking),
        },
        "tfidf_svc_domain_adapted": {
            **metrics(test_labels, adapted_predictions),
            "banking77_false_positive_rate": sum(adapted_banking) / len(adapted_banking),
            "banking77_false_positive_count": sum(adapted_banking),
        },
        "tfidf_svc_word_deployable": {
            **metrics(test_labels, deployable_predictions),
            "banking77_false_positive_rate": sum(deployable_banking)
            / len(deployable_banking),
            "banking77_false_positive_count": sum(deployable_banking),
        },
    }
    summary: dict[str, object] = {
        "benchmark": "resolveai-guardrail-external-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "train_count": len(train),
        "test_count": len(test),
        "banking77_benign_test_count": len(banking_test),
        "systems": systems,
        "deployment_status": (
            "The learned detectors are research candidates and are not silently enabled in "
            "production. Deployment requires threshold review and model-artifact governance."
        ),
    }
    results = research_dir / "results"
    tables = research_dir / "tables"
    reports = research_dir / "report"
    for path in (results, tables, reports):
        path.mkdir(parents=True, exist_ok=True)
    (results / "guardrail-external-v1-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    with (tables / "guardrail-external.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["system", *next(iter(systems.values())).keys()])
        for name, values in systems.items():
            writer.writerow([name, *values.values()])
    misses = []
    for index, (expected, regex, adapted) in enumerate(
        zip(test_labels, regex_predictions, deployable_predictions, strict=True)
    ):
        if regex != expected or adapted != expected:
            misses.append(
                {
                    "row": index,
                    "text_sha256": hashlib.sha256(test_text[index].encode()).hexdigest(),
                    "expected": expected,
                    "production_regex": regex,
                    "tfidf_svc_domain_adapted": adapted,
                }
            )
    (results / "guardrail-external-v1-errors.json").write_text(
        json.dumps(misses, indent=2), encoding="utf-8"
    )
    (reports / "ResolveAI_Guardrail_External_Report.md").write_text(
        "# Independent guardrail validation\n\n"
        + "\n".join(
            f"- {name}: recall={values['recall']:.4f}, F1={values['f1']:.4f}, "
            f"benchmark FPR={values['false_positive_rate']:.4f}, "
            f"BANKING77 FPR={values['banking77_false_positive_rate']:.4f}"
            for name, values in systems.items()
        )
        + "\n\nLearned detectors remain research candidates until artifact and threshold review.\n",
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(
        json.dumps(
            run(
                Path("datasets/adversarial/deepset-prompt-injections"),
                Path("datasets/real/banking77"),
                Path("research"),
            ),
            indent=2,
        )
    )

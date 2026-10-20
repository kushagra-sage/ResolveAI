"""Run a reproducible external validation on real BANKING77 support queries."""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

from resolveai.guardrails import inspect_input
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, f1_score
from sklearn.pipeline import FeatureUnion, make_pipeline
from sklearn.svm import LinearSVC

TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def features(text: str) -> list[str]:
    words = TOKEN.findall(text.lower())
    return [f"u:{word}" for word in words] + [
        f"b:{left}_{right}" for left, right in pairwise(words)
    ]


class MultinomialNB:
    def __init__(self, alpha: float = 0.1) -> None:
        self.alpha = alpha
        self.class_counts: Counter[str] = Counter()
        self.feature_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.feature_totals: Counter[str] = Counter()
        self.vocabulary: set[str] = set()

    def fit(self, rows: list[dict[str, str]]) -> None:
        for row in rows:
            label = row["category"]
            counts = Counter(features(row["text"]))
            self.class_counts[label] += 1
            self.feature_counts[label].update(counts)
            self.feature_totals[label] += sum(counts.values())
            self.vocabulary.update(counts)

    def predict(self, text: str) -> str:
        counts = Counter(features(text))
        total_rows = sum(self.class_counts.values())
        vocabulary_size = len(self.vocabulary)
        best_label = ""
        best_score = -math.inf
        for label, class_count in self.class_counts.items():
            score = math.log(class_count / total_rows)
            denominator = self.feature_totals[label] + self.alpha * vocabulary_size
            for feature, count in counts.items():
                numerator = self.feature_counts[label][feature] + self.alpha
                score += count * math.log(numerator / denominator)
            if score > best_score:
                best_label, best_score = label, score
        return best_label


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def macro_f1(expected: list[str], predicted: list[str]) -> float:
    values = []
    for label in sorted(set(expected)):
        pairs = tuple(zip(expected, predicted, strict=True))
        true_positive = sum(a == label and b == label for a, b in pairs)
        false_positive = sum(a != label and b == label for a, b in pairs)
        false_negative = sum(a == label and b != label for a, b in pairs)
        precision_denominator = true_positive + false_positive
        recall_denominator = true_positive + false_negative
        precision = true_positive / precision_denominator if precision_denominator else 0
        recall = true_positive / recall_denominator if recall_denominator else 0
        values.append(2 * precision * recall / (precision + recall) if precision + recall else 0)
    return sum(values) / len(values)


def run(data_dir: Path, research_dir: Path) -> dict[str, object]:
    train = read_rows(data_dir / "train.csv")
    test = read_rows(data_dir / "test.csv")
    model = MultinomialNB()
    model.fit(train)
    expected = [row["category"] for row in test]
    predicted = [model.predict(row["text"]) for row in test]
    linear_model = make_pipeline(
        FeatureUnion(
            [
                (
                    "word",
                    TfidfVectorizer(
                        ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=75_000
                    ),
                ),
                (
                    "char",
                    TfidfVectorizer(
                        analyzer="char_wb",
                        ngram_range=(3, 5),
                        min_df=2,
                        sublinear_tf=True,
                        max_features=100_000,
                    ),
                ),
            ]
        ),
        LinearSVC(C=1.5, random_state=20261008),
    )
    linear_model.fit([row["text"] for row in train], [row["category"] for row in train])
    linear_predictions = linear_model.predict([row["text"] for row in test]).tolist()
    guardrails = [inspect_input(row["text"]) for row in test]
    blocked = [result for result in guardrails if result.decision == "block"]
    summary: dict[str, object] = {
        "benchmark": "banking77-external-validation-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_type": "real-world public customer-support queries",
        "license": "CC-BY-4.0",
        "train_count": len(train),
        "test_count": len(test),
        "intent_count": len(set(expected)),
        "multinomial_nb_accuracy": sum(
            a == b for a, b in zip(expected, predicted, strict=True)
        )
        / len(test),
        "multinomial_nb_macro_f1": macro_f1(expected, predicted),
        "tfidf_linear_svc_accuracy": accuracy_score(expected, linear_predictions),
        "tfidf_linear_svc_macro_f1": f1_score(
            expected, linear_predictions, average="macro"
        ),
        "input_guardrail_false_positive_rate": len(blocked) / len(test),
        "input_guardrail_false_positive_count": len(blocked),
        "limitations": [
            "BANKING77 evaluates intent classification and benign-input safety, "
            "not end-to-end actions.",
            "The public banking domain does not represent all ResolveAI commerce workflows.",
            "The TF-IDF LinearSVC is a competitive classical intent baseline, "
            "not an agentic RAG or hosted-LLM baseline.",
        ],
    }
    results = research_dir / "results"
    tables = research_dir / "tables"
    reports = research_dir / "report"
    for directory in (results, tables, reports):
        directory.mkdir(parents=True, exist_ok=True)
    (results / "banking77-validation-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    with (tables / "banking77-validation.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "row",
                "expected_intent",
                "naive_bayes_intent",
                "tfidf_linear_svc_intent",
                "guardrail_decision",
            ]
        )
        rows = zip(expected, predicted, guardrails, strict=True)
        for index, (actual, guess, result) in enumerate(rows, 1):
            writer.writerow(
                [index, actual, guess, linear_predictions[index - 1], result.decision]
            )
    (reports / "BANKING77_External_Validation.md").write_text(
        "# BANKING77 external validation\n\n"
        f"- Train/test queries: {len(train):,}/{len(test):,}\n"
        f"- Intents: {len(set(expected))}\n"
        f"- Multinomial Naive Bayes accuracy: {summary['multinomial_nb_accuracy']:.4f}\n"
        f"- Macro F1: {summary['multinomial_nb_macro_f1']:.4f}\n"
        f"- TF-IDF LinearSVC accuracy: {summary['tfidf_linear_svc_accuracy']:.4f}\n"
        f"- TF-IDF LinearSVC macro F1: {summary['tfidf_linear_svc_macro_f1']:.4f}\n"
        f"- ResolveAI input-guardrail false-positive rate on benign queries: "
        f"{summary['input_guardrail_false_positive_rate']:.4f} ({len(blocked)}/{len(test)})\n\n"
        "These results add a real-query external-validation track. They do not replace the "
        "synthetic end-to-end benchmark because BANKING77 lacks action, policy, retrieval, "
        "approval, and outcome labels.\n",
        encoding="utf-8",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run(Path("datasets/real/banking77"), Path("research")), indent=2))

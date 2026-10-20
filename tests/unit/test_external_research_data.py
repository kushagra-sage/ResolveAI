import hashlib
import json
from pathlib import Path


def test_prompt_injection_corpus_is_pinned_and_checksum_verified() -> None:
    root = (
        Path(__file__).parents[2]
        / "datasets"
        / "adversarial"
        / "deepset-prompt-injections"
    )
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["revision"] == "4f61ecb038e9c3fb77e21034b22511b523772cdd"
    assert manifest["splits"]["train"] == {"rows": 546, "attack": 203, "benign": 343}
    assert manifest["splits"]["test"] == {"rows": 116, "attack": 60, "benign": 56}
    for name, checksum in manifest["checksums"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == checksum


def test_external_results_preserve_unfavorable_guardrail_result() -> None:
    result_path = (
        Path(__file__).parents[2]
        / "research"
        / "results"
        / "guardrail-external-v1-summary.json"
    )
    summary = json.loads(result_path.read_text(encoding="utf-8"))
    assert summary["systems"]["production_regex"]["recall"] == 0.0
    candidate = summary["systems"]["tfidf_svc_domain_adapted"]
    assert candidate["recall"] == 0.8
    assert candidate["banking77_false_positive_count"] == 0

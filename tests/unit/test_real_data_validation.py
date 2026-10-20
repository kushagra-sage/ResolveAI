import csv
import hashlib
import json
from pathlib import Path

from resolveai.guardrails import inspect_input


def test_banking77_is_pinned_verified_and_benign_for_input_guardrail() -> None:
    root = Path(__file__).parents[2] / "datasets" / "real" / "banking77"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["upstream_commit"] == "57ec275d8078af65b7731c2a98be812d844a6d6b"
    assert manifest["license"] == "CC-BY-4.0"
    expected = {
        "train.csv": "b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b",
        "test.csv": "d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d",
    }
    for name, checksum in expected.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == checksum

    with (root / "test.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3_080
    assert len({row["category"] for row in rows}) == 77
    assert all(inspect_input(row["text"]).decision == "allow" for row in rows)

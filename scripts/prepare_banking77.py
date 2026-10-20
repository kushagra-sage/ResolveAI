"""Download and verify the CC BY 4.0 BANKING77 dataset from its official repository."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

UPSTREAM_COMMIT = "57ec275d8078af65b7731c2a98be812d844a6d6b"
BASE_URL = (
    "https://raw.githubusercontent.com/PolyAI-LDN/task-specific-datasets/"
    f"{UPSTREAM_COMMIT}"
)
FILES = {
    "train.csv": (
        f"{BASE_URL}/banking_data/train.csv",
        "b06e26ac675513959a63135f11b94ea7786ed02da65db93a5650d8838cbc664b",
    ),
    "test.csv": (
        f"{BASE_URL}/banking_data/test.csv",
        "d12d6e3bc4c3103966ae786dc435913c0c563dfa328f5a3646d0e62cfeeb474d",
    ),
}
LICENSE_URL = f"{BASE_URL}/LICENSE"
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
LONG_NUMBER = re.compile(r"\b\d{10,19}\b")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ResolveAI-research/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def inspect_split(path: Path) -> dict[str, object]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    labels = sorted({row["category"] for row in rows})
    return {
        "rows": len(rows),
        "labels": len(labels),
        "email_like_matches": sum(bool(EMAIL.search(row["text"])) for row in rows),
        "long_number_matches": sum(bool(LONG_NUMBER.search(row["text"])) for row in rows),
    }


def prepare(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=True)
    checksums: dict[str, str] = {}
    for name, (url, expected_sha256) in FILES.items():
        destination = output / name
        data = destination.read_bytes() if destination.exists() else download(url)
        actual_sha256 = digest(data)
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"checksum mismatch for {name}: expected {expected_sha256}, got {actual_sha256}"
            )
        destination.write_bytes(data)
        checksums[name] = actual_sha256
    license_path = output / "LICENSE"
    if not license_path.exists():
        license_path.write_bytes(download(LICENSE_URL))
    manifest = {
        "dataset": "BANKING77",
        "source_repository": "https://github.com/PolyAI-LDN/task-specific-datasets",
        "paper": "https://aclanthology.org/2020.nlp4convai-1.5/",
        "license": "CC-BY-4.0",
        "upstream_commit": UPSTREAM_COMMIT,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "checksums": checksums,
        "splits": {
            "train": inspect_split(output / "train.csv"),
            "test": inspect_split(output / "test.csv"),
        },
        "privacy_note": (
            "Public research queries are not assumed anonymous. Automated email and long-number "
            "screening is recorded above; review remains required before redistribution or display."
        ),
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output / "README.md").write_text(
        "# BANKING77 external-validation data\n\n"
        "Downloaded from the official PolyAI repository at the commit recorded in "
        "`manifest.json`; files are checksum verified. The upstream dataset is licensed "
        "CC BY 4.0. Cite Casanueva et al. (2020), *Efficient Intent Detection with Dual "
        "Sentence Encoders*, DOI: 10.18653/v1/2020.nlp4convai-1.5.\n\n"
        "This dataset is used only for external intent and benign-input safety validation. "
        "It does not contain ResolveAI action, policy, retrieval, or business-outcome labels.\n",
        encoding="utf-8",
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(prepare(Path("datasets/real/banking77")), indent=2))

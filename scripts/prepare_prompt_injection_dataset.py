"""Acquire the public deepset prompt-injection benchmark with provenance metadata."""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATASET = "deepset/prompt-injections"
REVISION = "4f61ecb038e9c3fb77e21034b22511b523772cdd"
EXPECTED_COUNTS = {"train": 546, "test": 116}


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "ResolveAI-research/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def fetch_split(split: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    offset = 0
    while offset < EXPECTED_COUNTS[split]:
        query = urllib.parse.urlencode(
            {
                "dataset": DATASET,
                "config": "default",
                "split": split,
                "offset": offset,
                "length": min(100, EXPECTED_COUNTS[split] - offset),
            }
        )
        response = fetch_json(f"https://datasets-server.huggingface.co/rows?{query}")
        page = [item["row"] for item in response["rows"]]
        rows.extend(page)
        offset += len(page)
        if not page:
            break
    if len(rows) != EXPECTED_COUNTS[split]:
        raise RuntimeError(
            f"unexpected {split} count: expected {EXPECTED_COUNTS[split]}, got {len(rows)}"
        )
    if any(set(row) != {"text", "label"} for row in rows):
        raise RuntimeError(f"unexpected {split} schema")
    return rows


def prepare(output: Path) -> dict[str, object]:
    metadata = fetch_json(
        f"https://huggingface.co/api/datasets/{DATASET}/revision/{REVISION}"
    )
    if metadata.get("sha") != REVISION:
        raise RuntimeError("upstream revision did not resolve to the pinned commit")
    output.mkdir(parents=True, exist_ok=True)
    checksums: dict[str, str] = {}
    counts: dict[str, dict[str, int]] = {}
    for split in EXPECTED_COUNTS:
        rows = fetch_split(split)
        encoded = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        destination = output / f"{split}.jsonl"
        destination.write_text(encoded, encoding="utf-8")
        checksums[destination.name] = hashlib.sha256(destination.read_bytes()).hexdigest()
        counts[split] = {
            "rows": len(rows),
            "attack": sum(int(row["label"]) == 1 for row in rows),
            "benign": sum(int(row["label"]) == 0 for row in rows),
        }
    manifest: dict[str, object] = {
        "dataset": DATASET,
        "source": "https://huggingface.co/datasets/deepset/prompt-injections",
        "revision": REVISION,
        "downloaded_at": datetime.now(UTC).isoformat(),
        "license_note": (
            "The repository header lists Apache-2.0 while dataset_info lists CC-BY-4.0; "
            "both notices are preserved and downstream users must review the source card."
        ),
        "checksums": checksums,
        "splits": counts,
        "intended_use": "Independent prompt-injection detector evaluation.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(prepare(Path("datasets/adversarial/deepset-prompt-injections")), indent=2))

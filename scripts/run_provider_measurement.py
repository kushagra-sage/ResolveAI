"""Measure real latency, token usage, and optional dated pricing for a model endpoint."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from resolveai.adapters.mock import DeterministicModelAdapter


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * quantile))
    return ordered[index]


def load_prompts(path: Path, limit: int) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [
        "Resolve this support request concisely and safely: " + row["text"]
        for row in rows[:limit]
    ]


def openai_compatible_call(
    *, base_url: str, api_key: str | None, model: str, prompt: str, timeout: float
) -> dict[str, object]:
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
    ).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body: dict[str, Any] = json.loads(response.read())
    usage = body.get("usage") or {}
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError("provider returned no choices")
    text = str(choices[0].get("message", {}).get("content", ""))
    if not text.strip():
        raise RuntimeError("provider returned empty content")
    return {
        "text": text,
        "provider": "openai-compatible",
        "model": body.get("model", model),
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
    }


def run(args: argparse.Namespace) -> dict[str, object]:
    prompts = load_prompts(args.dataset, args.sample_size)
    adapter = DeterministicModelAdapter()
    rows: list[dict[str, object]] = []
    for index, prompt in enumerate(prompts, 1):
        started = time.perf_counter()
        if args.mode == "deterministic":
            response = adapter.complete(prompt)
        else:
            response = openai_compatible_call(
                base_url=args.base_url,
                api_key=args.api_key,
                model=args.model,
                prompt=prompt,
                timeout=args.timeout,
            )
        latency_ms = (time.perf_counter() - started) * 1_000
        input_tokens = response.get("input_tokens")
        output_tokens = response.get("output_tokens")
        cost_usd = None
        if (
            isinstance(input_tokens, int)
            and isinstance(output_tokens, int)
            and args.input_price_per_million is not None
            and args.output_price_per_million is not None
        ):
            cost_usd = (
                input_tokens * args.input_price_per_million
                + output_tokens * args.output_price_per_million
            ) / 1_000_000
        rows.append(
            {
                "case": index,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "latency_ms": latency_ms,
                "provider": response["provider"],
                "model": response["model"],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost_usd,
            }
        )
    latencies = [float(row["latency_ms"]) for row in rows]
    known_costs = [float(row["cost_usd"]) for row in rows if row["cost_usd"] is not None]
    summary: dict[str, object] = {
        "benchmark": f"provider-measurement-{args.mode}",
        "generated_at": datetime.now(UTC).isoformat(),
        "sample_count": len(rows),
        "mode": args.mode,
        "model": args.model if args.mode != "deterministic" else adapter.model,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "mean_latency_ms": statistics.fmean(latencies),
        "mean_input_tokens": statistics.fmean(
            int(row["input_tokens"]) for row in rows if row["input_tokens"] is not None
        ),
        "mean_output_tokens": statistics.fmean(
            int(row["output_tokens"]) for row in rows if row["output_tokens"] is not None
        ),
        "mean_cost_usd": statistics.fmean(known_costs) if known_costs else None,
        "price_snapshot_date": args.price_snapshot_date,
        "input_price_per_million_usd": args.input_price_per_million,
        "output_price_per_million_usd": args.output_price_per_million,
        "scope_note": (
            "Deterministic mode measures local adapter overhead and has no provider bill."
            if args.mode == "deterministic"
            else "OpenAI-compatible mode measures the configured network endpoint."
        ),
    }
    results = args.research_dir / "results"
    results.mkdir(parents=True, exist_ok=True)
    stem = f"provider-{args.mode}-v1"
    (results / f"{stem}-summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (results / f"{stem}-raw.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("deterministic", "openai-compatible"),
        default="deterministic",
    )
    parser.add_argument("--dataset", type=Path, default=Path("datasets/real/banking77/test.csv"))
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--research-dir", type=Path, default=Path("research"))
    parser.add_argument(
        "--base-url", default=os.getenv("RESOLVEAI_MODEL_BASE_URL", "http://localhost:11434/v1")
    )
    parser.add_argument("--model", default=os.getenv("RESOLVEAI_MODEL_NAME", "resolveai-local"))
    parser.add_argument("--api-key", default=os.getenv("RESOLVEAI_MODEL_API_KEY") or None)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--input-price-per-million", type=float)
    parser.add_argument("--output-price-per-million", type=float)
    parser.add_argument("--price-snapshot-date")
    args = parser.parse_args()
    if args.sample_size < 1:
        parser.error("--sample-size must be positive")
    prices = (args.input_price_per_million, args.output_price_per_million)
    if any(price is not None and price < 0 for price in prices):
        parser.error("prices must be non-negative")
    if (prices[0] is None) != (prices[1] is None):
        parser.error("both input and output prices must be supplied together")
    if prices[0] is not None and not args.price_snapshot_date:
        parser.error("--price-snapshot-date is required with pricing")
    return args


if __name__ == "__main__":
    print(json.dumps(run(parse_args()), indent=2))

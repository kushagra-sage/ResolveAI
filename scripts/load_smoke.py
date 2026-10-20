import argparse
import json
import platform
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import httpx


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile without samples")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def run(url: str, requests: int, concurrency: int) -> dict[str, object]:
    def one(_: int) -> tuple[float, int]:
        started = time.perf_counter()
        response = httpx.get(url, timeout=5.0)
        return (time.perf_counter() - started) * 1000, response.status_code

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(one, range(requests)))
    latencies = [latency for latency, _status in results]
    errors = sum(1 for _latency, status in results if status >= 400)
    return {
        "timestamp_utc": datetime.now(tz=UTC).isoformat(),
        "target": url,
        "request_count": requests,
        "concurrency": concurrency,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "latency_ms": {
            "mean": statistics.fmean(latencies),
            "p50": percentile(latencies, 0.50),
            "p95": percentile(latencies, 0.95),
            "max": max(latencies),
        },
        "error_count": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Small reproducible ResolveAI load smoke")
    parser.add_argument("--url", default="http://127.0.0.1:8000/health/live")
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("artifacts/load-smoke.json"))
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        raise SystemExit("requests and concurrency must be positive")
    result = run(args.url, args.requests, args.concurrency)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()

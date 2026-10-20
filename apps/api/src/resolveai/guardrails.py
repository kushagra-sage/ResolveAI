import hashlib
import re
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    guardrail: str
    decision: str
    reason: str
    sanitized_text: str
    content_sha256: str
    latency_ms: int


INJECTION_PATTERNS = (
    re.compile(r"\bignore (all |the )?(previous|prior|system) (rules|instructions)\b", re.I),
    re.compile(r"\b(system administrator|admin) approved this\b", re.I),
    re.compile(r"\breveal (the |your )?(system prompt|secrets?|environment variables?)\b", re.I),
    re.compile(r"\b(print|show|dump)\b.*\b(secrets?|environment variables?)\b", re.I),
    re.compile(r"\bcall (the )?refund (function|tool)\b.*\b(times|repeatedly)\b", re.I),
    re.compile(r"\buse (this |the )?(retrieved )?document'?s instructions instead\b", re.I),
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\b(?:api[_-]?key|password|secret)\s*[:=]\s*\S+", re.I),
    re.compile(r"\b\d{13,19}\b"),
)
PII_PATTERNS = (
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?:\+?91[- ]?)?[6-9]\d{9}\b"), "[REDACTED_PHONE]"),
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _redact(text: str) -> str:
    sanitized = text
    for pattern, replacement in PII_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


def inspect_input(text: str) -> GuardrailResult:
    started = time.perf_counter()
    reason = "accepted"
    decision = "allow"
    if any(pattern.search(text) for pattern in INJECTION_PATTERNS):
        decision = "block"
        reason = "prompt_injection_pattern"
    sanitized = _redact(text)
    return GuardrailResult(
        guardrail="input_v1",
        decision=decision,
        reason=reason,
        sanitized_text=sanitized,
        content_sha256=_digest(text),
        latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
    )


def quarantine_external_content(text: str) -> GuardrailResult:
    started = time.perf_counter()
    detected = any(pattern.search(text) for pattern in INJECTION_PATTERNS)
    sanitized = _redact(text)
    if detected:
        sanitized = "[QUARANTINED_UNTRUSTED_INSTRUCTIONS]"
    else:
        sanitized = f"<untrusted-data>\n{sanitized}\n</untrusted-data>"
    return GuardrailResult(
        guardrail="external_content_v1",
        decision="quarantine" if detected else "allow_as_data",
        reason="embedded_instruction" if detected else "external_content_delimited",
        sanitized_text=sanitized,
        content_sha256=_digest(text),
        latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
    )


def inspect_output(text: str, supported_citation_ids: set[str]) -> GuardrailResult:
    started = time.perf_counter()
    cited = set(re.findall(r"\[cite:([0-9a-fA-F-]{36})\]", text))
    reason = "accepted"
    decision = "allow"
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        decision, reason = "block", "secret_or_payment_data"
    elif not cited.issubset(supported_citation_ids):
        decision, reason = "block", "unsupported_citation"
    return GuardrailResult(
        guardrail="output_v1",
        decision=decision,
        reason=reason,
        sanitized_text=_redact(text),
        content_sha256=_digest(text),
        latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
    )

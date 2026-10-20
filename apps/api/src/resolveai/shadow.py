from dataclasses import dataclass

from resolveai.guardrails import inspect_input


@dataclass(frozen=True, slots=True)
class ShadowRequest:
    sanitized_input: str
    candidate_version: str
    writes_enabled: bool = False


@dataclass(frozen=True, slots=True)
class ShadowResult:
    candidate_version: str
    response: str
    proposed_action: str | None
    side_effect_attempted: bool


def make_shadow_request(raw_input: str, candidate_version: str) -> ShadowRequest:
    inspected = inspect_input(raw_input)
    return ShadowRequest(inspected.sanitized_text, candidate_version, writes_enabled=False)


def validate_shadow_result(request: ShadowRequest, result: ShadowResult) -> None:
    if request.writes_enabled:
        raise ValueError("shadow identity must be write-disabled")
    if result.side_effect_attempted:
        raise ValueError("shadow candidate attempted a side effect")
    if result.candidate_version != request.candidate_version:
        raise ValueError("candidate version mismatch")

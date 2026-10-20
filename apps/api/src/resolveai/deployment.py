import hashlib
import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeploymentSelection:
    version: dict[str, object]
    lane: str
    allocation_percent: int


def canary_bucket(tenant_id: uuid.UUID, subject_key: str) -> int:
    digest = hashlib.sha256(f"{tenant_id}:{subject_key}".encode()).digest()
    return int.from_bytes(digest[:4], "big") % 100


def select_deployment(
    *,
    tenant_id: uuid.UUID,
    subject_key: str,
    stable: dict[str, object],
    candidate: dict[str, object] | None,
    candidate_allocation_percent: int,
) -> DeploymentSelection:
    if not 0 <= candidate_allocation_percent <= 100:
        raise ValueError("candidate allocation must be between zero and 100")
    candidate_selected = (
        candidate is not None
        and canary_bucket(tenant_id, subject_key) < candidate_allocation_percent
    )
    selected = candidate if candidate_selected else stable
    if selected is None:
        raise RuntimeError("deployment selection did not resolve a version")
    return DeploymentSelection(
        version=selected,
        lane="candidate" if candidate_selected else "stable",
        allocation_percent=candidate_allocation_percent,
    )


def next_canary_allocation(current: int, *, gates_passed: bool) -> int:
    if not 0 <= current <= 100:
        raise ValueError("current allocation must be between zero and 100")
    if not gates_passed:
        return 0
    stages = (0, 5, 25, 50, 100)
    return next((stage for stage in stages if stage > current), 100)

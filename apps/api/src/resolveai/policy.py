import hashlib
import json
import uuid
from dataclasses import dataclass
from enum import StrEnum


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


@dataclass(frozen=True, slots=True)
class ActionRequest:
    action: str
    tenant_id: uuid.UUID
    resource_tenant_id: uuid.UUID
    parameters: dict[str, object]


@dataclass(frozen=True, slots=True)
class PolicyContext:
    roles: frozenset[str]
    risk_level: str
    autonomous_refund_limit_minor: int = 5_000
    single_approval_limit_minor: int = 50_000
    hard_refund_ceiling_minor: int = 100_000


@dataclass(frozen=True, slots=True)
class PolicyResult:
    decision: PolicyDecision
    policy_id: str
    policy_version: str
    reason: str
    risk_level: str
    required_approver_role: str | None
    approvals_required: int
    action_digest: str


def action_digest(request: ActionRequest) -> str:
    payload = {
        "action": request.action,
        "tenant_id": str(request.tenant_id),
        "resource_tenant_id": str(request.resource_tenant_id),
        "parameters": request.parameters,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _result(
    request: ActionRequest,
    decision: PolicyDecision,
    policy_id: str,
    reason: str,
    risk_level: str,
    required_role: str | None = None,
    approvals_required: int = 0,
) -> PolicyResult:
    return PolicyResult(
        decision=decision,
        policy_id=policy_id,
        policy_version="2026-10-03.v2",
        reason=reason,
        risk_level=risk_level,
        required_approver_role=required_role,
        approvals_required=approvals_required,
        action_digest=action_digest(request),
    )


def evaluate_action(request: ActionRequest, context: PolicyContext) -> PolicyResult:
    if request.tenant_id != request.resource_tenant_id:
        return _result(request, PolicyDecision.DENY, "TENANT-001", "cross_tenant_resource", "high")
    if request.action in {"read_payment_secret", "change_payment_destination"}:
        return _result(
            request, PolicyDecision.DENY, "PAYMENT-001", "sensitive_payment_action", "high"
        )
    if request.action in {"read_order", "get_shipment"}:
        allowed = bool(context.roles & {"customer", "support_agent", "supervisor", "admin"})
        return _result(
            request,
            PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
            "READ-001",
            "authorized_read" if allowed else "role_not_authorized",
            "low",
        )
    if request.action in {"create_ticket", "add_ticket_note"}:
        allowed = bool(context.roles & {"support_agent", "supervisor", "admin"})
        return _result(
            request,
            PolicyDecision.ALLOW if allowed else PolicyDecision.DENY,
            "TICKET-001",
            "authorized_ticket_write" if allowed else "role_not_authorized",
            "low",
        )
    if request.action in {
        "inventory_transfer",
        "adjust_delivery_radius",
        "disable_sku",
        "quarantine_batch",
    }:
        allowed = bool(context.roles & {"supervisor", "admin"})
        if not allowed:
            return _result(
                request,
                PolicyDecision.DENY,
                "COMMERCE-001",
                "role_not_authorized",
                "high",
            )
        return _result(
            request,
            PolicyDecision.REQUIRE_APPROVAL,
            "COMMERCE-002",
            "operational_mutation_requires_approval",
            "high",
            "supervisor",
            1,
        )
    if request.action == "execute_refund":
        if not context.roles & {"support_agent", "supervisor", "admin"}:
            return _result(
                request, PolicyDecision.DENY, "REFUND-001", "role_not_authorized", "high"
            )
        amount = request.parameters.get("amount_minor")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            return _result(request, PolicyDecision.DENY, "REFUND-002", "invalid_amount", "high")
        if amount > context.hard_refund_ceiling_minor:
            return _result(
                request,
                PolicyDecision.DENY,
                "REFUND-005",
                "refund_exceeds_ai_hard_ceiling",
                "high",
            )
        if amount > context.single_approval_limit_minor:
            return _result(
                request,
                PolicyDecision.REQUIRE_APPROVAL,
                "REFUND-003",
                "two_approvers_required",
                "high",
                "supervisor",
                2,
            )
        if amount > context.autonomous_refund_limit_minor:
            return _result(
                request,
                PolicyDecision.REQUIRE_APPROVAL,
                "REFUND-003",
                "supervisor_approval_required",
                "high" if context.risk_level == "high" else "medium",
                "supervisor",
                1,
            )
        return _result(
            request, PolicyDecision.ALLOW, "REFUND-004", "within_autonomous_limit", "medium"
        )
    if request.action == "request_account_closure":
        return _result(
            request,
            PolicyDecision.REQUIRE_APPROVAL,
            "ACCOUNT-001",
            "account_closure_requires_approval",
            "high",
            "supervisor",
            1,
        )
    return _result(request, PolicyDecision.DENY, "DEFAULT-001", "unknown_action", "high")


def approval_is_valid(
    *,
    expected_digest: str,
    actual_digest: str,
    requester_user_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    reviewer_roles: frozenset[str],
    required_role: str,
    previous_reviewer_ids: frozenset[uuid.UUID] = frozenset(),
) -> bool:
    return (
        expected_digest == actual_digest
        and requester_user_id != reviewer_user_id
        and reviewer_user_id not in previous_reviewer_ids
        and (required_role in reviewer_roles or "admin" in reviewer_roles)
    )

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictModel):
    status: str
    service: str = "resolveai-api"


class PrincipalResponse(StrictModel):
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    subject: str
    roles: list[str]
    permissions: list[str]
    customer_id: uuid.UUID | None


class CustomerResponse(StrictModel):
    id: uuid.UUID
    external_ref: str
    email: str
    name: str
    locale: str
    status: str


class CustomerSupportSummary(StrictModel):
    id: uuid.UUID
    external_ref: str
    email: str
    name: str
    locale: str
    status: str
    order_count: int
    ticket_count: int
    open_ticket_count: int
    lifetime_value_minor: int
    currency: str
    latest_ticket_subject: str | None
    latest_ticket_status: str | None
    latest_activity_at: datetime | None


class CustomerSupportOverviewResponse(StrictModel):
    data_source: Literal["synthetic-support-v1"] = "synthetic-support-v1"
    contains_real_pii: bool = False
    customer_count: int
    ticket_count: int
    open_ticket_count: int
    customers: list[CustomerSupportSummary]


class OrderResponse(StrictModel):
    id: uuid.UUID
    external_ref: str
    customer_id: uuid.UUID
    status: str
    currency: str
    total_minor: int
    placed_at: datetime


class KnowledgeIngestRequest(StrictModel):
    source_uri: str = Field(min_length=1, max_length=1000)
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1)
    document_type: str = Field(min_length=1, max_length=80)
    audience: str = Field(default="internal", min_length=1, max_length=40)
    policy_category: str | None = Field(default=None, max_length=100)
    rag_version: str | None = Field(default=None, max_length=80)
    metadata: dict[str, object] = Field(default_factory=dict)


class KnowledgeIngestResponse(StrictModel):
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    version_number: int
    chunk_count: int
    created: bool


class KnowledgeSearchRequest(StrictModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=50)
    audience: str | None = Field(default=None, max_length=40)
    rag_version: str | None = Field(default=None, max_length=80)


class CitationResponse(StrictModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    title: str
    source_uri: str
    content: str
    heading_path: list[str]
    score: float


class KnowledgeSearchResponse(StrictModel):
    rag_version: str
    abstained: bool
    failure_category: str | None
    citations: list[CitationResponse]


class ResolutionRequest(StrictModel):
    message: str = Field(min_length=1, max_length=8000)
    order_id: uuid.UUID | None = None
    payment_id: uuid.UUID | None = None
    currency: str = Field(default="INR", min_length=3, max_length=3)
    reason_code: str = Field(default="customer_request", min_length=1, max_length=80)


class ResolutionResponse(StrictModel):
    run_id: uuid.UUID
    status: str
    intent: str | None
    risk_level: str | None
    answer: str
    trace_id: str
    approval_request_id: uuid.UUID | None = None


class ApprovalResponse(StrictModel):
    id: uuid.UUID
    run_id: uuid.UUID
    requester_user_id: uuid.UUID
    action_type: str
    action_digest: str
    action: dict[str, object]
    evidence: list[dict[str, object]]
    required_role: str
    approvals_required: int
    approvals_completed: int
    status: str
    expires_at: datetime


class ApprovalDecisionRequest(StrictModel):
    decision: str = Field(pattern="^(APPROVE|EDIT|REJECT)$")
    reason: str = Field(min_length=1, max_length=500)
    modified_action: dict[str, object] | None = None


class CostSummaryRow(StrictModel):
    provider: str
    model: str
    feature: str
    agent: str | None
    prompt_version: str | None
    rag_version: str | None
    endpoint: str | None
    operation_type: str
    event_count: int
    quantity: int
    input_tokens: int
    output_tokens: int
    cost_usd_micros: int | None
    unknown_cost_events: int


SignalCategory = Literal[
    "REFUND_DELAY",
    "DELIVERY_DELAY",
    "PAYMENT_FAILURE",
    "INVENTORY_SHORTAGE",
    "PRODUCT_QUALITY",
    "SUPPORT_ESCALATION",
]
SignalSeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class CustomerSignalCreate(StrictModel):
    ticket_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None
    store_id: str | None = Field(default=None, min_length=1, max_length=120)
    sku_id: str | None = Field(default=None, min_length=1, max_length=120)
    category: SignalCategory
    severity: SignalSeverity
    confidence: float = Field(ge=0, le=1)
    occurred_at: datetime
    source: str = Field(min_length=1, max_length=80)
    evidence: dict[str, object] = Field(default_factory=dict)
    model_version: str | None = Field(default=None, max_length=80)
    rule_version: str | None = Field(default=None, max_length=80)


class CustomerSignalRead(CustomerSignalCreate):
    id: uuid.UUID
    created_at: datetime


class MetricPointCreate(StrictModel):
    metric_name: str = Field(min_length=1, max_length=100)
    entity_type: str = Field(min_length=1, max_length=40)
    entity_id: str = Field(min_length=1, max_length=120)
    value: float
    unit: str = Field(min_length=1, max_length=40)
    observed_at: datetime
    dimensions: dict[str, object] = Field(default_factory=dict)
    source: str = Field(min_length=1, max_length=80)


class MetricPointRead(MetricPointCreate):
    id: uuid.UUID
    created_at: datetime


class AnomalyDetectionRequest(StrictModel):
    category: SignalCategory
    detector: Literal["robust_z", "ewma", "rate_change"] = "robust_z"
    entity_type: Literal["TENANT", "STORE", "SKU"] = "TENANT"
    entity_id: str = Field(default="ALL", min_length=1, max_length=120)
    window_end: datetime | None = None
    window_minutes: int = Field(default=60, ge=15, le=1440)
    baseline_windows: int = Field(default=12, ge=4, le=168)
    minimum_support: int = Field(default=5, ge=1, le=10000)
    threshold: float = Field(default=3.5, ge=1, le=20)


class CommerceAnomalyRead(StrictModel):
    id: uuid.UUID
    metric_name: str
    entity_type: str
    entity_id: str
    category: str
    status: str
    window_start: datetime
    window_end: datetime
    sample_count: int
    baseline_value: float
    observed_value: float
    deviation_score: float
    confidence: float
    detector_name: str
    detector_version: str
    threshold: float
    explanation: dict[str, object]
    created_at: datetime


class AnomalyDetectionResponse(StrictModel):
    state: Literal["ANOMALY_CREATED", "NO_ANOMALY", "INSUFFICIENT_EVIDENCE"]
    reason: str
    baseline_counts: list[int]
    observed_count: int
    baseline_median: float | None
    deviation_score: float | None
    anomaly: CommerceAnomalyRead | None = None


class InvestigationRequest(StrictModel):
    anomaly_id: uuid.UUID


class RootCauseHypothesisRead(StrictModel):
    id: uuid.UUID
    anomaly_id: uuid.UUID
    rank: int
    status: str
    cause_code: str
    summary: str
    confidence: float
    supporting_evidence: list[dict[str, object]]
    contradicting_evidence: list[dict[str, object]]
    affected_entities: list[dict[str, object]]
    time_alignment: dict[str, object]
    created_at: datetime


class RecommendedActionCreate(StrictModel):
    anomaly_id: uuid.UUID | None = None
    hypothesis_id: uuid.UUID | None = None
    action_type: str = Field(min_length=1, max_length=80)
    parameters: dict[str, object] = Field(default_factory=dict)
    expected_impact: dict[str, object] = Field(default_factory=dict)


class RecommendedActionRead(RecommendedActionCreate):
    id: uuid.UUID
    status: str
    policy_decision: str
    approval_request_id: uuid.UUID | None
    action_digest: str
    created_at: datetime


class CommerceActionExecutionRead(StrictModel):
    recommended_action_id: uuid.UUID
    execution_record_id: uuid.UUID
    status: str
    replayed: bool
    verification: dict[str, object]


class ActionOutcomeCreate(StrictModel):
    recommended_action_id: uuid.UUID
    target_metric: str = Field(min_length=1, max_length=100)
    before_window_start: datetime
    before_window_end: datetime
    before_value: float
    after_window_start: datetime | None = None
    after_window_end: datetime | None = None
    after_value: float | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list, max_length=50)


class ActionOutcomeRead(ActionOutcomeCreate):
    id: uuid.UUID
    effect_estimate: float | None
    status: str
    created_at: datetime


class CommerceOverview(StrictModel):
    signal_count: int
    open_anomaly_count: int
    supported_hypothesis_count: int
    pending_action_count: int
    measured_outcome_count: int
    signals_by_category: dict[str, int]


class CommerceStoreCreate(StrictModel):
    external_ref: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    region: str = Field(min_length=1, max_length=100)
    capacity_units: int = Field(default=0, ge=0)
    status: Literal["ACTIVE", "PAUSED", "CLOSED"] = "ACTIVE"


class CommerceStoreRead(CommerceStoreCreate):
    id: uuid.UUID
    created_at: datetime


class CommerceSkuCreate(StrictModel):
    external_ref: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    status: Literal["ACTIVE", "DISABLED", "RETIRED"] = "ACTIVE"


class CommerceSkuRead(CommerceSkuCreate):
    id: uuid.UUID
    created_at: datetime


class InventorySnapshotCreate(StrictModel):
    store_ref: str = Field(min_length=1, max_length=120)
    sku_ref: str = Field(min_length=1, max_length=120)
    on_hand_units: int = Field(ge=0)
    reserved_units: int = Field(ge=0)
    reorder_point_units: int = Field(ge=0)
    observed_at: datetime
    source: str = Field(min_length=1, max_length=80)


class InventorySnapshotRead(InventorySnapshotCreate):
    id: uuid.UUID
    created_at: datetime


class FulfillmentEventCreate(StrictModel):
    order_ref: str = Field(min_length=1, max_length=120)
    store_ref: str | None = Field(default=None, max_length=120)
    sku_ref: str | None = Field(default=None, max_length=120)
    event_type: Literal[
        "PLACED",
        "PICKING",
        "PACKED",
        "ASSIGNED",
        "DISPATCHED",
        "DELIVERED",
        "DELAYED",
        "FAILED",
        "RETURNED",
    ]
    occurred_at: datetime
    source: str = Field(min_length=1, max_length=80)
    metadata: dict[str, object] = Field(default_factory=dict)


class FulfillmentEventRead(FulfillmentEventCreate):
    id: uuid.UUID
    created_at: datetime


class ProductBatchCreate(StrictModel):
    batch_ref: str = Field(min_length=1, max_length=120)
    sku_ref: str = Field(min_length=1, max_length=120)
    produced_at: datetime
    expires_at: datetime | None = None
    units_produced: int = Field(ge=0)
    status: Literal["ACTIVE", "QUARANTINED", "RECALLED", "EXPIRED"] = "ACTIVE"


class ProductBatchRead(ProductBatchCreate):
    id: uuid.UUID
    created_at: datetime


class QualityReportCreate(StrictModel):
    batch_ref: str | None = Field(default=None, max_length=120)
    sku_ref: str = Field(min_length=1, max_length=120)
    defect_type: str = Field(min_length=1, max_length=100)
    severity: SignalSeverity
    affected_units: int = Field(ge=0)
    reported_at: datetime
    source: str = Field(min_length=1, max_length=80)
    evidence: dict[str, object] = Field(default_factory=dict)


class QualityReportRead(QualityReportCreate):
    id: uuid.UUID
    created_at: datetime


class InventoryRiskRow(StrictModel):
    store_ref: str
    sku_ref: str
    available_units: int
    reorder_point_units: int
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    observed_at: datetime
    provenance: dict[str, object]


class DeliveryRiskRow(StrictModel):
    store_ref: str
    event_count: int
    delayed_count: int
    failed_count: int
    risk_rate: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    window_start: datetime
    window_end: datetime
    provenance: dict[str, object]


class ProductQualityRow(StrictModel):
    sku_ref: str
    report_count: int
    affected_units: int
    critical_reports: int
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    window_start: datetime
    window_end: datetime
    provenance: dict[str, object]


class DetectorEvaluationCase(StrictModel):
    case_key: str = Field(min_length=1, max_length=120)
    baseline_counts: list[int] = Field(min_length=4, max_length=168)
    observed_count: int = Field(ge=0)
    expected_anomaly: bool


class DetectorEvaluationRequest(StrictModel):
    detector: Literal["robust_z", "ewma", "rate_change"]
    threshold: float = Field(ge=1, le=20)
    minimum_support: int = Field(default=5, ge=1, le=10000)
    cases: list[DetectorEvaluationCase] = Field(min_length=1, max_length=1000)


class DetectorEvaluationResponse(StrictModel):
    id: uuid.UUID
    detector: str
    detector_version: str
    dataset_sha256: str
    sample_count: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    false_positive_rate: float | None
    insufficient_evidence_count: int
    created_at: datetime


class DetectorScheduleCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    detector: Literal["robust_z", "ewma", "rate_change"]
    category: SignalCategory
    entity_type: Literal["TENANT", "STORE", "SKU"] = "TENANT"
    entity_id: str = Field(default="ALL", min_length=1, max_length=120)
    interval_minutes: int = Field(default=60, ge=15, le=10080)
    window_minutes: int = Field(default=60, ge=15, le=1440)
    baseline_windows: int = Field(default=12, ge=4, le=168)
    minimum_support: int = Field(default=5, ge=1, le=10000)
    threshold: float = Field(default=3.5, ge=1, le=20)
    enabled: bool = True


class DetectorScheduleRead(DetectorScheduleCreate):
    id: uuid.UUID
    last_run_at: datetime | None
    next_run_at: datetime
    created_at: datetime


class DetectorScheduleRunResult(StrictModel):
    schedule_id: uuid.UUID
    schedule_name: str
    state: str
    anomaly_id: uuid.UUID | None
    next_run_at: datetime

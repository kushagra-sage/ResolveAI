const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type Approval = {
  id: string;
  run_id: string;
  requester_user_id: string;
  action_type: string;
  action_digest: string;
  action: Record<string, unknown>;
  evidence: Array<Record<string, unknown>>;
  required_role: string;
  status: string;
  expires_at: string;
};

export type ResolutionResult = {
  run_id: string;
  status: string;
  intent: string | null;
  risk_level: string | null;
  answer: string;
  trace_id: string;
  approval_request_id: string | null;
};

export type CustomerSupportSummary = {
  id: string;
  external_ref: string;
  email: string;
  name: string;
  locale: string;
  status: string;
  order_count: number;
  ticket_count: number;
  open_ticket_count: number;
  lifetime_value_minor: number;
  currency: string;
  latest_ticket_subject: string | null;
  latest_ticket_status: string | null;
  latest_activity_at: string | null;
};

export type CustomerSupportOverview = {
  data_source: "synthetic-support-v1";
  contains_real_pii: false;
  customer_count: number;
  ticket_count: number;
  open_ticket_count: number;
  customers: CustomerSupportSummary[];
};

export type CommerceOverview = {
  signal_count: number;
  open_anomaly_count: number;
  supported_hypothesis_count: number;
  pending_action_count: number;
  measured_outcome_count: number;
  signals_by_category: Record<string, number>;
};

export type CustomerSignal = {
  id: string;
  store_id: string | null;
  sku_id: string | null;
  category: string;
  severity: string;
  confidence: number;
  occurred_at: string;
  source: string;
  evidence: Record<string, unknown>;
};

export type CommerceAnomaly = {
  id: string;
  category: string;
  entity_type: string;
  entity_id: string;
  status: string;
  observed_value: number;
  baseline_value: number;
  deviation_score: number;
  confidence: number;
  detector_name: string;
  detector_version: string;
  window_start: string;
  window_end: string;
  explanation: Record<string, unknown>;
};

export type RootCause = {
  id: string;
  anomaly_id: string;
  rank: number;
  status: string;
  cause_code: string;
  summary: string;
  confidence: number;
  supporting_evidence: Array<Record<string, unknown>>;
  affected_entities: Array<Record<string, unknown>>;
};

export type RecommendedAction = {
  id: string;
  anomaly_id: string | null;
  hypothesis_id: string | null;
  action_type: string;
  parameters: Record<string, unknown>;
  expected_impact: Record<string, unknown>;
  status: string;
  policy_decision: string;
  approval_request_id: string | null;
  action_digest: string;
  created_at: string;
};

export type ActionOutcome = {
  id: string;
  recommended_action_id: string;
  target_metric: string;
  before_value: number;
  after_value: number | null;
  effect_estimate: number | null;
  confidence: number | null;
  status: string;
  limitations: string[];
  created_at: string;
};

export type InventoryRisk = {
  store_ref: string;
  sku_ref: string;
  available_units: number;
  reorder_point_units: number;
  risk_level: string;
  observed_at: string;
};

export type DeliveryRisk = {
  store_ref: string;
  event_count: number;
  delayed_count: number;
  failed_count: number;
  risk_rate: number;
  risk_level: string;
};

export type ProductQuality = {
  sku_ref: string;
  report_count: number;
  affected_units: number;
  critical_reports: number;
  risk_level: string;
};

export type ConsoleOverview = {
  agent_runs: number;
  completed_runs: number;
  latest_step_count: number;
  latest_run_status: string;
  audit_events: number;
  evaluation_cases: number;
  latest_evaluation_status: string;
  pending_approvals: number;
  generated_at: string;
};

export type TraceItem = {
  id: string;
  trace_id: string;
  status: string;
  intent: string | null;
  risk_level: string | null;
  current_node: string;
  step_count: number;
  created_at: string;
  steps: Array<{ sequence: number; node: string; status: string; error_category: string | null }>;
};

export type EvaluationItem = {
  id: string;
  dataset: string;
  dataset_version: string;
  status: string;
  sample_count: number;
  rag_version: string;
  prompt_version: string;
  model_version: string;
  mean_score: number | null;
  result_count: number;
  passed_results: number;
  created_at: string;
  results: Array<{ evaluator: string; status: string; score: number | null; details: Record<string, unknown> }>;
};

export type KnowledgeDocumentItem = {
  id: string;
  source_uri: string;
  title: string;
  document_type: string;
  policy_category: string | null;
  audience: string;
  status: string;
  current_version_id: string | null;
  chunk_count: number;
  updated_at: string;
  versions: Array<{ id: string; version_number: number; checksum: string; ingestion_status: string; mime_type: string; metadata: Record<string, unknown>; created_at: string }>;
};

export type CustomerWorkspace = {
  customer: { id: string; external_ref: string; name: string; email: string; locale: string; status: string };
  orders: Array<Record<string, string | number | null>>;
  payments: Array<Record<string, string | number | null>>;
  shipments: Array<Record<string, string | number | null>>;
  tickets: Array<Record<string, string | number | null>>;
  messages: Array<Record<string, string | number | null>>;
  refunds: Array<Record<string, string | number | null>>;
  resolution_outcomes: Array<Record<string, string | number | null>>;
};

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({ detail: response.statusText }))) as { detail?: string };
    throw new Error(body.detail ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

export function listApprovals(token: string): Promise<Approval[]> {
  return request<Approval[]>("/v1/approvals", token);
}

export function decideApproval(
  token: string,
  approvalId: string,
  decision: "APPROVE" | "EDIT" | "REJECT",
  reason: string,
  modifiedAction?: Record<string, unknown>,
): Promise<Approval> {
  return request<Approval>(`/v1/approvals/${approvalId}/decision`, token, {
    method: "POST",
    body: JSON.stringify({ decision, reason, modified_action: modifiedAction }),
  });
}

export function createResolution(
  token: string,
  payload: { message: string; order_id?: string; payment_id?: string; currency?: string; reason_code?: string },
): Promise<ResolutionResult> {
  return request<ResolutionResult>("/v1/resolutions", token, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export const getCustomerSupportOverview = (token: string) =>
  request<CustomerSupportOverview>("/v1/customers", token);
export const getCustomerWorkspace = (token: string, customerId: string) =>
  request<CustomerWorkspace>(`/v1/customers/${customerId}/workspace`, token);

export const getConsoleOverview = (token: string) =>
  request<ConsoleOverview>("/v1/console/overview", token);
export const getConsoleTraces = (token: string, status = "") =>
  request<{ items: TraceItem[]; total: number; limit: number; offset: number }>(
    `/v1/console/traces${status ? `?run_status=${encodeURIComponent(status)}` : ""}`,
    token,
  );
export const getConsoleEvaluations = (token: string) =>
  request<{ items: EvaluationItem[]; total: number }>("/v1/console/evaluations", token);
export const getConsoleRag = (token: string) =>
  request<{ items: Array<Record<string, string | number>> }>("/v1/console/rag", token);
export const getConsoleCost = (token: string) =>
  request<Record<string, unknown> & { items: Array<Record<string, unknown>> }>("/v1/console/cost", token);
export const getConsoleModels = (token: string) =>
  request<Record<string, Array<Record<string, unknown>>>>("/v1/console/models", token);
export const getConsolePolicies = (token: string) =>
  request<Record<string, unknown> & { items: Array<Record<string, unknown>> }>("/v1/console/policies", token);
export const getConsoleAudit = (token: string, eventType = "", outcome = "", offset = 0) => {
  const params = new URLSearchParams({ limit: "50", offset: String(offset) });
  if (eventType) params.set("event_type", eventType);
  if (outcome) params.set("outcome", outcome);
  return request<{ items: Array<Record<string, unknown>>; total: number; limit: number; offset: number }>(`/v1/console/audit?${params}`, token);
};
export const getConsoleReports = (token: string) =>
  request<Record<string, Array<Record<string, unknown>>>>("/v1/console/reports", token);
export const getConsoleHealth = (token: string) =>
  request<Record<string, unknown> & { jobs: Array<Record<string, unknown>>; outbox: Array<Record<string, unknown>> }>("/v1/console/health", token);
export const replayEvaluationJob = (token: string, jobId: string) =>
  request<{ id: string; status: string; replayed: boolean }>(`/v1/console/health/evaluation-jobs/${jobId}/replay`, token, { method: "POST" });
export const replayOutboxEvent = (token: string, eventId: string) =>
  request<{ id: string; status: string; replayed: boolean }>(`/v1/console/health/outbox/${eventId}/replay`, token, { method: "POST" });
export const reconcileDurableWork = (token: string) =>
  request<{ requeued_jobs: number; checked_at: string }>("/v1/console/health/reconcile", token, { method: "POST" });
export const getConsoleSettings = (token: string) =>
  request<{ tenant: Record<string, unknown>; runtime: Record<string, unknown> }>("/v1/console/settings", token);
export const listKnowledgeDocuments = (token: string) =>
  request<{ items: KnowledgeDocumentItem[]; total: number }>("/v1/knowledge/documents", token);
export const ingestKnowledgeDocument = (token: string, payload: Record<string, unknown>) =>
  request<Record<string, unknown>>("/v1/knowledge/documents", token, { method: "POST", body: JSON.stringify(payload) });
export const updateKnowledgeStatus = (token: string, documentId: string, status: "active" | "archived") =>
  request<{ id: string; status: string }>(`/v1/knowledge/documents/${documentId}/status`, token, { method: "PATCH", body: JSON.stringify({ status }) });
export const searchKnowledge = (token: string, query: string) =>
  request<{ rag_version: string; abstained: boolean; failure_category: string | null; citations: Array<Record<string, unknown>> }>("/v1/knowledge/search", token, { method: "POST", body: JSON.stringify({ query, top_k: 5, audience: "internal" }) });

export const getCommerceOverview = (token: string) =>
  request<CommerceOverview>("/v1/commerce/overview", token);
export const listCustomerSignals = (token: string) =>
  request<CustomerSignal[]>("/v1/customer-signals", token);
export const listCommerceAnomalies = (token: string) =>
  request<CommerceAnomaly[]>("/v1/commerce/anomalies", token);
export const listRootCauses = (token: string) =>
  request<RootCause[]>("/v1/commerce/root-causes", token);
export const listRecommendedActions = (token: string) =>
  request<RecommendedAction[]>("/v1/commerce/recommended-actions", token);
export const listActionOutcomes = (token: string) =>
  request<ActionOutcome[]>("/v1/commerce/action-outcomes", token);
export const listInventoryRisk = (token: string) =>
  request<InventoryRisk[]>("/v1/commerce/inventory-risk", token);
export const listDeliveryRisk = (token: string) =>
  request<DeliveryRisk[]>("/v1/commerce/delivery-risk", token);
export const listProductQuality = (token: string) =>
  request<ProductQuality[]>("/v1/commerce/product-quality", token);
export const executeRecommendedAction = (token: string, actionId: string) =>
  request<{ status: string; replayed: boolean; verification: Record<string, unknown> }>(
    `/v1/commerce/recommended-actions/${actionId}/execute`,
    token,
    { method: "POST" },
  );

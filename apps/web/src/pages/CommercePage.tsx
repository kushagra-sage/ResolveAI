import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Radar,
  ShieldCheck,
  Send,
  Sparkles,
} from "../components/Icons";
import { useAuth } from "../auth/AuthProvider";
import { PageHeader, StatusPill } from "../components/PageHeader";
import {
  executeRecommendedAction,
  getCommerceOverview,
  listActionOutcomes,
  listCommerceAnomalies,
  listCustomerSignals,
  listDeliveryRisk,
  listInventoryRisk,
  listProductQuality,
  listRecommendedActions,
  listRootCauses,
  type RecommendedAction,
} from "../lib/api";

export type CommercePageKind = "signals" | "anomalies" | "root-cause" | "actions" | "outcomes";

const pageCopy: Record<CommercePageKind, [string, string, string]> = {
  signals: ["COMMERCEOPS", "Signal explorer", "Tenant-scoped operational signals with controlled categories, provenance, confidence, and minimized evidence."],
  anomalies: ["COMMERCEOPS", "Risk & anomaly queue", "Explainable detector output alongside current inventory, delivery, and product-quality risk."],
  "root-cause": ["COMMERCEOPS", "Root-cause studio", "Ranked hypotheses supported by signal concentration and time-aligned operational facts."],
  actions: ["COMMERCEOPS", "Recommended actions", "Policy-evaluated proposals with digest-bound approval and idempotent execution."],
  outcomes: ["COMMERCEOPS", "Outcome learning", "Before-and-after measurements with confidence and explicit causal limitations."],
};

export function CommercePage({ kind }: { kind: CommercePageKind }) {
  const { accessToken: activeToken } = useAuth();
  const enabled = Boolean(activeToken);
  const overview = useQuery({ queryKey: ["commerce-overview", activeToken], queryFn: () => getCommerceOverview(activeToken), enabled });
  const signals = useQuery({ queryKey: ["commerce-signals", activeToken], queryFn: () => listCustomerSignals(activeToken), enabled: enabled && kind === "signals" });
  const anomalies = useQuery({ queryKey: ["commerce-anomalies", activeToken], queryFn: () => listCommerceAnomalies(activeToken), enabled: enabled && kind === "anomalies" });
  const inventory = useQuery({ queryKey: ["inventory-risk", activeToken], queryFn: () => listInventoryRisk(activeToken), enabled: enabled && kind === "anomalies" });
  const delivery = useQuery({ queryKey: ["delivery-risk", activeToken], queryFn: () => listDeliveryRisk(activeToken), enabled: enabled && kind === "anomalies" });
  const quality = useQuery({ queryKey: ["product-quality", activeToken], queryFn: () => listProductQuality(activeToken), enabled: enabled && kind === "anomalies" });
  const rootCauses = useQuery({ queryKey: ["root-causes", activeToken], queryFn: () => listRootCauses(activeToken), enabled: enabled && kind === "root-cause" });
  const actions = useQuery({ queryKey: ["recommended-actions", activeToken], queryFn: () => listRecommendedActions(activeToken), enabled: enabled && kind === "actions" });
  const outcomes = useQuery({ queryKey: ["action-outcomes", activeToken], queryFn: () => listActionOutcomes(activeToken), enabled: enabled && kind === "outcomes" });
  const [eyebrow, title, description] = pageCopy[kind];
  const errors = [overview.error, signals.error, anomalies.error, inventory.error, delivery.error, quality.error, rootCauses.error, actions.error, outcomes.error].filter(Boolean);
  const loading = [overview, signals, anomalies, inventory, delivery, quality, rootCauses, actions, outcomes].some((query) => query.isFetching);

  return <>
    <PageHeader eyebrow={eyebrow} title={title} description={description} actions={<StatusPill tone={overview.data ? "good" : "warning"}>{loading ? "Loading live data" : overview.data ? "Live PostgreSQL" : "No measured data"}</StatusPill>} />
    {errors.length > 0 && <div className="inline-error">{errors[0] instanceof Error ? errors[0].message : "Unable to load CommerceOps data."}</div>}
    {overview.data && <div className="metric-grid commerce-metrics"><Metric icon={<Radar />} label="Signals" value={overview.data.signal_count} /><Metric icon={<AlertTriangle />} label="Open anomalies" value={overview.data.open_anomaly_count} /><Metric icon={<Sparkles />} label="Supported causes" value={overview.data.supported_hypothesis_count} /><Metric icon={<CheckCircle2 />} label="Measured outcomes" value={overview.data.measured_outcome_count} /></div>}
    {kind === "signals" && <SignalsTable rows={signals.data ?? []} loaded={signals.isSuccess} />}
    {kind === "anomalies" && <AnomalyWorkspace anomalies={anomalies.data ?? []} inventory={inventory.data ?? []} delivery={delivery.data ?? []} quality={quality.data ?? []} loaded={anomalies.isSuccess} />}
    {kind === "root-cause" && <RootCauseTable rows={rootCauses.data ?? []} loaded={rootCauses.isSuccess} />}
    {kind === "actions" && <ActionsTable rows={actions.data ?? []} loaded={actions.isSuccess} token={activeToken} />}
    {kind === "outcomes" && <OutcomesTable rows={outcomes.data ?? []} loaded={outcomes.isSuccess} />}
  </>;
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return <article className="metric-card"><div>{icon}<span>{label}</span></div><strong>{value}</strong><small>Measured from the live tenant database</small></article>;
}

function Empty({ loaded, label }: { loaded: boolean; label: string }) {
  return <section className="panel empty-state"><Database size={28} /><h3>{loaded ? `No ${label} recorded` : "Loading authenticated data"}</h3><p>{loaded ? "The API returned an empty measured state; no value has been invented." : "ResolveAI is querying the tenant-scoped backend with your active session."}</p></section>;
}

function tone(status: string): "good" | "warning" | "danger" | "neutral" {
  if (["LOW", "SUPPORTED", "MEASURED", "EXECUTED", "RESOLVED"].includes(status)) return "good";
  if (["HIGH", "CRITICAL", "REJECTED", "DENY"].includes(status)) return "danger";
  if (["MEDIUM", "OPEN", "PROPOSED", "APPROVAL_REQUIRED"].includes(status)) return "warning";
  return "neutral";
}

function SignalsTable({ rows, loaded }: { rows: Awaited<ReturnType<typeof listCustomerSignals>>; loaded: boolean }) {
  if (!rows.length) return <Empty loaded={loaded} label="signals" />;
  return <section className="panel table-panel"><table><thead><tr><th>Occurred</th><th>Category</th><th>Entity</th><th>Severity</th><th>Confidence</th><th>Source</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{new Date(row.occurred_at).toLocaleString()}</td><td>{row.category.replaceAll("_", " ")}</td><td>{row.store_id ?? "Tenant"} / {row.sku_id ?? "All SKUs"}</td><td><StatusPill tone={tone(row.severity)}>{row.severity}</StatusPill></td><td>{Math.round(row.confidence * 100)}%</td><td>{row.source}</td></tr>)}</tbody></table></section>;
}

function AnomalyWorkspace({ anomalies, inventory, delivery, quality, loaded }: { anomalies: Awaited<ReturnType<typeof listCommerceAnomalies>>; inventory: Awaited<ReturnType<typeof listInventoryRisk>>; delivery: Awaited<ReturnType<typeof listDeliveryRisk>>; quality: Awaited<ReturnType<typeof listProductQuality>>; loaded: boolean }) {
  return <div className="commerce-stack">
    {anomalies.length ? <section className="panel table-panel"><div className="section-heading"><div><p className="eyebrow">DETECTOR OUTPUT</p><h3>Explainable anomalies</h3></div></div><table><thead><tr><th>Category</th><th>Entity</th><th>Observed / baseline</th><th>Deviation</th><th>Detector</th><th>Status</th></tr></thead><tbody>{anomalies.map((row) => <tr key={row.id}><td>{row.category.replaceAll("_", " ")}</td><td>{row.entity_type}: {row.entity_id}</td><td>{row.observed_value} / {row.baseline_value}</td><td>{row.deviation_score.toFixed(2)}</td><td>{row.detector_name} v{row.detector_version}</td><td><StatusPill tone={tone(row.status)}>{row.status}</StatusPill></td></tr>)}</tbody></table></section> : <Empty loaded={loaded} label="anomalies" />}
    <div className="risk-grid"><RiskCard title="Inventory risk" rows={inventory.map((row) => [row.store_ref, row.sku_ref, `${row.available_units} available`, row.risk_level])} /><RiskCard title="Delivery risk" rows={delivery.map((row) => [row.store_ref, `${row.delayed_count} delayed`, `${Math.round(row.risk_rate * 100)}% risk rate`, row.risk_level])} /><RiskCard title="Product quality" rows={quality.map((row) => [row.sku_ref, `${row.report_count} reports`, `${row.affected_units} units`, row.risk_level])} /></div>
  </div>;
}

function RiskCard({ title, rows }: { title: string; rows: string[][] }) {
  return <section className="panel risk-card"><div className="section-heading"><div><p className="eyebrow">LIVE RISK READ MODEL</p><h3>{title}</h3></div></div>{rows.length ? rows.map((row, index) => <div className="risk-row" key={`${row[0]}-${index}`}><div><strong>{row[0]}</strong><small>{row[1]} · {row[2]}</small></div><StatusPill tone={tone(row[3])}>{row[3]}</StatusPill></div>) : <p className="muted-copy">NOT MEASURED — no operational facts in this window.</p>}</section>;
}

function RootCauseTable({ rows, loaded }: { rows: Awaited<ReturnType<typeof listRootCauses>>; loaded: boolean }) {
  if (!rows.length) return <Empty loaded={loaded} label="root-cause hypotheses" />;
  return <div className="cause-grid">{rows.map((row) => <section className="panel cause-card" key={row.id}><div className="section-heading"><div><p className="eyebrow">RANK {row.rank}</p><h3>{row.cause_code.replaceAll("_", " ")}</h3></div><StatusPill tone={tone(row.status)}>{row.status}</StatusPill></div><p>{row.summary}</p><div className="evidence-count">{row.supporting_evidence.length} supporting evidence record{row.supporting_evidence.length === 1 ? "" : "s"} · {Math.round(row.confidence * 100)}% confidence</div></section>)}</div>;
}

function ActionsTable({ rows, loaded, token }: { rows: RecommendedAction[]; loaded: boolean; token: string }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const mutation = useMutation({ mutationFn: (id: string) => executeRecommendedAction(token, id), onSuccess: async (result) => { setMessage(`${result.status}${result.replayed ? " · idempotent replay" : " · execution recorded"}`); await queryClient.invalidateQueries({ queryKey: ["recommended-actions"] }); }, onError: (error) => setMessage(error instanceof Error ? error.message : "Execution failed") });
  if (!rows.length) return <Empty loaded={loaded} label="recommended actions" />;
  return <div className="approval-list">{message && <div className="evidence-notice"><ShieldCheck size={16} />{message}</div>}{rows.map((row) => <section className="panel action-card" key={row.id}><div className="section-heading"><div><p className="eyebrow">{row.policy_decision} · {row.action_digest.slice(0, 12)}…</p><h3>{row.action_type.replaceAll("_", " ")}</h3></div><StatusPill tone={tone(row.status)}>{row.status}</StatusPill></div><pre>{JSON.stringify(row.parameters, null, 2)}</pre><div className="action-footer"><small>Expected impact: {JSON.stringify(row.expected_impact)}</small>{row.status === "PROPOSED" && <button className="button primary small" disabled={mutation.isPending} onClick={() => mutation.mutate(row.id)}><Send size={14} /> Execute governed action</button>}{row.status === "APPROVAL_REQUIRED" && <Link className="button secondary small" to="/approvals">Review approval</Link>}</div></section>)}</div>;
}

function OutcomesTable({ rows, loaded }: { rows: Awaited<ReturnType<typeof listActionOutcomes>>; loaded: boolean }) {
  if (!rows.length) return <Empty loaded={loaded} label="action outcomes" />;
  return <section className="panel table-panel"><table><thead><tr><th>Metric</th><th>Before</th><th>After</th><th>Effect</th><th>Confidence</th><th>Status</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td>{row.target_metric}</td><td>{row.before_value}</td><td>{row.after_value ?? "NOT MEASURED"}</td><td>{row.effect_estimate ?? "—"}</td><td>{row.confidence === null ? "—" : `${Math.round(row.confidence * 100)}%`}</td><td><StatusPill tone={tone(row.status)}>{row.status}</StatusPill></td></tr>)}</tbody></table></section>;
}

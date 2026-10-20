import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthProvider";
import { CheckCircle2, CircleDollarSign, Database, FlaskConical, ShieldCheck } from "../components/Icons";
import { PageHeader, StatusPill } from "../components/PageHeader";
import { getConsoleCost, getConsoleEvaluations, getConsoleRag, getConsoleTraces } from "../lib/api";

export type EvidencePageKind = "traces" | "evaluation" | "rag" | "cost";

export function EvidencePage({ kind }: { kind: EvidencePageKind }) {
  const token = useAuth().accessToken;
  const [traceStatus, setTraceStatus] = useState("");
  const traces = useQuery({ queryKey: ["console-traces", token, traceStatus], queryFn: () => getConsoleTraces(token, traceStatus), enabled: Boolean(token) && kind === "traces" });
  const evaluations = useQuery({ queryKey: ["console-evaluations", token], queryFn: () => getConsoleEvaluations(token), enabled: Boolean(token) && kind === "evaluation" });
  const rag = useQuery({ queryKey: ["console-rag", token], queryFn: () => getConsoleRag(token), enabled: Boolean(token) && kind === "rag" });
  const cost = useQuery({ queryKey: ["console-cost", token], queryFn: () => getConsoleCost(token), enabled: Boolean(token) && kind === "cost" });

  if (kind === "traces") {
    const selected = traces.data?.items[0];
    return <><PageHeader eyebrow="OBSERVABILITY" title="Trace explorer" description="Live tenant-scoped run and stage evidence, with status filters and drill-down." actions={<StatusPill tone="good">{traces.data?.total ?? 0} runs</StatusPill>} /><LiveNotice loading={traces.isFetching} error={traces.error} /><section className="panel filter-bar"><label>Status<select value={traceStatus} onChange={(event) => setTraceStatus(event.target.value)}><option value="">All</option><option value="completed">Completed</option><option value="waiting_approval">Waiting approval</option><option value="failed">Failed</option></select></label></section>{selected ? <section className="panel trace-report"><div className="trace-id"><span>Latest matching trace</span><code>{selected.trace_id}</code></div><div className="trace-timeline">{selected.steps.map((step, index) => <div key={`${selected.id}-${step.sequence}`}><span>{index + 1}</span><div><strong>{step.node}</strong><small>{step.status}{step.error_category ? ` · ${step.error_category}` : ""}</small></div>{index < selected.steps.length - 1 && <i />}</div>)}</div><div className={`result-banner ${selected.status === "completed" ? "success" : "warning"}`}><CheckCircle2 size={18} /><div><strong>{selected.status}</strong><span>{selected.step_count} persisted stages · {selected.intent ?? "unclassified"} · {selected.risk_level ?? "unrated"}</span></div></div></section> : <Empty />}</>;
  }
  if (kind === "evaluation") {
    const latest = evaluations.data?.items[0];
    const passRate = latest?.result_count ? latest.passed_results / latest.result_count : null;
    return <><PageHeader eyebrow="EVALUATION" title="Evaluation lab" description="Live versioned evaluation runs and per-evaluator measurements." actions={<StatusPill tone={latest?.status === "completed" ? "good" : "warning"}>{latest?.status ?? "No runs"}</StatusPill>} /><LiveNotice loading={evaluations.isFetching} error={evaluations.error} /><div className="metric-grid three"><Metric icon={<FlaskConical />} label="Mean score" value={percent(latest?.mean_score)} note="across stored scored results" /><Metric icon={<ShieldCheck />} label="Pass rate" value={percent(passRate)} note={`${latest?.passed_results ?? 0} / ${latest?.result_count ?? 0} evaluator results`} /><Metric icon={<Database />} label="Sample count" value={String(latest?.sample_count ?? 0)} note={latest ? `${latest.dataset} ${latest.dataset_version}` : "no completed dataset"} /></div><Rows title="Evaluation runs" rows={(evaluations.data?.items ?? []).map((row) => ({ dataset: `${row.dataset} ${row.dataset_version}`, status: row.status, samples: row.sample_count, mean_score: row.mean_score, rag: row.rag_version, model: row.model_version, created_at: row.created_at }))} /></>;
  }
  if (kind === "rag") {
    return <><PageHeader eyebrow="RETRIEVAL EXPERIMENTS" title="RAG evolution" description="Live retrieval configurations, indexed chunks, and observed retrieval volume." actions={<StatusPill tone="good">{rag.data?.items.length ?? 0} versions</StatusPill>} /><LiveNotice loading={rag.isFetching} error={rag.error} /><Rows title="Version registry" rows={rag.data?.items ?? []} /></>;
  }
  const data = cost.data;
  const totalCalls = Number(data?.tool_call_count ?? 0);
  const failedCalls = Number(data?.failed_tool_calls ?? 0);
  return <><PageHeader eyebrow="FINOPS & RELIABILITY" title="Cost & reliability" description="Live cost, token, guardrail, execution, and failure counters; unknown prices remain unknown." actions={<StatusPill tone={failedCalls ? "danger" : "good"}>{failedCalls} failed calls</StatusPill>} /><LiveNotice loading={cost.isFetching} error={cost.error} /><div className="metric-grid three"><Metric icon={<CircleDollarSign />} label="Known cost" value={usd(Number(data?.known_cost_usd_micros ?? 0))} note={`${data?.unknown_cost_events ?? 0} unknown-cost events`} /><Metric icon={<Database />} label="Input tokens" value={Number(data?.input_tokens ?? 0).toLocaleString()} note={`${data?.output_tokens ?? 0} output tokens`} /><Metric icon={<CheckCircle2 />} label="Tool reliability" value={percent(totalCalls ? 1 - failedCalls / totalCalls : null)} note={`${totalCalls} persisted tool calls`} /></div><Rows title="Cost events" rows={data?.items ?? []} /></>;
}

function LiveNotice({ loading, error }: { loading: boolean; error: unknown }) { return <div className={`evidence-notice ${error ? "inline-error" : ""}`}><Database size={16} /><span><strong>{error ? "Live request failed" : loading ? "Refreshing" : "PostgreSQL evidence"}</strong>{error ? ` · ${error instanceof Error ? error.message : String(error)}` : " · authenticated, tenant-scoped, and generated from stored measurements."}</span></div>; }
function Metric({ icon, label, value, note }: { icon: ReactNode; label: string; value: string; note: string }) { return <article className="metric-card"><div>{icon}<span>{label}</span></div><strong>{value}</strong><small>{note}</small></article>; }
function Empty() { return <section className="panel empty-state"><Database size={28} /><h3>No matching evidence</h3><p>The backend returned an empty state; no value has been invented.</p></section>; }
function Rows({ title, rows }: { title: string; rows: Array<Record<string, unknown>> }) { const columns = rows.length ? Object.keys(rows[0]).slice(0, 8) : []; return <section className="panel table-panel"><div className="section-heading"><div><p className="eyebrow">LIVE MEASUREMENTS</p><h3>{title}</h3></div><StatusPill>{rows.length} rows</StatusPill></div>{rows.length ? <table><thead><tr>{columns.map((column) => <th key={column}>{column.replaceAll("_", " ")}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id ?? index)}>{columns.map((column) => <td key={column}>{render(row[column])}</td>)}</tr>)}</tbody></table> : <div className="empty-inline">No stored records.</div>}</section>; }
function render(value: unknown): string { if (value === null || value === undefined) return "—"; if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(3); if (typeof value === "object") return JSON.stringify(value); return String(value); }
function percent(value: number | null | undefined): string { return value === null || value === undefined ? "N/A" : `${(value * 100).toFixed(1)}%`; }
function usd(micros: number): string { return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 6 }).format(micros / 1_000_000); }

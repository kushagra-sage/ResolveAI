import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthProvider";
import { Database, RefreshCw, Search, ShieldCheck } from "../components/Icons";
import { PageHeader, StatusPill } from "../components/PageHeader";
import {
  getConsoleAudit,
  getConsoleHealth,
  getConsoleModels,
  getConsolePolicies,
  getConsoleReports,
  getConsoleSettings,
  ingestKnowledgeDocument,
  listKnowledgeDocuments,
  reconcileDurableWork,
  replayEvaluationJob,
  replayOutboxEvent,
  searchKnowledge,
  updateKnowledgeStatus,
  type KnowledgeDocumentItem,
} from "../lib/api";

export type AdminPageKind = "models" | "policies" | "audit" | "reports" | "health" | "settings" | "knowledge";

export function AdminPage({ kind }: { kind: AdminPageKind }) {
  if (kind === "audit") return <AuditPage />;
  if (kind === "knowledge") return <KnowledgePage />;
  if (kind === "health") return <HealthPage />;
  if (kind === "settings") return <SettingsPage />;
  if (kind === "models") return <RegistryPage />;
  if (kind === "policies") return <PolicyPage />;
  return <ReportsPage />;
}

const pageCopy = {
  models: ["LLMOPS", "Model registry", "Live model, prompt, and deployment versions with promotion evidence."],
  policies: ["GOVERNANCE", "Policy workspace", "Live deterministic policy thresholds and recorded decisions."],
  reports: ["RESEARCH", "Research reports", "Stored evaluation runs and immutable research artifacts."],
} as const;

function RegistryPage() {
  const token = useAuth().accessToken;
  const query = useQuery({ queryKey: ["console-models", token], queryFn: () => getConsoleModels(token), enabled: Boolean(token) });
  return <ResourcePage copy={pageCopy.models} query={query} sections={["models", "prompts", "deployments"]} />;
}

function PolicyPage() {
  const token = useAuth().accessToken;
  const query = useQuery({ queryKey: ["console-policies", token], queryFn: () => getConsolePolicies(token), enabled: Boolean(token) });
  return <ResourcePage copy={pageCopy.policies} query={query} sections={["items"]} />;
}

function ReportsPage() {
  const token = useAuth().accessToken;
  const query = useQuery({ queryKey: ["console-reports", token], queryFn: () => getConsoleReports(token), enabled: Boolean(token) });
  return <ResourcePage copy={pageCopy.reports} query={query} sections={["evaluation_runs", "artifacts"]} />;
}

type ResourceQuery = { data?: Record<string, unknown>; isFetching: boolean; error: unknown; refetch: () => unknown };

function ResourcePage({ copy, query, sections }: { copy: readonly [string, string, string]; query: ResourceQuery; sections: string[] }) {
  const data = query.data;
  const facts = data ? Object.entries(data).filter(([key, value]) => !sections.includes(key) && !Array.isArray(value)) : [];
  return <>
    <PageHeader eyebrow={copy[0]} title={copy[1]} description={copy[2]} actions={<button className="button secondary small" onClick={() => void query.refetch()}><RefreshCw size={14} /> Refresh</button>} />
    <LiveNotice fetching={query.isFetching} error={query.error} />
    {facts.length > 0 && <div className="metric-grid three">{facts.slice(0, 6).map(([key, value]) => <article className="metric-card" key={key}><div><Database /><span>{label(key)}</span></div><strong>{formatValue(value)}</strong><small>live tenant configuration</small></article>)}</div>}
    {sections.map((section) => <DataTable key={section} title={label(section)} rows={Array.isArray(data?.[section]) ? data[section] as Array<Record<string, unknown>> : []} />)}
  </>;
}

function AuditPage() {
  const token = useAuth().accessToken;
  const [eventType, setEventType] = useState("");
  const [outcome, setOutcome] = useState("");
  const [offset, setOffset] = useState(0);
  const query = useQuery({ queryKey: ["console-audit", token, eventType, outcome, offset], queryFn: () => getConsoleAudit(token, eventType, outcome, offset), enabled: Boolean(token) });
  return <>
    <PageHeader eyebrow="GOVERNANCE" title="Audit log explorer" description="Filter tenant-scoped actor, resource, trace, outcome, and execution evidence." actions={<StatusPill tone="good">{query.data?.total ?? 0} events</StatusPill>} />
    <LiveNotice fetching={query.isFetching} error={query.error} />
    <section className="panel filter-bar"><label>Event type<input value={eventType} onChange={(event) => { setEventType(event.target.value); setOffset(0); }} placeholder="resolution.created" /></label><label>Outcome<input value={outcome} onChange={(event) => { setOutcome(event.target.value); setOffset(0); }} placeholder="success" /></label><button className="button secondary small" onClick={() => void query.refetch()}><Search size={14} /> Apply</button></section>
    <DataTable title="Immutable event stream" rows={query.data?.items ?? []} />
    <div className="pager"><button className="button secondary small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button><span>{offset + 1}–{Math.min(offset + 50, query.data?.total ?? 0)} of {query.data?.total ?? 0}</span><button className="button secondary small" disabled={offset + 50 >= (query.data?.total ?? 0)} onClick={() => setOffset(offset + 50)}>Next</button></div>
  </>;
}

function HealthPage() {
  const token = useAuth().accessToken;
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["console-health", token], queryFn: () => getConsoleHealth(token), enabled: Boolean(token), refetchInterval: 15_000 });
  const refresh = async () => client.invalidateQueries({ queryKey: ["console-health"] });
  const reconcile = useMutation({ mutationFn: () => reconcileDurableWork(token), onSuccess: refresh });
  const replayJob = useMutation({ mutationFn: (id: string) => replayEvaluationJob(token, id), onSuccess: refresh });
  const replayEvent = useMutation({ mutationFn: (id: string) => replayOutboxEvent(token, id), onSuccess: refresh });
  const metrics = query.data ? Object.entries(query.data).filter(([, value]) => !Array.isArray(value)) : [];
  return <>
    <PageHeader eyebrow="PLATFORM" title="System health" description="Live API, database, queue, retry, outbox, and durable-work visibility." actions={<><button className="button secondary small" disabled={reconcile.isPending} onClick={() => reconcile.mutate()}><RefreshCw size={14} /> Reconcile stalled work</button><StatusPill tone={query.error ? "danger" : "good"}>{query.error ? "Degraded" : "Live"}</StatusPill></>} />
    <LiveNotice fetching={query.isFetching} error={query.error} />
    <div className="metric-grid">{metrics.slice(0, 8).map(([key, value]) => <article className="metric-card" key={key}><div><ShieldCheck /><span>{label(key)}</span></div><strong>{formatValue(value)}</strong><small>refreshed every 15 seconds</small></article>)}</div>
    <RecoveryTable title="Evaluation jobs and retries" rows={query.data?.jobs ?? []} replayable={new Set(["failed", "dead_letter"])} onReplay={(id) => replayJob.mutate(id)} />
    <RecoveryTable title="Outbox and webhook delivery" rows={query.data?.outbox ?? []} replayable={new Set(["failed"])} onReplay={(id) => replayEvent.mutate(id)} />
  </>;
}

function SettingsPage() {
  const token = useAuth().accessToken;
  const query = useQuery({ queryKey: ["console-settings", token], queryFn: () => getConsoleSettings(token), enabled: Boolean(token) });
  return <>
    <PageHeader eyebrow="ADMINISTRATION" title="Tenant settings" description="Safe runtime and tenant configuration; secrets are never returned to the browser." actions={<StatusPill tone="good">Read-only safety view</StatusPill>} />
    <LiveNotice fetching={query.isFetching} error={query.error} />
    <div className="settings-grid"><KeyValuePanel title="Tenant" values={query.data?.tenant} /><KeyValuePanel title="Runtime" values={query.data?.runtime} /></div>
  </>;
}

function KnowledgePage() {
  const auth = useAuth();
  const token = auth.accessToken;
  const client = useQueryClient();
  const documents = useQuery({ queryKey: ["knowledge-documents", token], queryFn: () => listKnowledgeDocuments(token), enabled: Boolean(token) });
  const [form, setForm] = useState({ title: "", source_uri: "", content: "" });
  const [searchText, setSearchText] = useState("");
  const [searchResult, setSearchResult] = useState<Array<Record<string, unknown>>>([]);
  const ingest = useMutation({ mutationFn: () => ingestKnowledgeDocument(token, { ...form, document_type: "policy", audience: "internal", rag_version: "hybrid-v1", metadata: { source: "workspace" } }), onSuccess: async () => { setForm({ title: "", source_uri: "", content: "" }); await client.invalidateQueries({ queryKey: ["knowledge-documents"] }); } });
  const lifecycle = useMutation({ mutationFn: ({ id, status }: { id: string; status: "active" | "archived" }) => updateKnowledgeStatus(token, id, status), onSuccess: async () => client.invalidateQueries({ queryKey: ["knowledge-documents"] }) });
  const search = useMutation({ mutationFn: () => searchKnowledge(token, searchText), onSuccess: (result) => setSearchResult(result.citations) });
  const canWrite = auth.roles.includes("admin");
  return <>
    <PageHeader eyebrow="RAG OPERATIONS" title="Knowledge workspace" description="Ingest, version, search-test, inspect chunks, and retire grounded sources." actions={<StatusPill tone="good">{documents.data?.total ?? 0} sources</StatusPill>} />
    <LiveNotice fetching={documents.isFetching} error={documents.error} />
    <div className="two-column knowledge-tools">
      <section className="panel form-panel"><p className="eyebrow">INGEST & VERSION</p><h3>Upload text source</h3><label>Title<input value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} /></label><label>Source URI<input value={form.source_uri} onChange={(event) => setForm({ ...form, source_uri: event.target.value })} placeholder="kb://policy/refunds" /></label><label>Document content<textarea rows={8} value={form.content} onChange={(event) => setForm({ ...form, content: event.target.value })} /></label><button className="button primary" disabled={!canWrite || !form.title || !form.source_uri || !form.content || ingest.isPending} onClick={() => ingest.mutate()}>{canWrite ? "Ingest source" : "Admin role required"}</button>{ingest.error && <p className="form-error">{String(ingest.error)}</p>}</section>
      <section className="panel form-panel"><p className="eyebrow">RETRIEVAL TEST</p><h3>Inspect grounded matches</h3><label>Search query<textarea rows={3} value={searchText} onChange={(event) => setSearchText(event.target.value)} /></label><button className="button secondary" disabled={!searchText || search.isPending} onClick={() => search.mutate()}><Search size={14} /> Run search</button><div className="retrieval-results">{searchResult.map((row, index) => <article key={String(row.chunk_id ?? index)}><strong>{String(row.title ?? "Untitled")}</strong><small>score {formatValue(row.score)}</small><p>{String(row.content ?? "")}</p></article>)}</div></section>
    </div>
    <KnowledgeTable documents={documents.data?.items ?? []} canWrite={canWrite} onStatus={(id, status) => lifecycle.mutate({ id, status })} />
  </>;
}

function KnowledgeTable({ documents, canWrite, onStatus }: { documents: KnowledgeDocumentItem[]; canWrite: boolean; onStatus: (id: string, status: "active" | "archived") => void }) {
  return <section className="panel table-panel"><div className="section-heading"><div><p className="eyebrow">SOURCE LINEAGE</p><h3>Documents, versions, and chunks</h3></div></div><table><thead><tr><th>Source</th><th>Status</th><th>Versions</th><th>Chunks</th><th>Latest ingestion</th><th>Lifecycle</th></tr></thead><tbody>{documents.map((document) => <tr key={document.id}><td><strong>{document.title}</strong><small>{document.source_uri}</small></td><td><StatusPill tone={document.status === "active" ? "good" : "warning"}>{document.status}</StatusPill></td><td>{document.versions.length}</td><td>{document.chunk_count}</td><td>{document.versions[0]?.ingestion_status ?? "none"}</td><td><button className="button secondary small" disabled={!canWrite} onClick={() => onStatus(document.id, document.status === "active" ? "archived" : "active")}>{document.status === "active" ? "Retire" : "Reactivate"}</button></td></tr>)}</tbody></table></section>;
}

function LiveNotice({ fetching, error }: { fetching: boolean; error: unknown }) {
  return <div className={`evidence-notice ${error ? "inline-error" : ""}`}><Database size={16} /><span><strong>{error ? "Backend request failed" : fetching ? "Refreshing live data" : "Live tenant data"}</strong>{error ? `: ${error instanceof Error ? error.message : String(error)}` : " · values come from PostgreSQL and authenticated runtime state."}</span></div>;
}

function DataTable({ title, rows }: { title: string; rows: Array<Record<string, unknown>> }) {
  const columns = useMemo(() => rows.length ? Object.keys(rows[0]).filter((key) => !["details", "config", "results"].includes(key)).slice(0, 7) : [], [rows]);
  return <section className="panel table-panel"><div className="section-heading"><div><p className="eyebrow">LIVE RECORDS</p><h3>{title}</h3></div><StatusPill>{rows.length} rows</StatusPill></div>{rows.length ? <table><thead><tr>{columns.map((column) => <th key={column}>{label(column)}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id ?? index)}>{columns.map((column) => <td key={column}>{formatValue(row[column])}</td>)}</tr>)}</tbody></table> : <div className="empty-inline">No stored records. The interface reports the empty state without fabricating values.</div>}</section>;
}

function RecoveryTable({ title, rows, replayable, onReplay }: { title: string; rows: Array<Record<string, unknown>>; replayable: Set<string>; onReplay: (id: string) => void }) {
  const columns = rows.length ? Object.keys(rows[0]).slice(0, 7) : [];
  return <section className="panel table-panel"><div className="section-heading"><div><p className="eyebrow">DURABLE WORK</p><h3>{title}</h3></div><StatusPill>{rows.length} rows</StatusPill></div>{rows.length ? <table><thead><tr>{columns.map((column) => <th key={column}>{label(column)}</th>)}<th>Recovery</th></tr></thead><tbody>{rows.map((row, index) => { const status = String(row.status ?? ""); return <tr key={String(row.id ?? index)}>{columns.map((column) => <td key={column}>{formatValue(row[column])}</td>)}<td><button className="button secondary small" disabled={!replayable.has(status)} onClick={() => onReplay(String(row.id))}>{replayable.has(status) ? "Replay" : "Not needed"}</button></td></tr>; })}</tbody></table> : <div className="empty-inline">No stored work items. Queue depth is zero.</div>}</section>;
}

function KeyValuePanel({ title, values }: { title: string; values?: Record<string, unknown> }) {
  return <section className="panel detail-panel"><p className="eyebrow">LIVE CONFIGURATION</p><h3>{title}</h3><dl className="details-list">{Object.entries(values ?? {}).map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd>{formatValue(value)}</dd></div>)}</dl></section>;
}

function label(value: string): string { return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(3);
  if (typeof value === "object") return JSON.stringify(value);
  const text = String(value);
  return text.length > 72 ? `${text.slice(0, 69)}…` : text;
}

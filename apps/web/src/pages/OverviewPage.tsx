import { ArrowRight, CheckCircle2, Clock3, Database, ShieldCheck, Sparkles } from "../components/Icons";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { PageHeader, StatusPill } from "../components/PageHeader";
import { getCommerceOverview, getConsoleOverview } from "../lib/api";
import { useAuth } from "../auth/AuthProvider";

const workflow = [
  ["Signal", "Customer request enters the governed workspace"],
  ["Reason", "17-stage agent grounds, plans, and checks policy"],
  ["Approve", "High-risk actions require an independent reviewer"],
  ["Execute", "Digest-bound tool call runs exactly once"],
  ["Learn", "Outcome, cost, and evaluation evidence are recorded"],
];

export function OverviewPage() {
  const { accessToken: token } = useAuth();
  const commerce = useQuery({ queryKey: ["commerce-overview", token], queryFn: () => getCommerceOverview(token), enabled: Boolean(token) });
  const platform = useQuery({ queryKey: ["console-overview", token], queryFn: () => getConsoleOverview(token), enabled: Boolean(token) });
  return <>
    <section className="hero-card">
      <span className="hero-cloud hero-cloud-a" aria-hidden="true" />
      <span className="hero-cloud hero-cloud-b" aria-hidden="true" />
      <div className="hero-copy"><span className="hero-badge"><Sparkles size={14} /> Your governed operations brain</span><h2>Customer operations that resolve.<br/><em>Not just respond.</em></h2><p>ResolveAI learns from your policies, customer context, and operational evidence to resolve issues safely across every channel.</p><div className="hero-actions"><Link className="button primary" to="/resolution">Run a resolution <ArrowRight size={15} /></Link><Link className="button secondary" to="/traces">See how it reasons</Link></div></div>
      <div className="hero-system" aria-label="ResolveAI knowledge to outcomes architecture">
        <article className="system-stack knowledge-stack"><header><Database size={18} /><strong>Knowledge</strong></header><p>Grounding inputs</p><span>Customer context</span><span>Orders & payments</span><span>Policy knowledge</span><span>Retrieval evidence</span></article>
        <div className="system-connector"><i /><ArrowRight size={15} /></div>
        <div className="resolve-core"><div><Sparkles size={25} /><strong>ResolveAI</strong><small>17-stage agent</small></div></div>
        <div className="system-connector"><i /><ArrowRight size={15} /></div>
        <article className="system-stack outcome-stack"><header><CheckCircle2 size={18} /><strong>Outcomes</strong></header><p>Governed delivery</p><span>Grounded answers</span><span>Human approvals</span><span>Safe execution</span><span>Measured impact</span></article>
      </div>
    </section>
    <div className="trust-ribbon"><span>GROUND EVERY ANSWER</span><i>✦</i><span>APPROVE HIGH-RISK ACTIONS</span><i>✦</i><span>AUDIT EVERY STEP</span><i>✦</i><span>MEASURE REAL OUTCOMES</span></div>
    <div className="metric-grid">
      <article className="metric-card"><div><ShieldCheck size={18} /><span>Latest workflow</span></div><strong>{platform.data?.latest_step_count ?? 0}</strong><small>{platform.data?.latest_run_status ?? "loading"} · persisted stages</small></article>
      <article className="metric-card"><div><CheckCircle2 size={18} /><span>Completed runs</span></div><strong>{platform.data?.completed_runs ?? 0}</strong><small>of {platform.data?.agent_runs ?? 0} tenant runs</small></article>
      <article className="metric-card"><div><Clock3 size={18} /><span>Audit events</span></div><strong>{platform.data?.audit_events ?? 0}</strong><small>immutable recorded events</small></article>
      <article className="metric-card"><div><Database size={18} /><span>Evaluation scope</span></div><strong>{platform.data?.evaluation_cases ?? 0}</strong><small>{platform.data?.latest_evaluation_status ?? "no run"}</small></article>
    </div>
    <section className="panel workflow-panel"><div className="section-heading"><div><p className="eyebrow">THE CLOSED LOOP</p><h3>One evidence chain. Zero black boxes.</h3></div><StatusPill>Recorded synthetic evidence</StatusPill></div><div className="workflow-strip">{workflow.map(([name, description], index) => <div className={`workflow-step step-${index + 1}`} key={name}><b>{String(index + 1).padStart(2, "0")}</b><strong>{name}</strong><p>{description}</p>{index < workflow.length - 1 && <ArrowRight size={15} />}</div>)}</div></section>
    <div className="two-column">
      <section className="panel"><div className="section-heading"><div><p className="eyebrow">WHAT EXISTS NOW</p><h3>Production-shaped core</h3></div></div><ul className="check-list"><li>Hybrid versioned retrieval with citations and failure categories</li><li>Deterministic policy decisions: allow, approve, or deny</li><li>Separation of requester and reviewer with action-digest binding</li><li>Durable, idempotent tool execution and complete audit records</li><li>OpenTelemetry, Prometheus, evaluation queues, and cost events</li></ul></section>
      <section className="panel"><div className="section-heading"><div><p className="eyebrow">COMMERCEOPS INTELLIGENCE</p><h3>From operational signal to measured outcome</h3></div><StatusPill tone={commerce.data ? "good" : "warning"}>{commerce.isFetching ? "Loading" : commerce.data ? "Live backend" : "No measured data"}</StatusPill></div><p className="muted-copy">The operational loop now ingests facts, runs explainable detectors, ranks evidence-backed causes, governs corrective actions, and records outcomes.</p>{commerce.data && <div className="evidence-count">{commerce.data.signal_count} signals · {commerce.data.open_anomaly_count} open anomalies · {commerce.data.measured_outcome_count} measured outcomes</div>}<div className="route-links"><Link to="/signals">Signals <ArrowRight size={14} /></Link><Link to="/anomalies">Risks & anomalies <ArrowRight size={14} /></Link><Link to="/root-cause">Root causes <ArrowRight size={14} /></Link></div></section>
    </div>
  </>;
}

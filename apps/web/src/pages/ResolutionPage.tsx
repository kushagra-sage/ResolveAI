import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileText, LoaderCircle, Send, UserRound } from "../components/Icons";
import { useAuth } from "../auth/AuthProvider";
import { createResolution, type ResolutionResult } from "../lib/api";
import { PageHeader, StatusPill } from "../components/PageHeader";

const traceStages = ["Authenticate", "Input guard", "Classify intent", "Load customer", "Retrieve context", "Rerank", "Policy check", "Finalize audit"];

export function ResolutionPage() {
  const { accessToken: token } = useAuth();
  const [message, setMessage] = useState("I returned my laptop two weeks ago, but the refund still has not arrived.");
  const [result, setResult] = useState<ResolutionResult | null>(null);
  const mutation = useMutation({
    mutationFn: () => createResolution(token, {
      message,
      order_id: "a1cb0753-9fab-5bfe-a70d-7ddb6845bd50",
      payment_id: "86d8c584-7dc1-5fec-9bb0-d47556fcffcf",
      currency: "INR",
      reason_code: "RETURN_RECEIVED",
    }),
    onSuccess: setResult,
  });
  const run = () => mutation.mutate();

  return <>
    <PageHeader eyebrow="CUSTOMER OPERATIONS" title="Resolution workspace" description="Run the real governed agent workflow, review grounded evidence, and hand risky actions to an independent approver." actions={<StatusPill tone={result?.status === "completed" ? "good" : "neutral"}>{result ? result.status : "Ready"}</StatusPill>} />
    <div className="resolution-grid">
      <section className="panel conversation-panel"><div className="ticket-heading"><div><p className="eyebrow">TICKET TKT-DEMO-014</p><h3>Refund has not arrived</h3></div><StatusPill tone="danger">High risk</StatusPill></div>
        <div className="message-bubble customer"><div className="message-author"><UserRound size={16} />Customer · 10:42</div><p>{message}</p></div>
        {result && <div className="message-bubble ai" aria-live="polite"><div className="message-author"><SparkIcon />ResolveAI · grounded result</div><p>{result.answer}</p><div className="result-meta"><span>Intent: {result.intent ?? "unclassified"}</span><span>Risk: {result.risk_level ?? "unknown"}</span><span>Trace: {result.trace_id.slice(0, 10)}…</span></div>{result.approval_request_id && <div className="approval-notice"><AlertTriangle size={16} />Approval required · {result.approval_request_id.slice(0, 8)}</div>}</div>}
        <div className="composer"><label htmlFor="customer-message">Customer request</label><textarea id="customer-message" rows={4} value={message} onChange={(event) => setMessage(event.target.value)} /><div><span>{mutation.error instanceof Error ? mutation.error.message : "Uses POST /v1/resolutions"}</span><button className="button primary" disabled={!token || !message.trim() || mutation.isPending} onClick={run}>{mutation.isPending ? <LoaderCircle className="spin" size={16} /> : <Send size={16} />} Run governed resolution</button></div></div>
      </section>
      <aside className="resolution-side">
        <section className="panel"><p className="eyebrow">CUSTOMER CONTEXT</p><div className="customer-title"><div className="customer-avatar">DC</div><div><h3>Demo Customer</h3><small>Synthetic test identity</small></div></div><dl className="details-list"><div><dt>Order</dt><dd>ORD-DEMO-001</dd></div><div><dt>Status</dt><dd>Return received</dd></div><div><dt>Total</dt><dd>₹2,360.00</dd></div><div><dt>Risk control</dt><dd>Approval gated</dd></div></dl></section>
        <section className="panel"><div className="section-heading"><div><p className="eyebrow">RUN TRACE</p><h3>Safety path</h3></div>{mutation.isPending && <StatusPill tone="warning">Running</StatusPill>}</div><ol className="compact-trace">{traceStages.map((stage, index) => <li key={stage} className={result ? "complete" : mutation.isPending && index < 4 ? "active" : ""}><span>{result ? <CheckCircle2 size={16} /> : index + 1}</span><div><strong>{stage}</strong><small>{result ? "recorded" : "awaiting run"}</small></div></li>)}</ol></section>
        <section className="panel evidence-card"><FileText size={19} /><div><strong>Evidence is run-specific</strong><p>Exact citations and policy decisions appear after the backend returns them. The interface never invents missing evidence.</p></div></section>
      </aside>
    </div>
  </>;
}

function SparkIcon() { return <span className="spark-icon">R</span>; }

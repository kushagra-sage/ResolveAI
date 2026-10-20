import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Check, ClipboardCheck, Pencil, X } from "../components/Icons";
import { useAuth } from "../auth/AuthProvider";
import { z } from "zod";
import { decideApproval, listApprovals, type Approval } from "../lib/api";
import { PageHeader, StatusPill } from "../components/PageHeader";

const decisionSchema = z.object({ reason: z.string().min(6, "Provide an auditable reason (at least 6 characters)."), modifiedAction: z.string() });
type DecisionForm = z.infer<typeof decisionSchema>;

export function ApprovalsPage() {
  const { accessToken: token } = useAuth();
  const approvals = useQuery({ queryKey: ["approvals", token], queryFn: () => listApprovals(token), enabled: Boolean(token) });

  return <>
    <PageHeader eyebrow="HUMAN GOVERNANCE" title="Approval center" description="Review evidence, preserve separation of duties, and record a reason before any high-risk action executes." actions={<StatusPill tone={approvals.data?.length ? "warning" : "good"}>{approvals.isFetching ? "Loading" : `${approvals.data?.length ?? 0} pending`}</StatusPill>} />
    {approvals.error && <div className="inline-error">{approvals.error instanceof Error ? approvals.error.message : "Unable to load approvals."}</div>}
    <div className="approval-list">
      {approvals.data?.map((approval) => <ApprovalCard key={approval.id} approval={approval} token={token} />)}
      {!approvals.isFetching && (!approvals.data || approvals.data.length === 0) && <section className="panel empty-state"><div className="empty-icon"><ClipboardCheck size={28} /></div><h3>No pending approvals</h3><p>Every governed action is currently resolved.</p></section>}
    </div>
  </>;
}

function ApprovalCard({ approval, token }: { approval: Approval; token: string }) {
  const queryClient = useQueryClient();
  const [serverMessage, setServerMessage] = useState("");
  const form = useForm<DecisionForm>({ resolver: zodResolver(decisionSchema), defaultValues: { reason: "", modifiedAction: JSON.stringify(approval.action, null, 2) } });
  const mutation = useMutation({
    mutationFn: ({ decision, values }: { decision: "APPROVE" | "EDIT" | "REJECT"; values: DecisionForm }) => {
      let modifiedAction: Record<string, unknown> | undefined;
      if (decision === "EDIT") {
        const parsed: unknown = JSON.parse(values.modifiedAction);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Edited action must be a JSON object.");
        modifiedAction = parsed as Record<string, unknown>;
      }
      return decideApproval(token, approval.id, decision, values.reason, modifiedAction);
    },
    onSuccess: async (result) => { setServerMessage(`${result.status}: decision recorded in the audit trail.`); await queryClient.invalidateQueries({ queryKey: ["approvals"] }); },
    onError: (error) => setServerMessage(error instanceof Error ? error.message : "Decision failed."),
  });
  const submitDecision = (decision: "APPROVE" | "EDIT" | "REJECT") => form.handleSubmit((values) => mutation.mutate({ decision, values }))();

  return <section className="panel approval-card"><div className="approval-head"><div><StatusPill tone="warning">Pending · {approval.required_role}</StatusPill><h3>{approval.action_type.replaceAll("_", " ")}</h3><p>Run {approval.run_id.slice(0, 8)} · expires {new Date(approval.expires_at).toLocaleString()}</p></div><code>{approval.action_digest.slice(0, 12)}…</code></div>
    <div className="approval-body"><div><p className="field-label">Proposed action</p><pre>{JSON.stringify(approval.action, null, 2)}</pre><p className="field-label">Supporting evidence</p><div className="evidence-count">{approval.evidence.length} evidence record{approval.evidence.length === 1 ? "" : "s"} bound to this request</div></div>
      <form onSubmit={(event) => event.preventDefault()}><label htmlFor={`reason-${approval.id}`}>Review reason</label><textarea id={`reason-${approval.id}`} rows={3} {...form.register("reason")} placeholder="Why is this decision appropriate?" />{form.formState.errors.reason && <small className="form-error">{form.formState.errors.reason.message}</small>}<label htmlFor={`action-${approval.id}`}>Editable action JSON</label><textarea id={`action-${approval.id}`} rows={7} className="code-input" {...form.register("modifiedAction")} />{serverMessage && <p className="form-status">{serverMessage}</p>}<div className="decision-actions"><button type="button" className="button danger" disabled={mutation.isPending} onClick={() => submitDecision("REJECT")}><X size={15} /> Reject</button><button type="button" className="button secondary" disabled={mutation.isPending} onClick={() => submitDecision("EDIT")}><Pencil size={15} /> Approve edit</button><button type="button" className="button primary" disabled={mutation.isPending} onClick={() => submitDecision("APPROVE")}><Check size={15} /> Approve & execute</button></div></form>
    </div>
  </section>;
}

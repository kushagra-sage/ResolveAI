import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CircleDollarSign,
  Database,
  MessageSquareText,
  PackageSearch,
  Users,
} from "../components/Icons";
import { useAuth } from "../auth/AuthProvider";
import { PageHeader, StatusPill } from "../components/PageHeader";
import { getCustomerSupportOverview, getCustomerWorkspace } from "../lib/api";

export function CustomerPage() {
  const { accessToken: activeToken } = useAuth();
  const [selectedCustomer, setSelectedCustomer] = useState("");
  const overview = useQuery({
    queryKey: ["customer-support", activeToken],
    queryFn: () => getCustomerSupportOverview(activeToken),
    enabled: Boolean(activeToken),
  });
  const workspace = useQuery({
    queryKey: ["customer-workspace", activeToken, selectedCustomer],
    queryFn: () => getCustomerWorkspace(activeToken, selectedCustomer),
    enabled: Boolean(activeToken && selectedCustomer),
  });
  const lifetimeValue = overview.data?.customers.reduce(
    (total, customer) => total + customer.lifetime_value_minor,
    0,
  ) ?? 0;

  return <>
    <PageHeader
      eyebrow="CUSTOMER INTELLIGENCE"
      title="Customer 360"
      description="A tenant-scoped view of synthetic customers, orders, support demand, and current case state."
      actions={<StatusPill tone={overview.data ? "good" : "warning"}>{overview.isFetching ? "Loading" : overview.data ? "Synthetic dataset active" : "No data"}</StatusPill>}
    />
    {overview.error && <div className="inline-error">{overview.error instanceof Error ? overview.error.message : "Unable to load customer support data."}</div>}
    <div className="evidence-notice synthetic-notice"><Database size={16} /><span><strong>Safe demonstration data.</strong> Every identity, message, order, and ticket on this page is deterministic and synthetic; no real customer PII is present.</span></div>
    {overview.data && <>
      <div className="metric-grid customer-metrics">
        <Metric icon={<Users />} label="Customers" value={String(overview.data.customer_count)} note="tenant-scoped profiles" />
        <Metric icon={<MessageSquareText />} label="Support tickets" value={String(overview.data.ticket_count)} note={`${overview.data.open_ticket_count} need attention`} />
        <Metric icon={<PackageSearch />} label="Orders" value={String(overview.data.customers.reduce((total, customer) => total + customer.order_count, 0))} note="linked commerce context" />
        <Metric icon={<CircleDollarSign />} label="Order value" value={formatMoney(lifetimeValue, "INR")} note="synthetic, not revenue" />
      </div>
      <section className="panel table-panel customer-table">
        <div className="section-heading"><div><p className="eyebrow">SYNTHETIC-SUPPORT-V1</p><h3>Customer and case workload</h3></div><StatusPill tone="neutral">No real PII</StatusPill></div>
        <table>
          <thead><tr><th>Customer</th><th>Latest support request</th><th>Tickets</th><th>Orders</th><th>Order value</th><th>Case state</th><th>Profile</th></tr></thead>
          <tbody>{overview.data.customers.map((customer) => <tr key={customer.id}>
            <td><strong>{customer.name}</strong><small>{customer.external_ref} · {customer.locale}</small></td>
            <td><strong>{customer.latest_ticket_subject ?? "No request"}</strong><small>{customer.email}</small></td>
            <td>{customer.ticket_count} total · {customer.open_ticket_count} open</td>
            <td>{customer.order_count}</td>
            <td>{formatMoney(customer.lifetime_value_minor, customer.currency)}</td>
            <td><StatusPill tone={ticketTone(customer.latest_ticket_status)}>{customer.latest_ticket_status ?? "none"}</StatusPill></td>
            <td><button className="button secondary small" onClick={() => setSelectedCustomer(customer.id)}>Open 360</button></td>
          </tr>)}</tbody>
        </table>
      </section>
      {selectedCustomer && <CustomerWorkspacePanel data={workspace.data} loading={workspace.isFetching} error={workspace.error} />}
    </>}
    {!overview.data && !overview.isFetching && <section className="panel empty-state"><Users size={28} /><h3>No customer data available</h3><p>Your authenticated role has no visible customer records, or the tenant dataset is empty.</p></section>}
  </>;
}

function CustomerWorkspacePanel({ data, loading, error }: { data: Awaited<ReturnType<typeof getCustomerWorkspace>> | undefined; loading: boolean; error: unknown }) {
  if (loading) return <section className="panel customer-workspace"><p>Loading complete customer context…</p></section>;
  if (error) return <div className="inline-error">{error instanceof Error ? error.message : "Unable to load customer workspace."}</div>;
  if (!data) return null;
  const sections: Array<[string, Array<Record<string, string | number | null>>]> = [["Orders", data.orders], ["Payments", data.payments], ["Shipments", data.shipments], ["Tickets", data.tickets], ["Conversation & agent notes", data.messages], ["Refunds", data.refunds], ["Resolution outcomes", data.resolution_outcomes]];
  return <section className="panel customer-workspace"><div className="section-heading"><div><p className="eyebrow">COMPLETE CUSTOMER CONTEXT</p><h3>{data.customer.name}</h3><p className="muted-copy">{data.customer.external_ref} · {data.customer.email} · {data.customer.locale}</p></div><StatusPill tone="good">{data.customer.status}</StatusPill></div><div className="workspace-columns">{sections.map(([title, rows]) => <article className="workspace-block" key={title}><h4>{title} · {rows.length}</h4><ul>{rows.slice(0, 8).map((row, index) => <li key={String(row.id ?? index)}><strong>{String(row.subject ?? row.external_ref ?? row.status ?? row.author_type ?? row.intent ?? "Record")}</strong><small>{workspaceSummary(row)}</small></li>)}{rows.length === 0 && <li>No stored records</li>}</ul></article>)}</div></section>;
}

function workspaceSummary(row: Record<string, string | number | null>): string {
  return Object.entries(row).filter(([key, value]) => key !== "id" && value !== null).slice(0, 4).map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`).join(" · ");
}

function Metric({ icon, label, value, note }: { icon: ReactNode; label: string; value: string; note: string }) {
  return <article className="metric-card"><div>{icon}<span>{label}</span></div><strong>{value}</strong><small>{note}</small></article>;
}

function formatMoney(valueMinor: number, currency: string): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(valueMinor / 100);
}

function ticketTone(status: string | null): "good" | "warning" | "neutral" {
  if (status === "resolved" || status === "closed") return "good";
  if (status === "open" || status === "pending") return "warning";
  return "neutral";
}

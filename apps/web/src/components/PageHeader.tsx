import type { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="page-header"><div><p className="eyebrow">{eyebrow}</p><h2>{title}</h2><p className="page-description">{description}</p></div>{actions && <div className="page-actions">{actions}</div>}</div>;
}

export function StatusPill({ tone = "neutral", children }: { tone?: "good" | "warning" | "danger" | "neutral"; children: ReactNode }) {
  return <span className={`status-pill ${tone}`}>{children}</span>;
}

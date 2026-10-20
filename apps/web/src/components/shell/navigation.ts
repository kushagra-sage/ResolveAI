import type { ComponentType } from "react";
import type { IconProps } from "../Icons";
import { Activity, AlertTriangle, BarChart3, BookOpen, BrainCircuit, CircleDollarSign, ClipboardCheck, FlaskConical, Gauge, HeartPulse, Home, ListChecks, MessageSquareText, PackageSearch, Radar, RefreshCcw, Settings, ShieldCheck, Sparkles, Users } from "../Icons";

type LucideIcon = ComponentType<IconProps>;

export type NavItem = { label: string; path: string; icon: LucideIcon; roles?: string[] };
export type NavGroup = { label: string; items: NavItem[] };

export const navigation: NavGroup[] = [
  { label: "Control plane", items: [
    { label: "Overview", path: "/", icon: Home },
    { label: "Resolution workspace", path: "/resolution", icon: MessageSquareText },
    { label: "Approval center", path: "/approvals", icon: ClipboardCheck, roles: ["supervisor", "admin"] },
  ]},
  { label: "Intelligence", items: [
    { label: "Customer 360", path: "/customers", icon: Users, roles: ["support_agent", "supervisor", "admin"] },
    { label: "Signal explorer", path: "/signals", icon: Radar, roles: ["support_agent", "supervisor", "admin"] },
    { label: "Anomaly queue", path: "/anomalies", icon: AlertTriangle, roles: ["support_agent", "supervisor", "admin"] },
    { label: "Root-cause studio", path: "/root-cause", icon: BrainCircuit, roles: ["supervisor", "admin"] },
    { label: "Actions", path: "/actions", icon: Sparkles, roles: ["supervisor", "admin"] },
    { label: "Outcomes", path: "/outcomes", icon: RefreshCcw, roles: ["supervisor", "admin"] },
  ]},
  { label: "AI operations", items: [
    { label: "Trace explorer", path: "/traces", icon: Activity, roles: ["support_agent", "supervisor", "admin"] },
    { label: "Evaluation lab", path: "/evaluation", icon: FlaskConical, roles: ["supervisor", "admin"] },
    { label: "RAG evolution", path: "/rag-evolution", icon: BookOpen, roles: ["supervisor", "admin"] },
    { label: "Cost & reliability", path: "/cost", icon: CircleDollarSign, roles: ["supervisor", "admin"] },
    { label: "Model registry", path: "/models", icon: Gauge, roles: ["admin"] },
  ]},
  { label: "Governance", items: [
    { label: "Policies", path: "/policies", icon: ShieldCheck, roles: ["supervisor", "admin"] },
    { label: "Audit log", path: "/audit", icon: ListChecks, roles: ["supervisor", "admin"] },
    { label: "Reports", path: "/reports", icon: BarChart3, roles: ["supervisor", "admin"] },
    { label: "System health", path: "/health", icon: HeartPulse, roles: ["admin"] },
    { label: "Settings", path: "/settings", icon: Settings, roles: ["admin"] },
    { label: "Knowledge", path: "/knowledge", icon: PackageSearch, roles: ["support_agent", "supervisor", "admin"] },
  ]},
];

export const allNavigation = navigation.flatMap((group) => group.items);

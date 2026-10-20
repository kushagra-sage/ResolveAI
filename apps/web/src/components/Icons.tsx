import type { SVGProps } from "react";

export type IconProps = SVGProps<SVGSVGElement> & { size?: number | string; strokeWidth?: number | string };

export function Glyph({ size = 18, strokeWidth = 1.8, ...props }: IconProps) {
  return <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d="M4 12h4l2.2-6 3.6 12 2.2-6h4" /><circle cx="12" cy="12" r="9" opacity=".28" /></svg>;
}

export const Activity = Glyph, AlertTriangle = Glyph, ArrowDownRight = Glyph, ArrowRight = Glyph,
  ArrowUpRight = Glyph, BarChart3 = Glyph, BookOpen = Glyph, Braces = Glyph, BrainCircuit = Glyph,
  Check = Glyph, CheckCircle2 = Glyph, CircleDollarSign = Glyph, ClipboardCheck = Glyph, Clock3 = Glyph,
  Command = Glyph, Construction = Glyph, Database = Glyph, FileText = Glyph, FlaskConical = Glyph,
  Gauge = Glyph, HeartPulse = Glyph, Home = Glyph, KeyRound = Glyph, ListChecks = Glyph, LogOut = Glyph,
  LoaderCircle = Glyph, Menu = Glyph, MessageSquareText = Glyph, Moon = Glyph, PackageSearch = Glyph,
  Pencil = Glyph, Radar = Glyph, RefreshCcw = Glyph, RefreshCw = Glyph, Search = Glyph, Send = Glyph,
  Settings = Glyph, ShieldCheck = Glyph, Sparkles = Glyph, Sun = Glyph, TriangleAlert = Glyph,
  UserRound = Glyph, Users = Glyph, X = Glyph;

const path = require("path");
const fs = require("fs");

const runtime = process.env.RESOLVEAI_PPTX_RUNTIME || "C:/Users/KIIT0001/AppData/Local/Temp/resolveai-pptx-runtime/node_modules";
const pptxgen = require(path.join(runtime, "pptxgenjs"));
const sharp = require(path.join(runtime, "sharp"));

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "artifacts", "ResolveAI_Faculty_Presentation.pptx");
const SHOTS = path.join(ROOT, "artifacts", "demo");
const FIGURE = path.join(ROOT, "research", "figures", "baseline-vs-resolveai.png");

const C = {
  ink: "07131D",
  aqua: "B9EEF1",
  lime: "9DF01B",
  white: "FFFFFF",
  paper: "F7FAF9",
  gray: "52616B",
  line: "15313B",
  pink: "F4D1EA",
  orange: "F8DAB7",
  mint: "C8F2DA",
  lavender: "D9D0FA",
  danger: "E05A47",
};

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.author = "ResolveAI";
pptx.subject = "Faculty project presentation";
pptx.title = "ResolveAI — Governed AI from signal to outcome";
pptx.company = "ResolveAI";
pptx.lang = "en-IN";
pptx.theme = {
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  lang: "en-US",
};
pptx.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.paper },
  objects: [
    { rect: { x: 0.35, y: 0.28, w: 0.42, h: 0.42, rectRadius: 0.1, fill: { color: C.lime }, line: { color: C.ink, width: 1 } } },
    { text: { text: "R", options: { x: 0.35, y: 0.36, w: 0.42, h: 0.16, fontFace: "Arial", fontSize: 9, bold: true, align: "center", margin: 0, color: C.ink, isTextBox: true } } },
    { text: { text: "ResolveAI", options: { x: 0.86, y: 0.35, w: 1.4, h: 0.2, fontFace: "Arial", fontSize: 11, bold: true, margin: 0, color: C.ink, isTextBox: true } } },
    { text: { text: "SYNTHETIC EVIDENCE • LOCAL VERIFIED BUILD", options: { x: 9.2, y: 0.37, w: 3.55, h: 0.16, fontFace: "Arial", fontSize: 8, bold: true, align: "right", margin: 0, color: C.gray, charSpacing: 1.1, isTextBox: true } } },
  ],
  slideNumber: { x: 12.62, y: 7.14, w: 0.3, h: 0.18, fontFace: "Arial", fontSize: 8, color: C.gray, align: "right", margin: 0 },
});

function tx(slide, text, x, y, w, h, options = {}) {
  slide.addText(text, {
    x, y, w, h, fontFace: "Arial", fontSize: 16, color: C.ink,
    margin: 0, breakLine: false, fit: "shrink", valign: "mid", isTextBox: true,
    ...options,
  });
}

function card(slide, x, y, w, h, fill = C.white, radius = 0.12) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h, rectRadius: radius,
    fill: { color: fill }, line: { color: C.line, width: 1.1 },
    shadow: { type: "outer", color: "000000", opacity: 0.13, blur: 1.5, angle: 45, distance: 1.3 },
  });
}

function title(slide, eyebrow, heading, sub = "") {
  tx(slide, eyebrow.toUpperCase(), 0.55, 0.9, 4.3, 0.2, { fontSize: 9, bold: true, color: C.gray, charSpacing: 1.5 });
  tx(slide, heading, 0.55, 1.14, 12.0, 0.72, { fontSize: 28, bold: true, valign: "top" });
  if (sub) tx(slide, sub, 0.55, 1.98, 11.9, 0.2, { fontSize: 11, color: C.gray, valign: "top" });
}

function pill(slide, text, x, y, w, fill = C.lime, color = C.ink) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w, h: 0.34, rectRadius: 0.12, fill: { color: fill }, line: { color: C.ink, width: 0.8 } });
  tx(slide, text, x + 0.08, y + 0.04, w - 0.16, 0.22, { fontSize: 9, bold: true, align: "center", color });
}

function stat(slide, value, label, x, y, w, fill) {
  card(slide, x, y, w, 1.42, fill);
  tx(slide, value, x + 0.18, y + 0.18, w - 0.36, 0.58, { fontSize: 30, bold: true });
  tx(slide, label, x + 0.18, y + 0.84, w - 0.36, 0.34, { fontSize: 11, bold: true, color: C.gray, valign: "top" });
}

async function contain(imagePath, x, y, w, h) {
  const meta = await sharp(imagePath).metadata();
  const ratio = meta.width / meta.height;
  const boxRatio = w / h;
  let iw = w, ih = h, ix = x, iy = y;
  if (ratio > boxRatio) {
    ih = w / ratio;
    iy = y + (h - ih) / 2;
  } else {
    iw = h * ratio;
    ix = x + (w - iw) / 2;
  }
  return { path: imagePath, x: ix, y: iy, w: iw, h: ih };
}

async function screenshot(slide, filename, x, y, w, h, caption = "") {
  card(slide, x, y, w, h, C.white);
  slide.addImage(await contain(path.join(SHOTS, filename), x + 0.08, y + 0.08, w - 0.16, h - (caption ? 0.45 : 0.16)));
  if (caption) tx(slide, caption, x + 0.18, y + h - 0.3, w - 0.36, 0.16, { fontSize: 9, bold: true, color: C.gray });
}

function row(slide, n, heading, body, x, y, w, fill) {
  slide.addShape(pptx.ShapeType.ellipse, { x, y: y + 0.05, w: 0.42, h: 0.42, fill: { color: fill }, line: { color: C.ink, width: 0.8 } });
  tx(slide, String(n), x, y + 0.13, 0.42, 0.12, { fontSize: 9, bold: true, align: "center" });
  tx(slide, heading, x + 0.58, y, w - 0.58, 0.25, { fontSize: 14, bold: true });
  tx(slide, body, x + 0.58, y + 0.28, w - 0.58, 0.45, { fontSize: 11, color: C.gray, valign: "top" });
}

function addNotes(slide, notes) { slide.addNotes(notes); }

async function build() {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });

  // 1 — title
  {
    const s = pptx.addSlide();
    s.background = { color: C.aqua };
    pill(s, "GOVERNED AGENTIC RAG", 0.72, 0.65, 2.3, C.white);
    tx(s, "ResolveAI", 0.72, 1.22, 5.5, 0.72, { fontSize: 48, bold: true });
    tx(s, "Customer operations that resolve.\nNot just respond.", 0.72, 2.0, 5.5, 1.45, { fontSize: 31, bold: true, valign: "top" });
    tx(s, "From evidence to policy, human approval, safe execution, and measurable learning.", 0.72, 3.68, 5.2, 0.72, { fontSize: 17, color: C.gray, valign: "top" });
    pill(s, "168-case benchmark", 0.72, 4.72, 1.8, C.lime);
    pill(s, "71 backend tests", 2.68, 4.72, 1.55, C.white);
    pill(s, "13 browser tests", 4.39, 4.72, 1.55, C.white);
    await screenshot(s, "overview.png", 6.45, 0.72, 6.25, 5.95, "Live authenticated product overview");
    tx(s, "Faculty project presentation • October 2026", 0.72, 6.75, 5.8, 0.24, { fontSize: 11, bold: true, color: C.gray });
    addNotes(s, "Open by stating that the workflow is real and locally executed, while the customer records and benchmark are synthetic. The contribution is the governed control plane, not a new foundation model.");
  }

  // 2 — problem
  {
    const s = pptx.addSlide("CONTENT");
    title(s, "Why this matters", "Support AI should do more than generate plausible text", "Operational actions create risks that a chat-only demo does not expose.");
    stat(s, "01", "Evidence can be missing, stale, or manipulated", 0.58, 2.52, 3.8, C.pink);
    stat(s, "02", "A model proposal is not authorization", 4.76, 2.52, 3.8, C.orange);
    stat(s, "03", "Side effects must be exact, verified, and replay-safe", 8.94, 2.52, 3.8, C.mint);
    card(s, 0.58, 4.42, 12.16, 1.55, C.ink);
    tx(s, "ResolveAI’s core idea", 0.88, 4.73, 2.1, 0.25, { fontSize: 12, bold: true, color: C.lime });
    tx(s, "Put deterministic controls around agentic RAG so every answer and action has an inspectable path from identity and evidence to outcome.", 3.05, 4.63, 9.15, 0.65, { fontSize: 22, bold: true, color: C.white, valign: "mid" });
    tx(s, "Real impact target: safer automation, faster investigation, reproducible evaluation, and accountable human oversight.", 0.88, 6.35, 11.8, 0.32, { fontSize: 14, bold: true, color: C.gray, align: "center" });
    addNotes(s, "Explain the problem in business language: once AI can issue refunds or modify operations, fluency is not enough. Identity, policy, approval, idempotency, verification, and evidence become product requirements.");
  }

  // 3 — workflow
  {
    const s = pptx.addSlide("CONTENT");
    title(s, "End-to-end workflow", "One governed path from signal to outcome", "Each transition persists evidence; risky actions cannot bypass policy or approval.");
    const steps = [
      ["Customer", C.aqua], ["RAG", C.pink], ["Policy", C.orange], ["Approval", C.lavender], ["Execute", C.mint], ["Evidence", C.lime],
    ];
    steps.forEach(([name, fill], i) => {
      const x = 0.55 + i * 2.12;
      card(s, x, 2.55, 1.7, 1.05, fill);
      tx(s, String(i + 1).padStart(2, "0"), x + 0.15, 2.72, 0.36, 0.18, { fontSize: 9, bold: true, color: C.gray });
      tx(s, name, x + 0.15, 2.95, 1.38, 0.28, { fontSize: 16, bold: true, align: "center" });
      if (i < steps.length - 1) s.addShape(pptx.ShapeType.chevron, { x: x + 1.78, y: 2.9, w: 0.25, h: 0.34, fill: { color: C.ink }, line: { color: C.ink } });
    });
    row(s, 1, "Authenticate and isolate", "Keycloak PKCE login, server-side RBAC, and tenant-scoped sessions.", 0.72, 4.2, 3.75, C.aqua);
    row(s, 2, "Ground and decide", "Hybrid retrieval with citations; deterministic ALLOW / APPROVAL / DENY.", 4.65, 4.2, 3.85, C.orange);
    row(s, 3, "Act and learn", "Idempotent tools, verification reads, audit, cost, traces, and evaluation.", 8.72, 4.2, 3.85, C.lime);
    card(s, 1.6, 5.75, 10.1, 0.66, C.white);
    tx(s, "Login → customer → resolution → retrieval → policy → approval → execution → trace → cost → evaluation", 1.85, 5.94, 9.6, 0.22, { fontSize: 14, bold: true, align: "center" });
    addNotes(s, "Walk left to right. Stress that approval is bound to an action digest, and resume reruns authorization and policy checks before execution.");
  }

  // 4 — architecture
  {
    const s = pptx.addSlide("CONTENT");
    title(s, "Implemented architecture", "A modular control plane with durable state", "Eleven local services reproduce identity, storage, execution, telemetry, and operations.");
    const blocks = [
      ["React workspace", 0.62, 2.55, C.aqua], ["Keycloak", 0.62, 4.05, C.lavender],
      ["FastAPI control plane", 3.35, 3.25, C.lime], ["LangGraph + policy", 6.05, 2.35, C.orange],
      ["PostgreSQL + pgvector", 6.05, 4.2, C.pink], ["Durable workers", 8.77, 3.25, C.mint],
      ["OTel → Prometheus → Grafana", 10.75, 5.05, C.white],
    ];
    blocks.forEach(([name, x, y, fill]) => { card(s, x, y, name.length > 23 ? 2.0 : 2.25, 0.78, fill); tx(s, name, x + 0.12, y + 0.18, name.length > 23 ? 1.76 : 2.01, 0.28, { fontSize: 12, bold: true, align: "center" }); });
    const arrows = [
      [2.88, 2.95, 0.44], [2.88, 4.43, 0.44], [5.64, 3.62, 0.38],
      [8.33, 2.75, 0.41], [8.33, 4.58, 0.41], [10.64, 3.62, 0.38],
    ];
    arrows.forEach(([x, y, w]) => s.addShape(pptx.ShapeType.line, { x, y, w, h: 0, line: { color: C.ink, width: 1.5, beginArrowType: "none", endArrowType: "triangle" } }));
    pill(s, "OIDC + PKCE", 0.76, 3.54, 1.25, C.white);
    pill(s, "tenant-scoped", 3.82, 4.35, 1.4, C.white);
    pill(s, "retry / DLQ / replay", 8.96, 4.36, 1.58, C.white);
    tx(s, "Storage: SeaweedFS S3 artifacts • Coordination: Redis • Scheduler: detector worker • Delivery: evaluation/outbox worker", 0.68, 6.35, 11.95, 0.35, { fontSize: 12, bold: true, color: C.gray, align: "center" });
    addNotes(s, "Describe the design as a modular monolith plus workers, not a premature microservice fleet. PostgreSQL is authoritative; Redis is disposable coordination. SeaweedFS replaced the earlier MinIO choice for local S3 compatibility.");
  }

  // 5 — auth + customer 360
  {
    const s = pptx.addSlide("CONTENT");
    title(s, "Product surface", "Authentication and Customer 360 make it a real product", "The UI uses live, tenant-scoped backend data and labels synthetic records clearly.");
    await screenshot(s, "customer-360.png", 0.58, 2.28, 7.55, 4.35, "Customer, orders, payments, shipments, tickets, notes, refunds, outcomes");
    card(s, 8.46, 2.28, 4.3, 4.35, C.white);
    pill(s, "NO PASTED TOKENS", 8.8, 2.66, 1.62, C.lime);
    row(s, 1, "Real login", "Authorization Code + PKCE, logout, automatic refresh.", 8.78, 3.3, 3.45, C.aqua);
    row(s, 2, "Role-aware UX", "Customer, agent, supervisor, and admin routes.", 8.78, 4.28, 3.45, C.lavender);
    row(s, 3, "Backend authority", "Permissions are resolved server-side from PostgreSQL.", 8.78, 5.26, 3.45, C.mint);
    addNotes(s, "Show that the project is no longer a developer demo that asks users to paste bearer tokens. Customer 360 ties the AI control plane to the business case.");
  }

  // 6 — resolution
  {
    const s = pptx.addSlide("CONTENT");
    title(s, "Resolution workspace", "A governed result—not an unchecked answer", "Every risky action passes through typed policy and independent review.");
    await screenshot(s, "resolution.png", 0.58, 2.25, 8.0, 4.45, "Live resolution workflow");
    card(s, 8.9, 2.25, 3.85, 4.45, C.ink);
    tx(s, "Execution boundary", 9.24, 2.62, 3.1, 0.34, { fontSize: 20, bold: true, color: C.white });
    const items = [
      ["Evidence", "Citations or abstention"], ["Policy", "ALLOW / APPROVAL / DENY"],
      ["Approval", "Exact action digest"], ["Tool", "Idempotency + verification"], ["Audit", "Actor, policy, trace, outcome"],
    ];
    items.forEach(([a, b], i) => {
      const y = 3.24 + i * 0.58;
      slideDot(s, 9.25, y, i % 2 ? C.lime : C.aqua);
      tx(s, a, 9.57, y - 0.02, 0.9, 0.2, { fontSize: 11, bold: true, color: C.white });
      tx(s, b, 10.45, y - 0.02, 1.83, 0.28, { fontSize: 10, color: "CAD6DA", valign: "top" });
    });
    addNotes(s, "Use a request that triggers approval. Explain that a model cannot grant itself permission and that human approval cannot override the hard ceiling.");
  }

  // 7 — trace and system health
  {
    const s = pptx.addSlide("CONTENT");
    title(s, "Operational transparency", "Reasoning evidence and recovery state, together", "Traces, queues, retries, dead letters, and reconciliation are first-class product surfaces.");
    await screenshot(s, "trace-explorer.png", 0.58, 2.28, 6.02, 4.35, "Persisted agent stages and outcomes");
    await screenshot(s, "system-health.png", 6.78, 2.28, 5.98, 4.35, "Queue depth, retries, replay, and reconciliation");
    pill(s, "QUEUE DEPTH 0", 4.92, 6.55, 1.48, C.lime);
    pill(s, "OUTBOX DEPTH 0", 6.56, 6.55, 1.58, C.mint);
    addNotes(s, "Point out the durable worker result: 25 pending online evaluations and four outbox events were processed successfully; both queue depths reached zero.");
  }

  // 8 — evaluation UI
  {
    const s = pptx.addSlide("CONTENT");
    title(s, "Evidence pages", "No placeholders, no fake metrics, no silent zeros", "Evaluation, RAG, trace, cost, and audit pages query authenticated backend records.");
    await screenshot(s, "evaluation-lab.png", 0.58, 2.27, 7.25, 4.4, "Versioned evaluation runs and results");
    card(s, 8.15, 2.27, 4.62, 4.4, C.white);
    row(s, 1, "Measured", "Stored scores, sample counts, versions, and status.", 8.5, 2.7, 3.72, C.lime);
    row(s, 2, "Filterable", "Trace status, audit event/outcome, pagination.", 8.5, 3.72, 3.72, C.aqua);
    row(s, 3, "Inspectable", "Document versions, chunks, citations, tool receipts.", 8.5, 4.74, 3.72, C.pink);
    row(s, 4, "Honest", "Unknown cost stays unknown; empty state stays empty.", 8.5, 5.76, 3.72, C.orange);
    addNotes(s, "This slide is the credibility story. The project does not fabricate operational success when data are absent.");
  }

  // 9 — benchmark chart
  {
    const s = pptx.addSlide("CONTENT");
    title(s, "Controlled research benchmark", "Quality and safety improve across 168 synthetic cases", "Paired comparison against a minimal keyword baseline; seed 20261006.");
    s.addChart(pptx.ChartType.bar, [
      { name: "Baseline", labels: ["Answer accuracy", "Faithfulness", "Policy compliance", "Action success", "Context recall"], values: [17.86, 21.43, 46.43, 21.43, 21.43] },
      { name: "ResolveAI", labels: ["Answer accuracy", "Faithfulness", "Policy compliance", "Action success", "Context recall"], values: [96.43, 96.43, 85.71, 96.43, 96.43] },
    ], {
      x: 0.55, y: 2.24, w: 8.15, h: 4.25,
      catAxisLabelColor: C.ink, catAxisLabelFontSize: 11,
      valAxisLabelColor: C.gray, valAxisLabelFontSize: 9, valAxisMinVal: 0, valAxisMaxVal: 100,
      valGridLine: { color: "D8E2E4", width: 1 }, catGridLine: { style: "none" },
      chartColors: [C.gray, C.lime], showLegend: true, legendPos: "b", legendFontSize: 10,
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0\"%\"",
      showTitle: false, showCatName: false, showValAxisTitle: false, showCatAxisTitle: false,
      border: { color: C.line, width: 1 }, showBorder: true,
    });
    stat(s, "+0.5089", "paired mean quality delta", 9.0, 2.35, 3.45, C.lime);
    stat(s, "[0.4628, 0.5528]", "bootstrap 95% confidence interval", 9.0, 4.0, 3.45, C.aqua);
    pill(s, "Hallucination 78.57% → 3.57%", 9.0, 5.78, 3.45, C.pink);
    tx(s, "All values are proportions converted to percentages. Results do not establish production impact.", 9.0, 6.3, 3.4, 0.35, { fontSize: 9, bold: true, color: C.gray, align: "center", valign: "top" });
    addNotes(s, "State the sample size and synthetic limitation before quoting results. Explain the paired bootstrap interval and emphasize that the baseline is intentionally minimal.");
  }

  // 10 — honest limitations
  {
    const s = pptx.addSlide("CONTENT");
    title(s, "What the evidence does—and does not—show", "Credibility comes from making limitations visible", "The benchmark supports a controlled engineering claim, not a production ROI claim.");
    card(s, 0.62, 2.35, 5.95, 3.9, C.mint);
    tx(s, "Supported", 0.98, 2.72, 2.2, 0.4, { fontSize: 24, bold: true });
    row(s, 1, "Implemented workflow", "Auth, RAG, policy, approval, execution, audit, evaluation.", 0.98, 3.35, 5.0, C.lime);
    row(s, 2, "Controlled improvement", "+0.5089 paired quality delta on the fixed cases.", 0.98, 4.38, 5.0, C.aqua);
    row(s, 3, "Operational reliability", "71 backend tests; 13 Chromium tests; queues drained.", 0.98, 5.4, 5.0, C.white);
    card(s, 6.86, 2.35, 5.87, 3.9, C.pink);
    tx(s, "Not yet supported", 7.22, 2.72, 2.8, 0.4, { fontSize: 24, bold: true });
    row(s, 1, "Production effectiveness", "No real customer traffic or representative domain sample.", 7.22, 3.35, 4.95, C.white);
    row(s, 2, "Provider cost / latency", "Local deterministic timing; no billed model execution.", 7.22, 4.38, 4.95, C.orange);
    row(s, 3, "Human factors", "No reviewer agreement, fatigue, or trust study yet.", 7.22, 5.4, 4.95, C.lavender);
    pill(s, "KNOWN WEAKNESS: 15.38% BENIGN FALSE-POSITIVE RATE", 3.98, 6.52, 5.4, C.danger, C.white);
    addNotes(s, "Do not hide the false-positive rate. Present it as the next calibration target and evidence that the evaluation can reveal weaknesses.");
  }

  // 11 — future / conclusion
  {
    const s = pptx.addSlide();
    s.background = { color: C.ink };
    pill(s, "WHAT WE BUILT", 0.72, 0.65, 1.62, C.lime);
    tx(s, "ResolveAI makes agentic support\ninspectable, governable, and testable.", 0.72, 1.3, 7.25, 1.8, { fontSize: 30, bold: true, color: C.white, valign: "top" });
    tx(s, "A working local product + a reproducible research baseline + a clear path to external validation.", 0.72, 3.72, 6.7, 0.55, { fontSize: 16, color: "CAD6DA", valign: "top" });
    const future = [
      ["01", "Representative approved data"], ["02", "Strong model/agent baselines"],
      ["03", "Ablation + fault injection"], ["04", "Human reviewer study"],
    ];
    future.forEach(([n, text], i) => {
      const x = 0.72 + (i % 2) * 3.35, y = 4.65 + Math.floor(i / 2) * 0.85;
      slideDot(s, x, y + 0.08, i % 2 ? C.aqua : C.lime);
      tx(s, n, x + 0.34, y, 0.36, 0.24, { fontSize: 9, bold: true, color: C.lime });
      tx(s, text, x + 0.75, y - 0.02, 2.4, 0.3, { fontSize: 13, bold: true, color: C.white });
    });
    card(s, 8.22, 0.78, 4.45, 5.92, C.aqua);
    tx(s, "Demo route", 8.6, 1.2, 2.2, 0.38, { fontSize: 22, bold: true });
    const demo = ["Login", "Customer 360", "Resolve issue", "Approve action", "Inspect trace", "Show benchmark"];
    demo.forEach((item, i) => {
      const y = 1.95 + i * 0.7;
      slideDot(s, 8.62, y + 0.03, i === demo.length - 1 ? C.lime : C.white);
      tx(s, item, 9.02, y - 0.04, 2.85, 0.28, { fontSize: 14, bold: true });
      if (i < demo.length - 1) s.addShape(pptx.ShapeType.line, { x: 8.75, y: y + 0.28, w: 0, h: 0.42, line: { color: C.ink, width: 1.2, endArrowType: "triangle" } });
    });
    tx(s, "http://localhost:3000", 8.6, 6.15, 3.45, 0.25, { fontSize: 12, bold: true, align: "center" });
    tx(s, "Thank you", 0.72, 6.65, 2.5, 0.35, { fontSize: 20, bold: true, color: C.lime });
    addNotes(s, "Close with the main contribution and invite questions. If asked about impact, separate demonstrated system capability from future production outcomes.");
  }

  const testSlides = Number(process.env.RESOLVEAI_TEST_SLIDES || 0);
  const outputFile = testSlides
    ? path.join(ROOT, "artifacts", `ResolveAI_Faculty_Presentation-${testSlides}.pptx`)
    : OUT;
  if (testSlides) pptx._slides = pptx._slides.slice(0, testSlides);
  await pptx.writeFile({ fileName: outputFile });
  console.log(outputFile);
}

function slideDot(slide, x, y, fill) {
  slide.addShape(pptx.ShapeType.ellipse, { x, y, w: 0.2, h: 0.2, fill: { color: fill }, line: { color: C.ink, width: 0.7 } });
}

build().catch((error) => { console.error(error); process.exit(1); });

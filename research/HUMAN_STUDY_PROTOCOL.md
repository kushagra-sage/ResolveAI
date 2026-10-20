# ResolveAI blinded human-evaluation protocol

## Objective

Measure whether ResolveAI improves answer correctness, evidence usefulness, reviewer effort, and
operator trust relative to the baseline without exposing evaluators to system identity.

## Design

- Recruit at least 12 consenting adult participants familiar with support or operations work.
- Use a balanced, randomized comparison of 12 held-out cases per participant from a 24-case pool.
- Label systems A/B randomly per participant; do not reveal which is ResolveAI.
- Counterbalance case and system order to reduce learning and fatigue effects.
- Exclude real customer PII; use approved public or synthetic cases only.
- Record consent, full name, email, and a pseudonymous participant ID. Restrict access to the
  identifiable response workbook and remove name/email before analysis.

## Measures

For each response, collect 1–5 ratings for correctness, evidence support, action safety, clarity,
and trust; a binary approve/reject decision; decision time; and optional comments. Measure
inter-rater agreement, median decision time, approval accuracy, and paired rating differences with
confidence intervals. Report exclusions and missing responses.

## Stopping and safety

Participation is voluntary and may stop before submission. The form collects name and email only
for participation records and duplicate control. Do not collect phone numbers, customer data, or
free-text personal information. Store the identifiable workbook with restricted access, define a
deletion date, and use only de-identified exports for analysis. Institutional/faculty approval is
required before recruiting participants. This document is a protocol, not evidence that a study
has occurred.

## Artifacts

Use `research/human-study-template.csv`. Freeze the cases and analysis plan before collection,
retain raw responses access-controlled, and publish only aggregate results.

Running `python scripts/prepare_human_study.py` creates 144 counterbalanced assignments for 12
pseudonymous participants, with 12 cases per participant from a 24-case pool under
`research/human-study/`. Keep `blinding-key.csv`
separate from the evaluator-facing assignments and do not join it until collection closes.

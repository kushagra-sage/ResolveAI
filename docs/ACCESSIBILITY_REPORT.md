# Accessibility validation report

**Date:** 2026-10-06  
**Target:** WCAG 2.1 AA  
**Scope:** ResolveAI local React workspace; automated development validation, not certification

## Implemented controls

- Semantic `main`, navigation, section, table, form, heading, and dialog structures.
- Explicit labels for token, message, decision, and editable-action fields.
- A keyboard-visible “Skip to main content” link and visible `:focus-visible` treatment.
- Command navigation through Ctrl/Cmd+K and Escape.
- Reduced-motion CSS that disables nonessential animation and smooth scrolling when requested.
- Status content uses text as well as color; interactive controls retain visible borders.

## Automated results

The Playwright axe suite scans Overview, Resolution, Approvals, Evaluation, and CommerceOps
Anomalies with the `wcag2a`, `wcag2aa`, `wcag21a`, and `wcag21aa` tag sets. It fails on serious or
critical violations.

| Engine | Result | Evidence |
|---|---:|---|
| Chromium | 5/5 passed | Playwright HTML report and traces under `artifacts/` |
| WebKit | 5/5 passed | Final 90-second configuration; all five pages passed |
| Firefox | Not executed | Playwright Firefox download reproduced a Windows side-by-side loader error for the `mozglue` assembly before page launch |

The keyboard test passed in Chromium and WebKit. WebKit follows the macOS preference that omits
links from sequential Tab focus, so the test explicitly focuses and activates the skip link there;
Chromium verifies sequential Tab order.

## Limitations

Automated axe checks do not prove WCAG conformance. No independent accessibility audit, screen
reader matrix, magnification/zoom study, speech input test, cognitive walkthrough, or testing by
people with disabilities was performed. Firefox accessibility coverage remains blocked by the
local Playwright runtime loader. Production fonts, CSP, reverse proxy, embedded content, and any
future third-party widgets require renewed testing.

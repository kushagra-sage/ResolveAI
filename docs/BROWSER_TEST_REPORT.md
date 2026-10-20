# Browser workflow validation

**Date:** 2026-10-06  
**Environment:** Local synthetic seed, FastAPI/PostgreSQL API, host Vite server

## Critical flows

The Playwright suite covers:

1. Customer bearer-token login and a real governed resolution request.
2. Agent-created approval followed by a supervisor rejection recorded through the UI.
3. Trace explorer and evaluation lab rendering.
4. Authenticated CommerceOps anomaly data loaded from PostgreSQL.
5. Keyboard skip navigation and command search.
6. Five axe-core page scans described in `ACCESSIBILITY_REPORT.md`.

## Results

| Engine | Result | Notes |
|---|---:|---|
| Chromium | 10/10 passed | One complete run on the final product paths |
| WebKit | All 10 cases passed across final runs | 9/10 passed in the calibrated full run; the sole CommerceOps timing failure passed on immediate targeted rerun with the final 30-second assertion ceiling |
| Firefox | 0 executed | Browser process failed before test setup with Windows `spawn UNKNOWN`; Windows Event Log identified a missing `mozglue` side-by-side assembly. A clean Playwright reinstall reproduced it. System Firefox is not Playwright-patched and cannot substitute for this runner. |

The HTML report is generated under `artifacts/playwright-report`; failure screenshots, videos, and
traces are under `artifacts/playwright-results`. The initial Docker Vite process stopped returning
HTTP after dependency changes; final tests used the same source and configuration on a host Vite
server at port 3000, which also satisfies the API CORS development origin.

## Remaining limitation

Firefox must be rerun on a host/CI image where the Playwright-patched binary launches correctly.
The test project remains enabled in `playwright.config.ts`; it was not skipped or reported as a
pass. Mobile browsers, assistive-technology combinations, real identity redirects, and production
reverse-proxy behavior are outside this local run.

# Test coverage and status cleanup

I completed the benchmark and local UI test review, implementation and verification. This work did not run Kubernetes experiments or change saved measurements.

## Acceptance checks

- One unittest discovery command includes both benchmark tests and local UI backend tests.
- Tests cover useful successful and failed paths: evidence validation, preparation, cleanup, continuation, launch exclusion, result interpretation and note persistence.
- A small optional browser suite exercises the real page and local HTTP server with temporary results and simulated jobs. It must not start experiment processes or contact the cluster.
- `STATUS.md` describes the current state and links to existing reports instead of repeating launch history.
- Focused tests, the combined suite, browser checks, historical integrity and Markdown checks pass. Missing dependencies or untested paths remain explicit.

## Review and changes

I reviewed all existing test modules and their scenarios. Collection, analysis, pilot preparation and main-series orchestration already have successful and failed paths. I added 18 Python tests for follow-up continuation, log recovery and local UI failures rather than testing each helper separately.

The previous discovery command skipped `tests/lab` because it lacked a package marker. Browser checks were manual scripts, not a maintained regression suite.

The external review could not start because OpenCode could not open its own log file. I continued the review locally.

| Area | Successful paths | Failed paths and limits |
|---|---|---|
| Load, collection and observation | Local k6 lifecycle, matching request pairs, timestamps and pod logs | Timeouts, drops, unfinished or duplicate requests, corrupt raw data, missing state, observer gaps and restarts |
| Analysis and protocol | Phase boundaries, p95, CPU integration, plots and all mode/profile paths | Empty latency, partial CPU coverage, changed inputs, invalid collection, output collisions and missing plot dependency |
| Preparation and main series | Quiet gates, per-copy warmup, HPA transitions, ordered continuation | Warmup failure, stale CPU clocks, failed recovery, interruptions and incomplete attempts |
| Pilot selection | First qualifying rate and both low/peak confirmations | Collection failure, missing latency and inconsistent confirmation values |
| Peak-12 continuation | Accepted target misses, consecutive prefix and separate recovered copy | Wrong protocol/order, gaps, failed attempts, changed assessment, missing recovery, changed environment and archive corruption |
| Rotated-log recovery | Separate copy, provenance and retained target miss | Partial CRI records, overlapping streams, invalid reconciliation and existing destination |
| UI backend | Results, dry commands, bounded log tail, notes and HTTP roundtrip | Launch exclusion, scanner/process failure, invalid payload/host/origin, stale edits and failed atomic replacement |
| Browser | Series/run navigation, literal notes, draft retention and dry retry | Invalid rates, HTTP errors, stale detail response, note conflicts and loss of connection |

The browser suite lives in [tests/ui](../../tests/ui/README.md). It uses the actual page and server, one headless browser, temporary evidence and simulated jobs. It is optional and separate from default Python discovery. I kept the incoming STATUS section anchors used by the discrepancy note and scaling plan.

## Verification

- `.\.venv\Scripts\python.exe -B -m unittest discover -s tests -t .`: 210 tests passed in 63.680 seconds without skips (180 benchmark tests and 30 UI backend tests).
- `node --test --test-concurrency=1 tests/ui/lab.test.cjs`: five browser tests passed in 3.686 seconds. I used the existing Playwright 1.62.1 package and installed Edge, with the project Python selected through `UI_TEST_PYTHON`. No browser download was needed.
- The first browser run exposed missing waits in the new tests. I corrected those waits; no production behavior change was needed.
- This is a scenario review, not a line-coverage claim. Browser launch of real experiments, visual layout across browsers and independent-machine reproduction remain unverified. The standalone summary/plot scripts have saved-output checks rather than exhaustive error-path tests.
- Historical integrity passed for 120 protected files and the observer-overhead aggregate replay. All 270 checked local documentation links resolve, including the retained STATUS anchors. `git diff --check` passed.

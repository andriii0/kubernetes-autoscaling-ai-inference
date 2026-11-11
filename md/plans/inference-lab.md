# Inference Lab

## Objective

I maintain a local Windows browser UI for saved results and existing experiment commands. I keep English UI text, the existing evidence format and missing measurements. The active experiment procedure remains in `scaling-experiment.md`.

## Steps

1. Read saved metadata, collection checks, assessments, request events and plots. Group real series and runs into Pilots, Main series and Follow-up checks.
2. Build the three-column Results view, keyboard navigation and responsive preview.
3. Connect a single prepared fixed-one steady pilot and existing v1.1 continuation. Show settings, phase, run number and command output. Serialize UI jobs and detect external Windows experiment processes before live starts.
4. Verify with saved evidence, isolated tests and dry run. Capture a 1280 × 800 screenshot with a real run selected.

## Decisions and limits

I use Python's standard-library HTTP server on loopback and plain HTML/CSS/JavaScript. This adds no runtime dependency. The browser reads saved evidence; it does not replay collection on every refresh. A saved `running` field alone does not prove a live process. Reviewed interruptions and corrupt/partial files remain visible.

`bench/run_pilot.py` runs one experiment. The UI pilot preset is fixed one, steady, 2 requests/10 s, 120 seconds, one repetition, prepared quiet gates and a 5000-ms target. A small adapter owns the existing Service tunnel. Its dry run validates arguments without cluster access or result creation.

`bench/run_series.py` needs a completed prefix of a v1.1 series and matching archived executable hashes. I expose continuation and its real `--dry-run`; I do not imply it creates a new matrix. The minimal future extension is an explicit `--new-series` path in that driver, exclusive directory creation and the existing `matrix()`/`execute()` flow with its review/stop rules.

## Acceptance and verification

- Saved runs show profile, offered rate, scoped successful p95, successes, failures and timeouts. Unknown values stay null and render as an em dash.
- Target misses are amber; invalid collection and execution failures are red. Resource gaps alone do not override a valid collection check.
- Series show real attempts and completed counts. Historical/stale states are not presented as confirmed live activity.
- Existing results remain read-only during browsing/dry run. Live jobs use unique run paths and existing launchers/analyzers.
- Test saved peak versus whole-run p95, timeout counts, malformed/partial data, series grouping, path boundaries, single-job exclusion and dry-run commands.
- Check the rendered page at desktop and narrower sizes, keyboard focus, loading/error/empty states, and save a screenshot. Live cluster execution is outside this UI verification.

## Progress

### Result notes

I added a collapsible Notes editor to run and series previews. Notes use a separate UTF-8 `notes.md`, atomic replacement and revision checks against concurrent edits. The UI retains drafts during navigation and warns before closing with unsaved changes. I verified file round trips, conflict rejection, result path limits and unchanged metadata in tests. All 24 UI tests passed; Chromium checks against temporary results passed for HTTP save/reload, Unicode, literal HTML and draft preservation. No research notes were filled automatically.

### Runs tab and pilot settings

I added a separate Runs tab following the supplied two-card reference. The existing Results columns and preview stay intact. The shared header switches between Runs and Results, preserving the selected result.

1. Move launch entry points into Pilot run and Main series cards. Keep the real v1.1 continuation scope visible rather than implying a new nine-run HPA command.
2. Add a native modal dialog for pilot mode, profile, rate, low burst rate, steady duration and p95 target. Keep one repetition and the existing preparation gates. Support fixed modes and prepared HPA burst; burst duration comes from `bench/workload.json`.
3. Validate settings at the HTTP boundary and adapter, pass them to the existing launcher, and record the command in UI job logs. Preserve the existing result format.
4. Verify custom steady/burst dry runs, invalid settings, tab selection persistence, keyboard/modal behavior and responsive layouts. Capture Runs and the dialog. No live load is part of this change.

Acceptance: the supplied card layout is recognizable, Results retains its existing navigation and preview, and the displayed custom pilot settings match the generated command. Errors stay visible in the dialog. Closing it returns keyboard focus to the pilot card.

I verified the revision with 23 passing UI tests and custom fixed-three steady and HPA burst dry runs. Invalid HTTP pilot settings were rejected before process creation. No pilot result folders were created. Chromium checks passed for tab selection persistence, real Results peak p95, modal Escape/focus, rate validation, HPA profile constraints and the submitted custom command. Runs and the dialog fit widths 1280, 900, 640 and 480 px without horizontal overflow. Screenshots: [Runs](../assets/inference-lab-runs.png), [pilot settings](../assets/inference-lab-pilot.png). Live execution remains unverified.

- I completed the Results reader, three-column screen and launch adapters. The external peak-12 comparison continued separately during UI verification.

## Verification results

I verified this on Windows on 2026-11-10 using saved evidence and dry run:

- All 20 UI tests passed with `.venv\Scripts\python.exe -B -m unittest discover -s tests/lab -v`. They cover evidence interpretation, missing/corrupt data, timeout accounting, path boundaries, job exclusion, command dispatch, HTTP controls and closed browser connections.
- Pilot dry run passed through the CLI and browser. It validated the real launcher arguments and created no run folder.
- The real series dry run stopped with `Executable input changed: ...\bench\run_pilot.py`. This is the existing driver's archive guard against the current working-tree source, not a UI collection failure. I did not bypass it.
- Chromium checks passed for real series/run navigation, keyboard focus, saved/full plot opening, missing metrics, interruption, collection failures, target misses, and empty/error views. Widths 1280, 900, 800, 640 and 480 px had no horizontal overflow.
- A second server, including on another port, was rejected by the Windows lock.
- The [1280 × 800 screenshot](../assets/inference-lab.png) selects the real main `attempt-06-autoscaling-burst`. The preview labels primary peak p95 separately from the saved whole-run plot. Its source evidence remains in `results/main/series-2026-10-25-v1.1/`.

Browser automation used temporary, external Playwright tooling. The application has no new runtime package. Live cluster execution through the UI was not tested. Folder-opening dispatch was tested with a mock; the live Explorer window was not part of automated verification. A fresh series initializer remains the small proposed driver extension above. On server restart, earlier UI logs remain on disk; active external experiment processes are detected rather than reattached as UI jobs.

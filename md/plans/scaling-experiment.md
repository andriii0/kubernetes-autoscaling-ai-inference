# Scaling experiment procedure

Updated: 2026-10-21. Status: original step-18 preliminary check complete; protocol v1.1 agreed; step-20 code/instructions locally verified; step-21 main series not executed. This document keeps the future scaling and main-analysis procedure previously described in the getting started guide. It does not make this the active task or mark any milestone complete.

## Objective and prerequisites

Compare fixed capacity with automatic scaling on the existing local CPU setup. The [roadmap](../ROADMAP.md#18-test-three-manually-configured-replicas) owns milestones and the intended experiment matrix. [STATUS.md](../STATUS.md) names the active task. The [pilot plan](measurements-and-pilot.md) has saved results.

The [fixed replica preparation](fixed-replicas.md) may run a separately labelled preliminary check before the main protocol is agreed. It checks collection, warmup and traffic distribution; it does not complete the main comparison.

Before using this procedure for the main comparison:

1. Use the completed one-replica pilot recording/analysis and selected low/peak rates from [the saved report](../../results/pilot/discovery-2026-10-18-series1/README.md). Protocol v1.1 supplies the agreed targets and conditions; its implementation has local verification below.
2. Use the [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd), agreed by the student on 2026-10-21. It owns targets, windows, matrix, order and outcome/data rules. Roadmap steps 17 and 20 are complete as agreement and local implementation preparation; runtime readiness and approved execution remain separate.
3. Verify the current cluster, application image, model identity, Service URL and available resources. [Getting started](../GETTING_STARTED.md) owns setup and troubleshooting commands.
4. Follow the accepted choices in [DECISIONS.md](../DECISIONS.md). Source configuration stays in [deploy/ollama.yaml](../../deploy/ollama.yaml) and [bench/inference.js](../../bench/inference.js). Schema, units and collection limits stay in [OBSERVATION.md](../OBSERVATION.md).

All commands run in PowerShell from the project root. `$env:BASE_URL` must contain the current Service tunnel URL. The tunnel must remain open. Preserve raw evidence and give each run a new directory.

## 1. Manual replica comparison

Do this after the pilot has selected useful load rates. Remove only this workload's HPA if it exists, then request three replicas:

```powershell
kubectl --context ai-lab -n inference delete hpa ollama --ignore-not-found
kubectl --context ai-lab -n inference scale deployment/ollama --replicas=3
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
kubectl --context ai-lab -n inference get pods
```

Check that all three pods are running and ready. Ready confirms server availability, not model warmup.

The collector supports a separately labelled preliminary check with three fixed copies. Use the current Service URL, not a pod port-forward. Give every run a new path:

```powershell
python bench/run_pilot.py --base-url "$env:BASE_URL" --replicas 3 --rate 8 --duration 30s --run-dir results/fixed-replicas/NEW/service-check
python bench/run_pilot.py --base-url "$env:BASE_URL" --replicas 3 --rate 8 --duration 5m --run-dir results/fixed-replicas/NEW/peak-1
```

The first command must succeed before the longer check. The launcher requires three stable ready pods and no HPA. It checks Service endpoints, observes 60 seconds of idle state and sends the shared workload directly to each pod through the Kubernetes API proxy. `warmup.json` saves each pod's identity, Ready transition, first generation completion and model-load measurement. All initial warmups must succeed before k6 starts. These proxy/CLI timings are preparation records, not measured Service response times.

k6 uses the Service for measured traffic. After load, the collector saves native Ollama access logs for every pod. Generation completion counts must agree with client counts, and every pod must handle measured traffic. This proves aggregate distribution, not an individual request-to-pod mapping. Timeouts or other concurrent callers can prevent reconciliation; preserve that failed check and inspect it before continuing.

The [saved preliminary check](../../results/fixed-replicas/check-2026-10-20-series1/README.md) records one short distribution test and one five-minute peak test. It does not freeze the main protocol or establish a repeated scaling result. The existing source manifest defaults to one replica; applying it resets the manually scaled count. Server recovery still needs fresh resource observations before another independent probe if work may remain.

Use `bench/analyze.py` on the saved runs. Three-pod plots show each pod separately because kubelet source times differ. `per-replica-resources.json` contains individual resource summaries; missing or asynchronous samples are not replaced by zero or silently summed.

<a id="2-hpa-setup-and-checks"></a>

The HPA/review/publication/audit sections below preserve the 2026-10-20 execution context. Their statements about an unfinished protocol describe that date. The current agreement and step-20 plan follow those historical records. Saved result reports and inputs remain unchanged.

## 2. Preliminary HPA implementation and check

Completed preliminary check, approved and executed on 2026-10-20. This check may precede the frozen main protocol. It does not complete the repeated comparison.

- [x] Add autoscaling/v2 HPA for Ollama: 1-3 copies, CPU target 60%, downscale stabilization 300 seconds. Keep default scale-up behavior.
- [x] Extend the existing launcher with autoscaling mode and burst profile; keep fixed-mode commands and checks. Python and k6 share the burst stages: 120/1/300/1/360 seconds, low=2 and peak=8 requests/10 seconds (782 seconds total).
- [x] Reset to one copy without HPA (180-second limit), observe idle for 60 seconds and warm the initial model (120-second timeout). Apply HPA, require two consecutive numeric CPU/ScalingActive observations at one ready copy (300-second limit).
- [x] Track changing pod UIDs and their log streams from container startup through deletion. Preserve missing resource values, distinguish API errors from unavailable counters, and stop on collection failures, restarts or configuration drift. New copies are not warmed separately.
- [x] Reuse request reconciliation and analysis. Add HPA/pod timelines, phase-specific latency/error counts and per-pod resources. First HTTP response is not proof of first successful generation. Server/client counts need not match after a timeout.
- [x] Exercise dynamic transitions, missing first metrics, idle new pods, deleted logs, broken log streams/API, restarts, interruption, deadline consistency, false counters and no-scaling outcomes. Run all bench tests, historical integrity and diff checks before load.
- [x] Run one saved burst followed by client drain and a separately labelled 300-second period without new requests. Preserve partial failures. Stop log processes; remove HPA and restore one copy, saving recovery separately.
- [x] Save raw evidence, summary and charts; add a short simple-English HPA section to the existing Notion results page. Update setup/status and only mark observed behavior complete. No commits or push.

Acceptance: complete request accounting and explicit observation/log coverage; growth and reduction are assessed separately from data validity. Reaching three copies is not required. If no transition occurs, report that result without tuning this run. Existing historical evidence must remain unchanged. All copies share one host; this check cannot establish HPA benefit.

Configuration: [deploy/hpa.yaml](../../deploy/hpa.yaml). Source behavior: [Kubernetes HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/). Later main runs still require the agreed Notion protocol below.

Evidence: [saved preliminary run and verification](../../results/autoscaling/check-2026-10-20-series1/README.md). At the preliminary HPA review, all 79 tests passed. This is a historical result; the later repair verification is recorded below. The main protocol and matrix are still unfinished.

## Review fixes before the main protocol

Scope: make the current checks reproducible without changing saved measurements or selecting main-experiment targets.

- [x] Validate missing API state before reading it; report a missing Deployment explicitly.
- [x] Add an explicit positive `--slo-ms` option, pass it to k6 and save it in metadata. Keep ambient overrides blocked.
- [x] Separate CSV/JSON lifecycle checks from optional plot checks; skip only real k6 checks when its executable is unavailable. Use a precise test observer clock instead of depending on wall-clock resolution.
- [x] Correct stale HPA status text and explain the test environment and existing provisional thresholds.
- [x] Verify the suite with and without plot support, exercise negative cases, check historical hashes and review the diff. Keep the main protocol and repeated comparison unfinished.

Verification (2026-10-20T17:01:42+00:00, Windows, project `.venv`): Python 3.12.0, k6 2.2.0, Matplotlib 3.11.2. `python -m unittest discover -s bench` passed all 86 tests without skips. Before installing the already declared Matplotlib dependency, the suite passed with two plot checks skipped; with k6 also absent from PATH, 12 dependency-specific checks were skipped and the remaining checks passed. The dynamic HPA lifecycle test then passed five consecutive repetitions. These use local HTTP fixtures and simulated Kubernetes, not a new cluster experiment.

All 467 existing result files are byte-identical to the pre-fix snapshot. The historical verifier passed (120 protected files, saved aggregates and 184 local links); `git diff --check` passed. Current source corrections do not change archived run inputs or their original verdicts. No main latency target, commit or push is part of this repair.

Independent review (2026-10-20): source and test assertions were inspected separately from the earlier report. The project environment passed all 86 tests without skips. Fresh temporary Python environments passed with two skips without Matplotlib and 12 skips without Matplotlib and k6. The dynamic lifecycle test passed five further repetitions. Replaying the saved fixed-three and HPA runs with a duplicated observation in memory produced the strict timestamp error; unmodified runs remained valid. All 467 result files still matched the pre-fix hashes, and the historical verifier passed again. No functional defect or weakened check was found in this repair. Only stale descriptions of already implemented collection/analysis features were corrected; source code and tests were unchanged. The main protocol and repeated comparison remain unfinished.

## Publish the reviewed implementation and evidence

Scope: address the remaining review notes and publish the related fixed-three/HPA implementation, tests, documentation and saved results together. Do not change measurements, archived inputs or main-experiment targets.

- [x] Mark the 79-test result as historical and explain the two request-rate denominators in source and generated analysis notes.
- [x] Prepare one reviewed Git snapshot with both saved scaling series and all related implementation files. Keep missing required test data visible as a failure.
- [x] Verify a clean export of the Git index with the full bench suite and historical verifier. Compare all local result-file hashes with the pre-fix snapshot.
Verification: the clean Git export passed all 86 tests without skips, preserved 120 protected historical files and their aggregates, and resolved all 184 local links. All 467 local result paths are unchanged. Git contains 465 result files; the other two paths are ignored Python bytecode caches and stay local.

Publication procedure: create the commit, verify a clean clone, push it and compare the remote branch SHA. Report those final outcomes in the chat after they are verified.

The main protocol must agree the error, dropped-work and latency targets before the main series. Move the provisional error/dropped-work thresholds into shared configuration and verify that k6 uses those agreed values at that stage. This publication does not select targets or execute the main matrix.

## Fix audit findings F1-F3

Objective: reject contradictory log/latency evidence and analyze retained API failures without inventing state. Preserve saved results, archived inputs and the existing draft-protocol edits.

- [x] F1: detect a log stream that fails after its last update, distinguish requested termination from failure, and recheck exit evidence during replay. Test late failure, normal deletion, requested stop and contradictory saved coverage.
- [x] F2: reconcile request and successful-response latency sample counts/values against raw k6 points and trend summaries. Reuse the same percentile convention and document a numeric tolerance. Test contradictory events, raw points, summaries, empty success series and preserved historical runs.
- [x] F3: keep missing pod/HPA state as gaps in summaries, timelines and plots. Do not infer zero replicas or pod disappearance from a failed read. Test a mixed batch of valid and invalid runs, including plot generation.
- [x] Run focused tests, the full bench suite and historical integrity checks. Recompute saved summaries/timelines and compare all result hashes with the pre-fix snapshot. Record verified outcomes in Status.

Verification (2026-10-20): all 98 tests passed without skips in the project environment. Fresh environments passed with three plot checks skipped without Matplotlib and 13 dependency-specific checks skipped without k6 and Matplotlib. The new negative tests reject the old shutdown/replay, latency and missing-state implementations. All 13 saved event-based run verdicts/counts and successful-latency summaries are unchanged; saved fixed-three/HPA summaries, per-pod resources and scaling timelines match exactly. All 467 local result paths retain their pre-fix hashes. The excluded original pilot diagnostic remains excluded from the published series.

Historical documentation follow-up (2026-10-20): step 18 was expanded to require the agreed repeat/settings rules. The 2026-10-21 scope correction below restores its original preliminary-check criterion and assigns the repeated comparison to step 21. The two authoring-root integrity drafts are labelled as superseded recovery records. The maintained Notion result page was fetched again: its fixed-three/HPA sections already link the published c81c55c evidence and explain historical test counts, so no page rewrite was needed.

The fixed-three timeout/distribution rule remains a preliminary limitation. Agree how client failures, distribution coverage and server drain are represented across all modes in the main protocol before changing that rule. No live load, target selection, archive rewrite, commit or push is part of this repair.

## Protocol v1.0 agreement

Historical version-1.0 completion record. The current protocol is v1.1; the original agreement and verification below are retained.

Objective: record the student-approved step-17 agreement without changing executable code, historical measurements or archived inputs. The [main experiment protocol v1.0](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) owns the full numeric rules and rationale.

- [x] Save version 1.0 and the source baseline 389fb66 in Notion, retaining evidence/source links.
- [x] Carry forward the pilot settings and selected rates; distinguish the 5000-ms study assumption from observed performance.
- [x] Record profiles, primary phase/resource windows, quiet-state preparation, timeout/distribution rules, the 18-run order and retained system outcomes.
- [x] Update related current Markdown and link the agreement from existing Notion evidence pages. Keep steps 18/20/21 open at that time and historical result bytes unchanged.

Verification (2026-10-21): all four edited Notion pages were fetched again; the v1.0 rules and current-versus-historical wording were checked. The 13 changed files are Markdown only. The historical verifier passed (120 protected files, matching saved aggregates and 183 local links), git diff --check passed, and all 467 result paths remain byte-identical to the pre-edit snapshot. Bench code/configuration and archived inputs are unchanged, so the bench suite was not rerun for this documentation-only change. No live load, commit or push.

## Protocol v1.1 clarifications

Objective: address the independently reviewed preparation/resource/assessment gaps before main load. Preserve the earlier agreement, all saved evidence and the selected workload, targets, matrix and order. The [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) owns the exact rules. Affected main runs: 0. At that revision, step 17 was complete and steps 18/20/21 remained open.

- [x] Record post-warmup settling for all initial copies and a warmup-free metrics-server source window before HPA application.
- [x] Select estimated CPU core-seconds and observed peak memory per instance, with explicit interval boundaries, continuity and coverage rules.
- [x] Include the initial HPA reaction in both profiles and define the fixed run-assessment fields and combined verdict.
- [x] Require zero unfinished requests for full assessment; reuse the existing rejection rather than adding a duplicate validator.
- [x] Update related current Markdown and the existing Notion protocol/PDP references. Preserve historical version-1.0 records and the low-load overhead caveat.

Verification (2026-10-21): the protocol v1.1 and PDP update were fetched again; the five clarification areas, assessment fields, original v1.0 approval and zero affected main runs were confirmed. The incremental diff changes the same 13 Markdown files only. The historical verifier passed (120 protected files, matching saved aggregates and 183 local links); git diff --check passed. All 498 protected code/config/result paths, including all 467 result files, retain their pre-v1.1 hashes. No code changed, so the bench suite was not rerun for this documentation revision. No runtime load, commit or push.

## Restore the original step-18 scope

On 2026-10-21, restore step 18 to the preliminary three-copy check defined in the original roadmap (499b1a4). Commit 389fb66 had expanded its completion criterion to the repeated main comparison, creating overlap with step 21. The saved one-copy pilot and three-copy check already satisfy the original criterion: ready/warm initial copies, verified Service distribution and saved peak probes. The saved fixed-three service/peak runs and both one-copy peak confirmations were reconciled again and remain valid.

Step 18 is complete; step 20 remains complete as local implementation preparation; step 21 owns execution of the full repeated matrix and remains open. No extra step-18 runs are needed. This is a milestone-scope correction, not a change to protocol v1.1 settings, targets, repetitions or order. Saved result reports and archived inputs keep their original bytes and historical wording. Related current Markdown and Notion references are aligned.

Verification (2026-10-21): six current Markdown files changed. The saved fixed-three service/peak checks and both one-copy peak confirmations reconcile. All 500 protected code/config/result paths, including all 467 saved result files, retain their pre-edit hashes. The historical verifier passed (120 protected historical files, matching saved aggregates and 184 local links); git diff --check passed. The Notion protocol and PDP were fetched again and show the corrected milestone scope. No bench code changed, so the bench suite was not rerun for this documentation-only correction. No live load, commit or push.

## 3. Main run procedure

Step 20 preparation is complete with local verification. Reuse the existing launcher, reconciliation, analyzer, observer and workload. bench/main_protocol.py contains protocol-specific preparation and calculations; no separate collector, service or matrix orchestrator was added. Main runtime execution remains unapproved in this task.

### Implementation and verification

- [x] Support all fixed/autoscaling and steady/burst combinations.
- [x] Record protocol version, repetition, planned/actual order, replacement links/reasons, source commit/dirty state and executable input hashes.
- [x] Use shared error/drop/latency settings and assess the primary start-time phase. Reuse unfinished-request rejection; export the fixed assessment fields and sensitivity result.
- [x] Check remaining copies before switching mode. Prepare the initial count without a routine restart, wait for fresh low CPU, observe idle, warm initial copies and settle again. Before HPA, check the entire metrics-server window too.
- [x] Retain fixed-mode traffic separately from client counts/statuses after timeouts; preserve system failures and partial attempts.
- [x] Estimate per-instance CPU core-seconds on the common scheduled window, with continuity/clipping/coverage and separate observed memory/node values. Keep historical client-drain summaries.
- [x] Supply the manual order and single-run instructions below for the main series in step 21. Step 18 is the completed preliminary check.
- [x] All 122 bench tests passed without skips on 2026-10-21. New tests cover six mode/profile paths using real k6/local HTTP, preparation gates, target failures, incomplete attempts and resource calculations. Kubernetes interactions are simulated; preparation gates have separate direct tests. All 467 saved result paths are byte-identical; 11 saved summaries and the HPA phase/timeline replay match. The historical verifier passed (120 protected files, matching saved aggregates and 183 local links); git diff --check passed. The Notion protocol/PDP updates were fetched again. No cluster load, commit or push.

### Before runtime work

Confirm the current Docker/Minikube state and Service tunnel, inspect actual resources/image/model identity, and ensure no other project k6/observer process is running. Record unrelated heavy activity. Review Git changes: metadata records HEAD, dirty state and exact archived input hashes; HEAD alone does not identify uncommitted executable content. Keep the reviewed executable inputs fixed across the series.

Use a new parent series path and a new attempt path each time. Do not pre-create the attempt folder. Do not run the old preliminary mode-switch commands before main mode: the launcher first checks quiet remaining copies, then removes only this workload's HPA and selects one or three initial copies. It refuses a conflicting HPA. No rollout restart is required. Preparation failure stops before k6 and retains the attempt.

Initial models receive separate warmup. Both HPA profiles then apply HPA and verify two numeric, ScalingActive observations at one copy. New HPA copies load during measurement. The launcher keeps observation through scheduled end even if k6 exits after its last scheduled request slightly early. Client completion, the full scheduled window and later observation remain separate. Fixed modes keep 10 seconds after the scheduled/client window; HPA keeps 300 seconds, then restores one copy and removes HPA.

### Manual matrix checklist

No row below has been executed. Mark an attempt only after reviewing its assessment and evidence; record failures too. Actual order counts every attempt, including interruptions/replacements. Keep the planned order of the matrix cell when an attempt replaces it.

| Planned order | Repetition | Mode | Profile | Reviewed attempt path / outcome |
|---|---|---|---|---|
| 1 | 1 | fixed-1 | steady | [ ] |
| 2 | 1 | fixed-3 | steady | [ ] |
| 3 | 1 | autoscaling | steady | [ ] |
| 4 | 1 | fixed-1 | burst | [ ] |
| 5 | 1 | fixed-3 | burst | [ ] |
| 6 | 1 | autoscaling | burst | [ ] |
| 7 | 2 | fixed-3 | burst | [ ] |
| 8 | 2 | autoscaling | burst | [ ] |
| 9 | 2 | fixed-1 | burst | [ ] |
| 10 | 2 | fixed-3 | steady | [ ] |
| 11 | 2 | autoscaling | steady | [ ] |
| 12 | 2 | fixed-1 | steady | [ ] |
| 13 | 3 | autoscaling | steady | [ ] |
| 14 | 3 | fixed-1 | steady | [ ] |
| 15 | 3 | fixed-3 | steady | [ ] |
| 16 | 3 | autoscaling | burst | [ ] |
| 17 | 3 | fixed-1 | burst | [ ] |
| 18 | 3 | fixed-3 | burst | [ ] |

### Run one approved attempt

Read one row of the checklist and set its fields. This command runs only that attempt; it is not a loop. Keep the Service tunnel open. Omit --duration and --slo-ms: main settings come from the shared protocol configuration. Rates are requests per ten seconds.

```powershell
$mode = Read-Host 'Mode from the checklist'
$profile = Read-Host 'Profile from the checklist'
$repetition = [int](Read-Host 'Repetition from the checklist')
$plannedOrder = [int](Read-Host 'Planned order from the checklist')
$actualOrder = [int](Read-Host 'Actual attempt number, including failed attempts')
$runDir = Read-Host 'New attempt path under results/main/NEW-SERIES'
$activity = Read-Host 'Other heavy activity, or none observed'
.\.venv\Scripts\python.exe -B bench/run_pilot.py --protocol-version 1.1 --mode "$mode" --profile "$profile" --rate 8 --repetition $repetition --planned-order $plannedOrder --actual-order $actualOrder --activity-note "$activity" --base-url "$env:BASE_URL" --run-dir "$runDir"
```

For a justified replacement, use a new path and actual attempt number, retain the same planned cell and add --replaces-run OLD-PATH-OR-ID --replacement-reason "Reason". Never overwrite or erase the original. Do not replace a run merely because latency, errors or scaling behavior are unfavorable.

Inspect metadata.json, collection-check.json and assessment.json after every attempt. Exit 99 means a k6 threshold failed; it can still be valid measurement evidence. overall not_assessable requires reviewing missing data, duration, drops or traffic evidence; it is not a successful repetition. Server-drain verification stays separate. Stop for a preparation/collection problem and inspect before another attempt.

For analysis, choose a new output directory:

```powershell
$analysisDir = Read-Host 'New analysis output path'
.\.venv\Scripts\python.exe -B bench/analyze.py "$runDir" --output-dir "$analysisDir" --no-plots
```

assessments.json contains the fixed verdict fields and phase counts; primary-resources.json contains scheduled-window interval estimates and coverage. Existing summary.csv, per-replica-resources.json and plots retain their documented historical/client-drain meanings. Full application CPU stays unavailable without full expected-instance coverage; per-instance memory peaks are never summed as an application peak. Main-series cross-repetition findings remain step 22/23 work.

## 4. Main result analysis

This section covers the remaining main-series comparison and presentation. Existing per-run analysis now also exports protocol assessment and scheduled-window resource estimates for main attempts. Combining actual repetitions and writing comparative findings remain future work. The [pilot plan](measurements-and-pilot.md#5-pilot-output-and-decisions) owns the first whole-run summaries and rate selection; extend that work for the main matrix rather than building a separate analyzer.

### Read request and cluster records

Read JSONL one record at a time. Keep k6 records with `type == "Point"`; use `successful_latency_ms` for successful full-response latency and `inference_errors` for response outcomes. Report completed, failed and dropped work separately, with actual run duration and created load. Keep optional metric availability visible; missing token/load fields are not zeros.

Read `cluster.jsonl` for state and resource observations. A counted Ready pod must have `Ready=True` in `status.conditions` and no `deletionTimestamp`. Ready does not prove that a model has completed generation; keep those timelines distinct.

Use UTC for alignment. Protocol v1.1 assigns requests by start time: steady uses the full run, burst uses the full peak including initial HPA reaction. Later completions remain in their start phase. Report the primary 5000-ms criterion, predefined 10000-ms sensitivity check and whole-run context with sample counts. Do not invent short-window p95 values from sparse samples.

### Use the selected resource source

The primary resource window is scenario start through scheduled end (300 seconds steady or 782 seconds burst), common across modes. Show client-drain and post-load periods separately; primary-resources.json now exports this window separately from historical summaries.

Use `resource_usage` for normalized direct kubelet observations. Preserve the raw `kubelet` series for checking calculations. Keep `resources` (metrics-server) separate to explain the HPA input; do not substitute it when direct resource data is missing. The schema and units are defined in [OBSERVATION.md](../OBSERVATION.md).

For the primary quantities, select `scope == "container"`, `namespace == "inference"` and `container == "ollama"`. Estimate CPU core-seconds from valid per-instance source-counter intervals, clipping only at the primary boundaries as specified in Notion v1.1. Report covered seconds and active-window coverage; never bridge resets, identity changes or missing samples. A full application CPU total may sum these independently accumulated quantities only with complete coverage of every expected instance. Otherwise retain per-instance covered quantities and leave the full total unavailable.

Use maximum observed working-set MiB per instance with coverage for memory. Do not sum per-instance peaks as an application peak. Instantaneous totals still require complete samples from the same source instant. Show node CPU/memory separately so the application is not counted twice. CPU-seconds per successful request is outside the required scope.

Preserve nulls, counter resets, errors and gaps. If an expected container lacks a metric, label the total incomplete instead of presenting the other containers as the whole application. Check CPU and memory coverage independently.

Respect `cpu_timestamp_ms`, `memory_timestamp_ms` and `cpu_clock`; repeated collection does not guarantee a new source sample. Use `pod_uid`, `restart_count` and `container_start_time_seconds` to avoid joining counters from different instances. These readings cover the selected containers and Minikube node, not Windows-wide energy or monetary savings.

### Produce tables, charts and findings

Write one summary row per run to CSV and use it in the main findings document in Notion. Include mode, profile, repeat, successful-response p95, response errors, completed/unfinished/dropped requests, Ready replica counts, selected resource quantities/coverage and the v1.1 assessment fields. Use not_assessable for incomplete data/duration/offered load; otherwise any failed service target means fail, all three passing means pass, and a remaining unknown means not_assessable. Scaling transitions and resource coverage remain separate observations. Raw files remain the source for checking summary values; console output alone is not enough.

Produce aligned plots for response latency and its agreed target, Ready replicas, and application CPU/memory. Mark load growth, decline, model startup and the measured interval. Reuse the existing CSV/JSON and plot generation; add only the agreed windows and fields needed for the main comparison.

Show each repetition and its variation. Mixed assessable pass/fail repetitions mean inconsistent target attainment; not_assessable repetitions mean incomplete evidence and must also be shown; preserve system failures and do not add repeats just to obtain a favorable result. Do not average run p95 values and call that an overall p95. If needed, recalculate a pooled percentile from the raw response samples and explain its meaning. Check the latency target together with the error target: timed-out slow requests disappearing from successful latency are not evidence of improvement.

The findings should answer when one replica exceeded the target, what changed with fixed extra capacity, how long scaling took, when targets were missed, how scale-down behaved, and what resource use accompanied each outcome. Report insufficient evidence when needed. Use the [research document's existing evaluation sections](../../docs/README.md) for the research update.

## Acceptance and verification

- The pilot and numeric protocol are complete before the main comparison. Current configuration and actual load are recorded for every run.
- Manual replica checks confirm placement, warmup and request distribution. HPA checks confirm real input metrics and explain the observed scaling behavior, including failures.
- Every run has its own directory, retains failed/partial evidence, and reconciles raw data with reported totals. Missing data is explicit.
- Tables and plots can be rebuilt from the raw files. Per-run results, source timings, coverage and limits remain visible.
- Use offline fixtures and focused checks while implementing recording/analysis. Run live load tests only when the active task calls for them; document their actual environment and results.

No scaling result, capacity claim or HPA benefit has been established by writing this plan. All replicas share the same computer, and adding replicas also changes the total allowed CPU budget. Follow the accepted [decisions and limits](../DECISIONS.md) when interpreting results.

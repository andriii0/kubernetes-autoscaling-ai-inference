# Scaling experiment procedure

Updated: 2026-10-20. Status: preliminary HPA check completed; main series not executed. This document keeps the future scaling and main-analysis procedure previously described in the getting started guide. It does not make this the active task or mark any milestone complete.

## Objective and prerequisites

Compare fixed capacity with automatic scaling on the existing local CPU setup. The [roadmap](../ROADMAP.md#18-test-three-manually-configured-replicas) owns milestones and the intended experiment matrix. [STATUS.md](../STATUS.md) names the active task. The [pilot plan](measurements-and-pilot.md) has saved results.

The [fixed replica preparation](fixed-replicas.md) may run a separately labelled preliminary check before the main protocol is agreed. It checks collection, warmup and traffic distribution; it does not complete the main comparison.

Before using this procedure for the main comparison:

1. Use the completed one-replica pilot recording/analysis and selected low/peak rates from [the saved report](../../results/pilot/discovery-2026-10-18-series1/README.md). The response-time target and frozen main protocol remain prerequisites.
2. Review and agree the separate [draft experiment protocol](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) in Notion. Draft 0.1 is a private discussion draft, not a frozen protocol. Final settings, latency/error targets and their measurement windows, matrix, repeat order and invalid-run rules remain open. Keep these execution instructions consistent with the agreed version before the main series.
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

Documentation follow-up: roadmap step 18 now explicitly requires the agreed repeat/settings rules, so preliminary probes alone cannot close it. The two authoring-root integrity drafts are labelled as superseded recovery records. The maintained Notion result page was fetched again: its fixed-three/HPA sections already link the published c81c55c evidence and explain historical test counts, so no page rewrite was needed.

The fixed-three timeout/distribution rule remains a preliminary limitation. Agree how client failures, distribution coverage and server drain are represented across all modes in the main protocol before changing that rule. No live load, target selection, archive rewrite, commit or push is part of this repair.

## 3. Main run procedure

Use the frozen protocol for actual rates, targets, durations and repeat order. Do not use the command examples below as a substitute for that protocol or complete run orchestration. The observer, load script and one-replica pilot metadata/events are implemented. `bench/run_pilot.py` supports steady/burst profiles, fixed one or three copies, and one preliminary autoscaling run. It records mode/profile settings, fixed-replica warmups and pod timing records, but accepts autoscaling only with burst. It does not execute or validate the repeated main matrix. Before the main series, record repeat identity and the agreed protocol version, verify every agreed mode/profile combination, and agree the initial-state and startup-timing rules. The command blocks below remain manual reference examples.

### Select and reset the mode

Switch modes between runs, not during a measured interval. Use `fixed-1`, `fixed-3` or `autoscaling` as the result label, and `steady` or `burst` as the load profile.

For fixed one replica:

```powershell
kubectl --context ai-lab -n inference delete hpa ollama --ignore-not-found
kubectl --context ai-lab -n inference scale deployment/ollama --replicas=1
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
```

For fixed three replicas:

```powershell
kubectl --context ai-lab -n inference delete hpa ollama --ignore-not-found
kubectl --context ai-lab -n inference scale deployment/ollama --replicas=3
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
```

For automatic scaling, use the fixed-one reset above first. Apply HPA only after initial warmup, immediately before recording the run. Removing and recreating this HPA resets its previous recommendation history.

Check that only the intended initial replicas remain and no pods are still `Terminating`. For a clean start, restart the workload without HPA:

```powershell
kubectl --context ai-lab -n inference rollout restart deployment/ollama
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
```

Warm and verify every initial replica as in section 1, then let outstanding work finish. Exclude initial warmup from measurement. In automatic mode, loading a model in a new replica during the run remains part of the scaling reaction, as defined by the [readiness decision](../DECISIONS.md#10-distinguish-server-readiness-from-a-warm-model). Record Ready transitions separately from first successful generation.

### Create a new run directory

Run this block once for each run. If directory creation fails, stop; do not continue with an existing directory.

```powershell
$mode = 'fixed-1'
$profile = 'burst'
$runDir = Join-Path 'results' ("{0}-{1}-{2}-{3}" -f $mode, $profile, [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'), [Guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $runDir -ErrorAction Stop | Out-Null
$env:LOW_RATE = Read-Host 'Low rate from the frozen protocol: requests per 10 seconds'
$env:RATE = Read-Host 'Peak rate from the frozen protocol: requests per 10 seconds'
$env:SLO_MS = Read-Host 'Frozen p95 limit in milliseconds'
```

`$mode` only labels results. The actual mode is set by the Kubernetes commands above. Changing the label does not change the cluster.

### Record configuration and start observation

Record the selected settings and actual deployed configuration. The previous guide's `settings.json` example was not complete metadata. The [pilot plan's saved-run format](measurements-and-pilot.md#2-saved-run-format) defines the required evidence; main runs also need their mode, profile and repeat identity.

As a starting record, save tool versions, image/model identity and configuration:

```powershell
@{
    mode = $mode
    profile = $profile
    base_url = $env:BASE_URL
    low_rate_per_10s = [int]$env:LOW_RATE
    peak_rate_per_10s = [int]$env:RATE
    p95_limit_ms = [int]$env:SLO_MS
} | ConvertTo-Json | Set-Content -Encoding utf8 "$runDir\settings.json"
Copy-Item -LiteralPath .\bench\inference.js -Destination "$runDir\inference.js"
Copy-Item -LiteralPath .\bench\observe.py -Destination "$runDir\observe.py"
minikube version | Set-Content -Encoding utf8 "$runDir\minikube-version.txt"
kubectl --context ai-lab version -o json | Set-Content -Encoding utf8 "$runDir\kubernetes-version.json"
k6 version | Set-Content -Encoding utf8 "$runDir\k6-version.txt"
docker image inspect ai-inference:0.1 | Set-Content -Encoding utf8 "$runDir\image.json"
kubectl --context ai-lab -n inference exec deployment/ollama -- ollama list | Set-Content -Encoding utf8 "$runDir\model-version.txt"
```

The copied load script retains the actual payload, scenario and threshold definitions instead of repeating them in this plan. Complete run metadata must also preserve hashes, resource/node settings, warmup records, process exit codes and before/after snapshots. A failed configuration read must be recorded and inspected; do not continue as if all evidence was captured.

For `autoscaling`, apply the reviewed HPA configuration now and verify numeric metrics and one initial replica. Skip this block for fixed modes:

```powershell
kubectl --context ai-lab apply -f .\deploy\hpa.yaml
kubectl --context ai-lab -n inference get hpa
```

Save the resulting configuration and print the run path:

```powershell
kubectl --context ai-lab -n inference get deployment,service,hpa -o yaml | Set-Content -Encoding utf8 "$runDir\cluster-config.yaml"
$runDir
```

In an observation window, enter the printed run path and start the observer:

```powershell
Set-Location 'C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference'
$observationDir = Read-Host 'Current run directory'
python .\bench\observe.py "$observationDir\cluster.jsonl"
```

The observer refuses an existing output file. Start collection before the measured interval and keep it running through the last response. Record its actual start/end times and exit code through the planned run orchestration.

### Collect the measured interval

In the first window, record the interval and run k6 once in the new directory:

```powershell
(Get-Date).ToUniversalTime().ToString('o') | Set-Content -Encoding utf8 "$runDir\started-at.txt"
k6 run --no-usage-report -e "PROFILE=$profile" --out "json=$runDir/requests.json" --summary-export "$runDir/summary.json" .\bench\inference.js 2>&1 | Tee-Object -FilePath "$runDir\console.txt"
$LASTEXITCODE | Set-Content -Encoding ascii "$runDir\exit-code.txt"
(Get-Date).ToUniversalTime().ToString('o') | Set-Content -Encoding utf8 "$runDir\ended-at.txt"
```

Do not repeat the k6 command in the same directory: k6 itself can overwrite its output files. The complete runner must enforce exclusive run creation and preserve failures. This is a remaining implementation requirement, not a feature supplied by these individual command blocks.

Let observation capture the final state, then stop it with `Ctrl+C`. Mark any extra idle observation after the measured interval separately. Use the actual schedule in the saved load script; allow extra time for outstanding requests to finish.

Execute the reviewed matrix from the [roadmap](../ROADMAP.md#20-prepare-the-main-experiment-matrix-and-run-procedure) and frozen protocol. Keep model/request settings, resource limits and load profiles comparable, and vary run order as planned. Avoid other heavy work on the computer.

Keep failed and partial runs with an explanation. If k6 drops scheduled work, do not report that run as if the full requested load was created. Fix generator capacity during the pilot or revise the protocol for the entire affected comparison. Response threshold failures and invalid measurement processes are different outcomes.

Source: [k6 raw JSON output](https://grafana.com/docs/k6/latest/results-output/real-time/json/).

## 4. Main result analysis

This section is the implementation plan for later main-series analysis. `bench/analyze.py` implements preliminary fixed-one/fixed-three analysis and one autoscaling timeline. The repeated main-series comparison remains future work. The [pilot plan](measurements-and-pilot.md#5-pilot-output-and-decisions) owns the first whole-run summaries and rate selection; extend that work for the main matrix rather than building a separate analyzer.

### Read request and cluster records

Read JSONL one record at a time. Keep k6 records with `type == "Point"`; use `successful_latency_ms` for successful full-response latency and `inference_errors` for response outcomes. Report completed, failed and dropped work separately, with actual run duration and created load. Keep optional metric availability visible; missing token/load fields are not zeros.

Read `cluster.jsonl` for state and resource observations. A counted Ready pod must have `Ready=True` in `status.conditions` and no `deletionTimestamp`. Ready does not prove that a model has completed generation; keep those timelines distinct.

Use UTC for alignment. A 30-second display window was the initial main-series suggestion, not a frozen protocol setting. Confirm adequate sample counts during the pilot. Use whole-run percentiles and individual response points when there are too few requests for stable windowed percentiles.

### Use the selected resource source

Use `resource_usage` for normalized direct kubelet observations. Preserve the raw `kubelet` series for checking calculations. Keep `resources` (metrics-server) separate to explain the HPA input; do not substitute it when direct resource data is missing. The schema and units are defined in [OBSERVATION.md](../OBSERVATION.md).

For application totals, select `scope == "container"`, `namespace == "inference"` and `container == "ollama"`. Only sum a complete set of container values from the same source instant. Otherwise show each pod separately and leave the application total missing. Convert bytes to MiB only for display. Show `scope == "node"` separately so the application is not counted twice.

Preserve nulls, counter resets, errors and gaps. If an expected container lacks a metric, label the total incomplete instead of presenting the other containers as the whole application. Check CPU and memory coverage independently.

Respect `cpu_timestamp_ms`, `memory_timestamp_ms` and `cpu_clock`; repeated collection does not guarantee a new source sample. Use `pod_uid`, `restart_count` and `container_start_time_seconds` to avoid joining counters from different instances. These readings cover the selected containers and Minikube node, not Windows-wide energy or monetary savings.

### Produce tables, charts and findings

Write one summary row per run to CSV and use it in the main findings document in Notion. Include mode, profile, repeat, successful-response p95, response errors, completed and dropped requests, Ready replica counts, resource use and coverage. Raw files remain the source for checking summary values; console output alone is not enough.

Produce aligned plots for response latency and its agreed target, Ready replicas, and application CPU/memory. Mark load growth, decline, model startup and the measured interval. The first version can use CSV and externally created charts before plot generation is automated.

Show each repetition and its variation. Do not average run p95 values and call that an overall p95. If needed, recalculate a pooled percentile from the raw response samples and explain its meaning. Check the latency target together with the error target: timed-out slow requests disappearing from successful latency are not evidence of improvement.

The findings should answer when one replica exceeded the target, what changed with fixed extra capacity, how long scaling took, when targets were missed, how scale-down behaved, and what resource use accompanied each outcome. Report insufficient evidence when needed. Use the [research document's existing evaluation sections](../../docs/README.md) for the research update.

## Acceptance and verification

- The pilot and numeric protocol are complete before the main comparison. Current configuration and actual load are recorded for every run.
- Manual replica checks confirm placement, warmup and request distribution. HPA checks confirm real input metrics and explain the observed scaling behavior, including failures.
- Every run has its own directory, retains failed/partial evidence, and reconciles raw data with reported totals. Missing data is explicit.
- Tables and plots can be rebuilt from the raw files. Per-run results, source timings, coverage and limits remain visible.
- Use offline fixtures and focused checks while implementing recording/analysis. Run live load tests only when the active task calls for them; document their actual environment and results.

No scaling result, capacity claim or HPA benefit has been established by writing this plan. All replicas share the same computer, and adding replicas also changes the total allowed CPU budget. Follow the accepted [decisions and limits](../DECISIONS.md) when interpreting results.

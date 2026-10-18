# Scaling experiment procedure

Updated: 2026-10-19. Status: planned, not executed. This document keeps the future scaling and main-analysis procedure previously described in the getting started guide. It does not make this the active task or mark any milestone complete.

## Objective and prerequisites

Compare fixed capacity with automatic scaling on the existing local CPU setup. The [roadmap](../ROADMAP.md#18-test-three-manually-configured-replicas) owns milestones and the intended experiment matrix. [STATUS.md](../STATUS.md) names the active task; finish the [pilot plan](measurements-and-pilot.md) first.

Before using this procedure:

1. Use the completed one-replica pilot recording/analysis and selected low/peak rates from [the saved report](../../results/pilot/discovery-2026-10-18-series1/README.md). The response-time target and frozen main protocol remain prerequisites.
2. Create and review `md/plans/experiment-protocol.md` with the final settings, matrix, repeat order and invalid-run rules. This file is a required future output; it does not exist yet. Once approved, it owns the frozen numeric protocol; keep this procedure consistent with it.
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

Send a separate warmup load. The following is a starting warmup command; verify every initial replica rather than assuming a fixed duration is enough:

```powershell
k6 run --no-usage-report -e PROFILE=steady -e RATE=5 -e DURATION=1m .\bench\inference.js
$pods = (kubectl --context ai-lab -n inference get pods -l app=ollama -o json | ConvertFrom-Json).items
foreach ($pod in $pods) {
    $pod.metadata.name
    kubectl --context ai-lab -n inference exec $pod.metadata.name -- ollama ps
}
```

Start with no inherited `SLO_MS` threshold during warmup, or remove it from that PowerShell session. Warmup is not a measured run. Confirm CPU execution and a loaded model in every initial replica, and confirm a successful generation from each one. `ollama ps` alone is not a request log. The pilot already records correlated requests. Per-replica request attribution and first-generation timing still need implementation for this comparison.

If a replica has not received a request, continue warmup and verify traffic distribution. Use `kubectl --context ai-lab -n inference top pods` as an operational check; final resource accounting follows the observation schema.

Repeat the selected peak probe with the same recorded settings and a fresh results directory. A performance gain is an outcome to measure. If there is no gain, inspect traffic distribution, actual output lengths and shared CPU/memory pressure before drawing conclusions.

## 2. HPA setup and checks

HPA is not implemented yet. The following is the starting proposal for a future `deploy/hpa.yaml`, carried over from the guide. The CPU target and scale-down window are provisional. Review them before the main series; they are not measured optima. When the real file is added, make it the configuration source and replace this proposal with a link.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ollama
  namespace: inference
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ollama
  minReplicas: 1
  maxReplicas: 3
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
```

The percentage refers to `requests.cpu`, not the whole computer. Read the workload's current request from its Deployment. The scale-down window reduces rapid changes in replica count; unfinished requests may delay the return to a lower count.

For the first check, reset to one replica without HPA, complete initial warmup as in section 1, and drain outstanding work. Then apply the reviewed file:

```powershell
kubectl --context ai-lab apply -f .\deploy\hpa.yaml
kubectl --context ai-lab -n inference get hpa
```

Use the reset commands in section 3. Verify a numeric CPU reading and the intended initial replica count before measuring. Watch scaling in another window:

```powershell
kubectl --context ai-lab -n inference get hpa --watch
```

Run a separately saved burst probe using the pilot-selected rates. [bench/inference.js](../../bench/inference.js) owns the actual burst schedule. Observe growth and decline in replica count, request outcomes and model loading. Scaling takes time to read metrics, decide, start a container and load a model.

If `TARGETS` stays `<unknown>`, fix the missing metric before treating the run as autoscaling evidence. If necessary, continue a separately marked observation period after requests stop to check scale-down.

Source: [Kubernetes HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/).

## 3. Main run procedure

Use the frozen protocol for actual rates, targets, durations and repeat order. Do not use the command examples below as a substitute for that protocol or complete run orchestration. The observer, load script and one-replica pilot metadata/events are implemented. `bench/run_pilot.py` intentionally accepts one replica and constant-rate pilot probes only; it is not a launcher for this matrix. Extend orchestration for mode/profile/repeat metadata, per-replica preparation and first-generation timing before using the following planned command blocks.

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

This section is the implementation plan for later main-series analysis. `bench/analyze.py` implements one-replica pilot analysis; multi-replica aggregation and scaling timelines remain future extensions. The [pilot plan](measurements-and-pilot.md#5-pilot-output-and-decisions) owns the first whole-run summaries and rate selection; extend that work for the main matrix rather than building a separate analyzer.

### Read request and cluster records

Read JSONL one record at a time. Keep k6 records with `type == "Point"`; use `successful_latency_ms` for successful full-response latency and `inference_errors` for response outcomes. Report completed, failed and dropped work separately, with actual run duration and created load. Keep optional metric availability visible; missing token/load fields are not zeros.

Read `cluster.jsonl` for state and resource observations. A counted Ready pod must have `Ready=True` in `status.conditions` and no `deletionTimestamp`. Ready does not prove that a model has completed generation; keep those timelines distinct.

Use UTC for alignment. A 30-second display window was the initial main-series suggestion, not a frozen protocol setting. Confirm adequate sample counts during the pilot. Use whole-run percentiles and individual response points when there are too few requests for stable windowed percentiles.

### Use the selected resource source

Use `resource_usage` for normalized direct kubelet observations. Preserve the raw `kubelet` series for checking calculations. Keep `resources` (metrics-server) separate to explain the HPA input; do not substitute it when direct resource data is missing. The schema and units are defined in [OBSERVATION.md](../OBSERVATION.md).

For application totals, select `scope == "container"`, `namespace == "inference"` and `container == "ollama"`. Sum valid `cpu_cores` values and sum `memory_working_set_bytes`; convert bytes to MiB only for display. Show `scope == "node"` separately so the application is not counted twice.

Preserve nulls, counter resets, errors and gaps. If an expected container lacks a metric, label the total incomplete instead of presenting the other containers as the whole application. Check CPU and memory coverage independently.

Respect `cpu_timestamp_ms`, `memory_timestamp_ms` and `cpu_clock`; repeated collection does not guarantee a new source sample. Use `pod_uid`, `restart_count` and `container_start_time_seconds` to avoid joining counters from different instances. These readings cover the selected containers and Minikube node, not Windows-wide energy or monetary savings.

### Produce tables, charts and findings

Write one summary row per run to CSV and use it in the planned `report/results.md`. Include mode, profile, repeat, successful-response p95, response errors, completed and dropped requests, Ready replica counts, resource use and coverage. Raw files remain the source for checking summary values; console output alone is not enough.

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

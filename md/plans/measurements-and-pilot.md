# Measurements and pilot load tests

Updated: 2026-10-18. Request/run collection is implemented and has a saved live low-load check. Pilot analysis and rate selection remain unfinished.

Implementation paths are relative to the repository root.

## Objective

Prepare repeatable measurements and find useful low and peak request rates for one warm CPU replica. Use the pilot to choose the settings for the later fixed-one, fixed-three and HPA comparison. Demo and portfolio uploads will be handled later.

## Existing implementation

- `bench/inference.js` sends controlled traffic through the Ollama Service and exports k6 metrics. `RATE` means requests per 10 seconds.
- Requests use `qwen2.5:0.5b`, one repeated prompt, non-streaming responses, at most 64 output tokens, a 1024-token context, two inference threads, temperature 0, seed 42 and a 30-second timeout.
- `bench/observe.py` is implemented and verified. `bench/analyze.py` remains a starter; progress is recorded below.
- One replica requests and is limited to 2 CPU units; memory request is 1 GiB and limit is 2 GiB. These remain pilot settings.

## 1. Measurement design

| Area | Data | Source and proposed collection |
|---|---|---|
| Requests | Start/end time, duration, HTTP status, outcome and error category, output-token count, model-load duration | k6 records correlated starts and completions; retain its raw metric export and summary |
| Load | Requested rate, started/completed requests, response failures and dropped iterations | k6; report each count separately |
| Application state | Pod UID/name, phase, Ready condition, restarts, desired and available replicas | `observe.py` reading Kubernetes through `kubectl`; target one poll every 5 seconds |
| Scaling state | HPA presence, desired/current replicas, conditions and reported CPU signal | Same observer; absent HPA is expected during this pilot |
| Container resources | Cumulative CPU core-seconds, memory working set in bytes, container start time | Implemented direct kubelet `/metrics/resource` collection through the Kubernetes API node proxy; see `md/OBSERVATION.md` for verification and limitations |
| Node resources | Node CPU and memory, node capacity and allocatable resources | Same resource endpoint and Kubernetes node metadata; scope is the Minikube node, not the whole Windows computer |

Keep metrics-server values separately as observations of the scaling input. They must not substitute for the resource-consumption source. The metrics-server project recommends collecting kubelet resource metrics directly for monitoring.

Store UTC timestamps, source timestamps where available, and collection start/end times. A 5-second polling target does not imply fresh underlying data every 5 seconds. Preserve raw samples and source windows.

Convert the CPU counter difference divided by elapsed seconds into average CPU units. For the current 2-CPU container limit, divide by 2 for the fraction of that limit. Keep consumed CPU, requested CPU and CPU limits as different fields. Convert memory bytes into MiB for tables. Match resource labels to the intended namespace/pod/container; use pod UID, restarts and container start time to detect changed instances. Counter resets or gaps must not produce negative CPU or invented zero values.

Observation failures must produce timestamped error records. Missing values stay missing. Record polling duration and overruns. Verify that collection itself does not materially change the low-load response times before increasing load. If the direct resource endpoint is unavailable, retain the diagnostic evidence and revise this choice before making resource-consumption claims; metrics-server-only probes can be labelled exploratory.

## 2. Saved run format

Each run gets a new directory under the code project's `results/pilot/`, for example `2026-10-16T120000Z-rate-2/`. Never overwrite an earlier run.

```text
metadata.json          # Run ID, actual times, rate/unit/duration, model/request,
                       # image identity, versions, script hashes, resources,
                       # node settings, warmup and process exit codes
requests.json          # Raw k6 metric export
request-events.jsonl   # Correlated per-request outcomes, without response text
summary.json           # k6 aggregates
cluster.jsonl          # Timestamped state, scaling input, raw/parsed resources and errors
console.txt            # k6 diagnostics
cluster-before.json
cluster-after.json
warmup.json            # Separate generation result/timing, without response text
collection-check.json  # Reconciliation, coverage, counts and integrity errors
inputs/                # Exact scripts/workload and an empty explicit k6 config
```

JSONL means one JSON record per line. Metadata must distinguish the measured request interval from warmup, drain and idle observation. Keep started/completed/failed/dropped counts and unfinished work explicit. A response failure counts among completed requests; it is not added to them again.

### Run one load probe

The existing [launcher](../../bench/run_pilot.py) creates an exclusive output directory before starting k6. Run this once for each candidate from section 4, with a new directory:

```powershell
$rate = 2
$runDir = Join-Path 'results/pilot' ("{0}-rate-{1}-{2}" -f [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'), $rate, [Guid]::NewGuid().ToString('N').Substring(0, 8))
python .\bench\run_pilot.py --base-url "$env:BASE_URL" --rate $rate --duration 2m --run-dir "$runDir"
```

It refuses existing paths before any process or request starts. The fixed-one-replica launcher then performs this sequence:

1. Copy the five executable input files into `inputs/`, record SHA-256 hashes and tool versions, and save metadata. Version-command failures are retained as warnings; absence of k6 or failed cluster collection still stops the run. Record unrelated computer activity with `--activity-note`.
2. Save a complete initial observer sample. Require one running/Ready pod and a stable one-replica Deployment, the intended container/node resource counters and no HPA targeting the Deployment. Record pod/container/image identity and resource configuration.
3. Observe idle state for 60 seconds, then send one separate warmup generation using the same `bench/workload.json` payload as k6. A failed warmup prevents measured load. The default warmup timeout is 120 seconds; the load-request timeout remains 30 seconds.
4. Run k6 against the preserved script copy. Observe throughout the run and its graceful completion period, then for another 10 seconds. A collection failure, loss of readiness, restart or changed container identity stops load and retains partial evidence. Polling cannot detect a transient change that begins and ends between samples.
5. Stop observation cooperatively, collect a final sample and save the final snapshot. Reconcile records and write `collection-check.json` and final metadata even when an ordinary run error or Ctrl+C interrupts the sequence.

The observer interval defaults to 5 seconds. `--idle-seconds`, `--post-seconds`, `--observer-interval` and `--warmup-timeout` are recorded overrides; very short test-only intervals are not the accepted pilot protocol. Inherited `K6_*`/scenario variables are removed and an explicit empty k6 config prevents local overrides from silently changing the experiment. Do not start a second standalone observer for this launcher.

`request-events.jsonl` contains `started` and `completed` events linked by run/scenario/iteration ID. Completion fields include UTC times, wall elapsed duration, HTTP duration, status, success/failure, error category, optional token count and model-load milliseconds. Missing optional data stays `null`; valid zero stays zero. Response text is excluded. Timeout, transport, HTTP status, invalid JSON, incomplete response and empty response are distinct failures. Dropped iterations never began a request and have no fabricated request event.

`metadata.json` distinguishes the load-process interval from `load_window`: the k6 scenario start, scheduled load end and final client completion. `phases` records orchestration transitions. `pilot_records.py` checks request-event identities/times, event/raw/summary counts, successful warmup, container stability throughout `cluster.jsonl`, ordered observations, gaps above twice the recorded interval and observation coverage of load/client drain. Boundary snapshot copies are retained for inspection but are not revalidated separately. Missing/mismatched archive hashes and failed version diagnostics appear in `warnings`; only measurement `errors` invalidate the collection. A warning about changed scripts still limits provenance and should be reviewed before drawing conclusions. Repeat this read-only check with:

```powershell
python .\bench\pilot_records.py "$runDir"
```

Exit 0 means collection passed and k6 thresholds passed; 99 with status `thresholds_failed` means thresholds failed but complete measurement evidence was retained. Exit 1 means failed/incomplete collection, 2 rejects an existing path, and 130 records an interruption. Inspect both `k6_exit_code` and `collection_valid`: load overload and measurement failure are different outcomes. A timeout is a completed failed client request; it does not prove Ollama stopped processing it. `server_drain_verified` remains false: wait for outstanding work and CPU recovery before another probe. The 10-second post-load observation alone does not certify recovery. The numeric discovery sequence and stop rules are defined only in section 4.

## 3. Verify the measurements first

1. Confirm the current cluster and Service address, one ready replica, no HPA targeting it, and recorded resource settings. Record other heavy activity on the computer and avoid it during probes.
2. Inspect the direct kubelet endpoint. Confirm that the expected Ollama container exposes advancing CPU counters and plausible memory values; verify units, labels and source timestamps.
3. Start observation, collect about 60 seconds of idle samples, and send a separate warmup request. Exclude warmup from k6 measurements and confirm model loading has finished.
4. Run a one-minute low-load check and reconcile request records with k6 totals. Compare observer-off/on checks if collection overhead is uncertain.
5. Inspect missing/error samples and check that request and resource timestamps align. Measure the actual collection cadence. Stop cleanly and confirm all files remain readable.

Acceptance: request totals reconcile, the intended container is identified, collection gaps are visible, timestamps can be aligned, and no saved run is overwritten. Do not treat an empty HPA list as a collection failure.

## 4. Pilot sequence

All discovery probes use one warm replica, the same request/settings and no autoscaler. Use independent constant-rate runs rather than one continuous ramp.

| Probe | Requested rate | Equivalent rate | Measured duration |
|---|---|---|---|
| A | 2 requests / 10 s | 0.2 requests/s | 2 minutes |
| B | 5 requests / 10 s | 0.5 requests/s | 2 minutes |
| C | 10 requests / 10 s | 1 request/s | 2 minutes |
| Conditional D | 20 requests / 10 s | 2 requests/s | 2 minutes |
| Conditional E | 40 requests / 10 s | 4 requests/s | 2 minutes |

These are starting candidates from the existing guide, not measured capacity. Only advance after inspecting the previous probe. If A is already too heavy, try 1 request per 10 seconds. If the useful boundary lies between two rates, test an intermediate rate.

Between probes, let all outstanding requests finish and CPU return close to the recorded idle level. Start each measured interval in a comparable warm state and record the pause.

Proposed discovery stop rules: do not increase the rate if p95 exceeds twice the low-load baseline, any response times out, or iterations are dropped. Treat these as reasons to inspect the result, not final application acceptance thresholds. Stop a run early on a container restart, loss of readiness or a broken measurement process; retain partial data and the reason. A nonzero k6 exit code caused by a response threshold is evidence of overload, not automatically a broken experiment.

Repeat the selected low and peak candidates for 5 minutes each, at least twice, to check that the choice is not based on one short fluctuation. Extend or repeat when the trend or variation remains unclear. A peak candidate should show reproducible response-time degradation while still producing enough completed responses to compare modes. If one replica has no usable overload boundary in these probes, revise the rates or workload and record the change.

## 5. Pilot output and decisions

Implement the minimum pilot analysis in `bench/analyze.py`: one CSV row per run containing actual rate, duration, completed/successful/failed/dropped counts, mean/p50/p95/max successful-response latency, output-token distribution, CPU observations and peak memory. Include sample counts and collection coverage.

Produce aligned time plots of individual response durations, request completions/failures, CPU, memory and ready replicas. At low rates, do not display a p95 every 5 seconds: too few responses fall in such a window. Use whole-run percentiles and individual response points for this pilot.

Record the selected low/peak rates and an explicitly justified acceptable p95/error target in `md/plans/experiment-protocol.md` before comparing replica modes. Discovery stop rules are not the final target. Record repeated-prompt caching and the single-host CPU setup as limitations. Confirm later that three replicas fit the node's allocatable resources and whether they actually improve performance.

The immediate result is a tested measurement path, saved pilot runs and documented experiment settings. No scaling-performance or resource-saving conclusion is expected at this stage.

## Sources

- Existing `md/ROADMAP.md`, `md/GETTING_STARTED_RU.md` sections 8, 11 and 14.13-14.16, and `bench/inference.js` in the target code directory.
- [Metrics Server purpose and limitations](https://github.com/kubernetes-sigs/metrics-server).
- [Kubernetes container CPU and memory metrics](https://kubernetes.io/docs/reference/instrumentation/metrics/).
- [k6 dropped iterations](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/dropped-iterations/).


## Implementation progress: 2026-10-16

- [x] Implement cluster observation and direct kubelet resource collection in `bench/observe.py`, without new dependencies.
- [x] Verify failure handling, no-overwrite behavior, source timestamps and CPU counter resets with 16 focused tests.
- [x] Verify one ready Ollama replica and absent HPA with saved live data: `results/observation-check-2026-10-16-verified/`.
- [x] Independently check raw resource units/counter differences, collection coverage, and k6 request totals.
- [x] Assess observer overhead with repeated paired low-load checks: `results/observer-overhead-2026-10-16-series1/`. Median paired mean change +5.22%, p95 change +3.95%; the frozen provisional budget was met. Retain the 5-second interval provisionally for the pilot.
- [x] Record correlated requests, shared workload settings and automatic pilot-run metadata; integrate observation and warmup.
- [x] Verify collection with the [live low-load check](../../results/pilot/20261018T202951240Z-collection-check/README.md).
- [ ] Implement the pilot summary/plots in `bench/analyze.py`.
- [ ] Run the increasing-rate pilot and select/freeze low/peak rates and response-time targets.

Implementation detail: the observer keeps raw kubelet values and normalized resource records inside `cluster.jsonl`, rather than requiring a second output file to stay synchronized. CPU rates are in CPU units and memory is in bytes; presentation-unit conversions belong in analysis. Deployment collection uses the entire namespace because Deployment metadata labels may differ from its pod labels.

The original failed verification retained CPU/memory data but omitted Deployment state due to that label difference. It is preserved separately and is not completion evidence. The corrected run supersedes it.

## Collection verification

Run `python -m unittest discover -s bench -p "test_*.py" -v` and `python md/plans/data-collection/verify-tests.py` from the repository root. The suite covers real k6 requests to an HTTP stub, launcher failures, specific invalid records and existing observation checks. The negative-check script disables selected checks only in temporary copies and requires the corresponding assertions to fail.

Archive/version problems are warnings, while request reconciliation, warmup and observation completeness remain required. The lifecycle test now uses the production 5-second interval; an injected 450-ms scheduling pause demonstrates why its former 200-ms interval was fragile. The original isolated failure did not recur in 35 diagnostic attempts; ten revised attempts passed. Unexpected launcher exits preserve diagnostic files in the printed temporary directory.

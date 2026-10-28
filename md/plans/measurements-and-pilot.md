# Measurements and pilot load tests

Updated: 2026-10-21. Observation/resource-source verification, request records and pilot-run orchestration are implemented. Collection has offline tests and a [saved live low-load check](../../results/pilot/20261018T202951240Z-collection-check/README.md). Minimal pilot analysis and discovery are complete; low/peak selection has two five-minute confirmations each. [Saved results](../../results/pilot/discovery-2026-10-18-series1/README.md) support low=2 and peak=8 requests/10 s. I agreed [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) on 2026-10-21; step-20 code and instructions now have local verification; main execution remains separate. Historical checks are linked below.

Implementation paths are relative to the repository root.

## Objective

Prepare repeatable measurements and find useful low and peak request rates for one warm CPU replica. Use the pilot to choose the settings for the later fixed-one, fixed-three and HPA comparison. Demo and portfolio uploads will be handled later.

### Completed implementation: data collection

The collection path now keeps k6 and the existing observer without third-party dependencies. Implementation order: share workload settings between warmup and k6; record correlated request starts/completions; orchestrate preflight, idle observation, warmup, measured load and final observation; reconcile events with raw k6 metrics and the saved summary. Partial failures are preserved and existing run directories are rejected.

Acceptance and verification are tracked in [data-collection/GATES.md](data-collection/GATES.md): real k6 against a local HTTP stub, lifecycle/failure tests, deliberately damaged evidence, existing observer regression tests and the saved live collection check. This completed collection stage did not execute capacity discovery or implement its charts; those were completed in the later pilot stage below.

### Completed revision: simplify checks and strengthen tests

1. Keep measurement failures blocking; make archive hashes and tool-version diagnostics warnings. Remove revalidation of duplicate boundary snapshots; retain validation of the full observation stream.
2. Make negative fixtures fail for one specific reason, with a matching valid control. Prove the unfinished-request and observation-order tests detect deliberately disabled checks.
3. Preserve diagnostics from a failed real-k6 lifecycle test, reproduce its intermittent failure and correct the identified cause without weakening the production coverage rule. Consolidate repeated cases.
4. Run focused tests and historical-evidence checks, then attempt a one-minute low-load check on the existing model/cluster. Save actual results and update status; a capacity pilot is outside this revision.

Acceptance: warnings alone do not invalidate measured data; each targeted disabled check fails its test; lifecycle failures retain actionable evidence; live verification is reported only from saved results. Existing unrelated changes and historical runs must remain intact.

## Existing implementation

### Completed execution: analysis and pilot discovery

The completed `bench/analyze.py` prerequisite provides one CSV row per run, successful-response percentiles, separate request outcomes, optional-token availability, measured-window container CPU/memory observations and collection coverage. Use the already installed Matplotlib as an optional analysis dependency for aligned request/resource/replica figures; keep the collector dependency-free. Preserve raw inputs and use a new output directory for each analysis.

Calculated values and missing/window handling were verified against controlled fixtures and the saved live check; rendered figures were inspected. A/B/C and the intermediate probe ran sequentially with stop-rule inspection and idle recovery; both selected rates then received two five-minute confirmations. Evidence is saved beside the runs. This completed stage did not authorize publication; the later explicit publication request is recorded in [publication-review/GATES.md](publication-review/GATES.md).

Acceptance and evidence: [pilot-analysis/GATES.md](pilot-analysis/GATES.md). The selected rates have repeated discovery evidence. Protocol v1.1 now records the main target as a study assumption; it does not change the original pilot settings or verdicts.

The first A probe exposed a timestamp-boundary rejection despite complete measurements: its last request started 1 ms after the nominal end. Preserve that original failed report. Before repeating discovery, allow exactly one millisecond at either start boundary, matching the integer-millisecond k6 clocks; report such cases as warnings and retain actual timestamps/counts. Two milliseconds outside still invalidates the run. Verify both sides and repeat A with the corrected collector rather than overwriting the original evidence.

- `bench/inference.js` sends controlled traffic through the Ollama Service and exports k6 metrics. `RATE` means requests per 10 seconds.
- Requests use `qwen2.5:0.5b`, one repeated prompt, non-streaming responses, at most 64 output tokens, a 1024-token context, two inference threads, temperature 0, seed 42 and a 30-second timeout.
- `bench/observe.py` is implemented and verified. `bench/analyze.py` produces pilot summaries and aligned plots; progress is recorded below.
- One replica requests and is limited to 2 CPU units; memory request is 1 GiB and limit is 2 GiB. These remain pilot settings.

## 1. Measurement design

| Area | Data | Source and proposed collection |
|---|---|---|
| Requests | Start/end time, duration, HTTP status, outcome and error category, output-token count, model-load duration | k6 emits paired start/completion events; retain its raw metric export and summary |
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

After the 2026-10-28 code refactor, new runs declare `source_archive_version: 2` and also archive `records.py`. The validator requires that helper for the new archive version and retains the original requirements for old runs. Prepared runs still archive `main_protocol.py`, `analyze.py` and mode helpers. The rate-search and wait-pair drivers also save `runtime.py` with its hash beside their own source copy.

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

## Fresh rate selection: 2026-10-27

I requested a new one-copy pilot after the completed main series and wait/no-wait pair. Its purpose is to select rates for a possible later comparison under current host conditions. This is a separate exploratory series; protocol v1.1 and all earlier results remain unchanged. I have not requested HPA or another main matrix as part of this background job.

Reuse the existing launcher, workload, observer, recovery/quiet-state gates, Service-tunnel helper and analyzer. A narrow `--pilot-preparation` option uses the already tested prepared fixed-one path and records purpose `pilot-recalibration`, without main-protocol metadata. A small sequential driver saves its fixed selection rules before load and stops after discovery and confirmations.

- Check one fixed copy, no HPA, the existing image/model/request settings, no game or other project generator, and the pre-launch host snapshot. Retain 60-second idle, separate warmup, fresh low CPU before load, 5-second observation and 10-second post-load observation. Record host snapshots again before each probe; they cannot reconstruct historical host conditions.
- Probe 2 requests/10 s for 2 minutes. If it misses p95 <= 5000 ms or errors <= 1%, or has any response failure, try 1 once; stop if neither is calm. Search peak candidates 8, 10, 12, 16 and 20 requests/10 s, each for 2 minutes, stopping at the first target miss. These are predefined candidates, not capacity claims. Stop further discovery on any response failure even if the combined target is not missed; retain an unresolved selection rather than escalating past it.
- A peak candidate misses the existing 5-second successful p95 or 1% response-error criterion. These criteria guide this new search and do not retroactively change earlier verdicts. Drops, unfinished requests, incomplete duration, collection errors or unexpected warnings stop the job and cannot be selected as valid delivered-load evidence. No automatic replacement runs.
- If a calm and peak candidate are found, confirm low/peak/low/peak with four separate five-minute runs. Both low confirmations must meet the criteria; both peak confirmations must miss at least one criterion. Otherwise record inconclusive selection and stop. HPA benefit is not a selection condition.
- Save raw inputs, observations, outcomes, source/runtime identity, actual timings, collection checks and CSV/JSON analysis beside every run. Check controlled settings and initial identity across runs; preserve target failures. Keep a two-hour wall-clock budget for scheduling further runs; an active run finishes its normal cleanup before exit.

Acceptance: the manifest reports the selected rates and confirmation verdict, or the exact reason selection could not be established. No old path is overwritten. No additional series, HPA run, commit or push follows automatically. Verify the new driver selection/stop rules and the launcher preparation path with local fixtures before starting actual load.

I requested one check about an hour after actual launch. If still running, schedule another check thirty minutes later and end the first check without monitoring. At that later check, follow to completion only if the current phase and remaining run count support an estimate of ten minutes or less; otherwise schedule another thirty-minute check. Pause the follow-up when the job finishes or stops, review saved outcomes and report any problem without starting replacement load.

Pre-launch verification: all 152 bench tests passed, including a real-k6/local-HTTP check of the new prepared pilot path and driver selection/stop fixtures. All 1,207 earlier result files retain their hashes. Docker was started and the existing ai-lab profile resumed without recreation. One Ready copy and no HPA were observed before launch; the retained restart is from recovery before measurement. No main-protocol settings or earlier executable archives changed. Current code/doc changes are uncommitted.

Outcome reviewed on 2026-10-27: [the background series](../../results/pilot/recalibration-20261027-104833/README.md) was interrupted after valid two-minute probes at 2, 8 and 10 requests/10 s (242 successful requests in total). The driver disappeared before measured load at rate 12; its last phase is `initial_quiet`, with no final exit record. All three saved analyses and archived input hashes match replay. No peak candidate or four five-minute confirmations were completed. The raw `running` manifest remains preserved; the separate review records observed process absence and incomplete selection. The exit cause is unknown. The final review deleted the follow-up heartbeat; no new load was started. Any continuation needs a new instruction and new paths, while completed main v1.1 evidence remains unchanged.

### Explicit retry after interruption

I requested another fresh pilot on 2026-10-27 with the same candidate rates, criteria, preparation and four confirmations. The new path is `results/pilot/recalibration-20261027-172726/`; no previous result is reused as a confirmation or overwritten. The existing measurement/selection code remains unchanged. A hidden PowerShell launcher records the driver PID and observed exit code separately because the previous process disappeared without a final record. The wrapper does not alter workload or collection rules.

I requested checks after thirty and sixty minutes. If still running at sixty minutes, schedule the next check twenty minutes later and continue at that interval. Do not continuously observe between checks; at later twenty-minute checks, follow only if the current phase and measured durations support no more than ten minutes remaining. Delete the heartbeat on completion or failure. Do not automatically restart failed attempts, start HPA, modify the main protocol or publish changes.

Retry startup confirmed at 17:31:47 UTC on 2026-10-27, with driver PID 6684 and a new manifest. The launcher syntax check passed; measurement code is unchanged from the 152-test verification. Heartbeat `30-60-20` records the requested follow-up cadence. The initial unsigned-script block happened before load and its log remains saved; the successful launch changes execution permission only for that wrapper process.

Completion reviewed on 2026-10-27: [all eight retry runs](../../results/pilot/recalibration-20261027-172726/README.md) finished by 18:29:08 UTC. Low=2 and peak=12 requests/10 s satisfy the predefined repeated-selection rule. Five-minute low p95 is 0.894/1.135 seconds; peak p95 is 18.941/27.730 seconds, with 0/361 and 153/360 timeout failures. Both peak target misses are preserved; severe variation is not hidden. All 1,231 requests have completions, with zero dropped/unfinished work. All collection checks, saved analyses, archived hashes and controlled identities match replay. The outer wrapper exit code remains unavailable despite a final driver manifest and complete run records. The heartbeat is no longer active. No new load, protocol change or publication followed review.

### Another full repeat after the completed pilot

I requested one more full pilot on 2026-10-27 after reviewing the completed retry. New path: `results/pilot/recalibration-20261027-191145/`. Reuse the same driver, preparation, low/peak candidates, criteria and four-confirmation order. The outcome may differ; do not force peak 12 or replace an unfavorable result. Preserve both earlier fresh series and main protocol v1.1.

Use the same background check cadence: thirty minutes, sixty minutes, then every twenty minutes while still active. No continuous observation between checks; at later twenty-minute checks, follow only if at most ten minutes remain. Delete the heartbeat when done. The operational wrapper retains the process handle before waiting; a no-load exit-code-7 check verifies exit recording. No measurement code or workload change is included, so no full suite rerun or additional validation load precedes this repeat. No HPA or publication follows automatically.

Actual startup was confirmed at 19:12:54 UTC on 2026-10-27. The [repeat completed](../../results/pilot/recalibration-20261027-191145/README.md) at 20:10:36 UTC with captured outer exit code 0, all eight valid runs and the same 2/12 selection. Low p95 is 1.148/1.234 seconds; peak p95 is 29.081/26.612 seconds, with 188/360 and 198/361 timeouts. All 1,229 requests completed, 843 successfully; no unfinished/dropped requests. Replay, saved analyses and archived hashes match. Controlled inputs also match the previous complete pilot. Selection repeats, while severe error-rate variation remains explicit. All raw files are preserved; the heartbeat was deleted and no additional load or publication followed.

### Publication checkpoint after both complete searches

I requested commit and push on 2026-10-27 after reviewing both complete 2/12 pilots and the interrupted attempt. Preserve all three series, including partial records, original verdicts, per-run archives and analysis. The publication includes the prepared fixed-one pilot option, bounded search driver and its tests. External temporary launchers, scheduling records and QA logs are excluded; no measured input or raw file is pruned to reduce the file count.

The publication review replayed all 19 completed runs, checked saved analysis and archived hashes, and confirmed that current executable files still match the last verified live pilot. The earlier 152-test verification is retained without another full suite run for unchanged code. Historical verification and Markdown checks pass. Any later fixed-three/HPA probe is a separate task; main v1.1 settings and its completed matrix remain unchanged.

To run the same search manually from the repository root, use a new destination each time:

```powershell
.\.venv\Scripts\python.exe -B bench/run_pilot_search.py --series-dir results/pilot/recalibration-new
```

This command creates real load. The example documents the entry point; it is not authorization for another run. The driver refuses an existing destination and stops after its fixed search/confirmations or a retained failure/inconclusive outcome.

## 5. Pilot output and decisions

Implement the minimum pilot analysis in `bench/analyze.py`: one CSV row per run containing actual rate, duration, completed/successful/failed/dropped counts, mean/p50/p95/max successful-response latency, output-token distribution, CPU observations and peak memory. Include sample counts and collection coverage.

Produce aligned time plots of individual response durations, request completions/failures, CPU, memory and ready replicas. At low rates, do not display a p95 every 5 seconds: too few responses fall in such a window. Use whole-run percentiles and individual response points for this pilot.

The [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) now retains the selected low/peak rates and records the main p95/error criteria. Discovery stop rules remain historical pilot rules, not application targets. Repeated-prompt caching and the single-host CPU setup remain limitations. Preliminary fixed-three placement/warmup/distribution is verified; the repeated main comparison and analysis are complete in steps 21 and 22. The selected peak did not reproduce the older slowdown; [the discrepancy note](../PILOT_MAIN_DISCREPANCY.md) records the evidence and unresolved cause. Do not apply the later main target retroactively to the pilot.

The immediate result is a tested measurement path, saved pilot runs and documented experiment settings. No scaling-performance or resource-saving conclusion is expected at this stage.

## Sources

- [Roadmap](../ROADMAP.md) for milestones, [getting started](../GETTING_STARTED.md) for setup, [observation documentation](../OBSERVATION.md) for the schema, and [the load script](../../bench/inference.js) for request/scenario settings.
- [Metrics Server purpose and limitations](https://github.com/kubernetes-sigs/metrics-server).
- [Kubernetes container CPU and memory metrics](https://kubernetes.io/docs/reference/instrumentation/metrics/).
- [k6 dropped iterations](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/dropped-iterations/).


## Implementation progress

- [x] Implement cluster observation and direct kubelet resource collection in `bench/observe.py`, without new dependencies.
- [x] Verify failure handling, no-overwrite behavior, source timestamps and CPU counter resets with 16 focused tests.
- [x] Verify one ready Ollama replica and absent HPA with saved live data: `results/observation-check-2026-10-16-verified/`.
- [x] Independently check raw resource units/counter differences, collection coverage, and k6 request totals.
- [x] Assess observer overhead: [saved report](../../results/observer-overhead-2026-10-16-series1/README.md). Apply the [accepted provisional setting](../DECISIONS.md#7-retain-a-5-second-observer-interval-provisionally) for the pilot.
- [x] Extend k6 with correlated per-request records and assemble pilot-run metadata automatically; integrate idle, warmup, load, post-load observation and record reconciliation. Offline verification and its limits: [data collection gates](data-collection/GATES.md).
- [x] Verify the integrated collector against the live Kubernetes/model environment: [2026-10-18 low-load check](../../results/pilot/20261018T202951240Z-collection-check/README.md). This does not complete increasing-rate pilot discovery.
- [x] Implement pilot summary/plots in `bench/analyze.py`; verify calculations/window filtering/missing values and inspect the saved-check plot. Optional Matplotlib is declared in `pyproject.toml`.
- [x] Run increasing-rate discovery and two five-minute confirmations per selected rate: [saved pilot](../../results/pilot/discovery-2026-10-18-series1/README.md).
- [x] Freeze the main protocol and justified response-time target (roadmap step 17): I agreed [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) on 2026-10-21. Step-20 implementation has local verification; fresh runtime readiness and main execution remain separate.

Implementation detail: the observer keeps raw kubelet values and normalized resource records inside `cluster.jsonl`, rather than requiring a second output file to stay synchronized. CPU rates are in CPU units and memory is in bytes; presentation-unit conversions belong in analysis. Deployment collection uses the entire namespace because Deployment metadata labels may differ from its pod labels.

The original failed verification retained CPU/memory data but omitted Deployment state due to that label difference. It is preserved separately and is not completion evidence. The corrected run supersedes it.

## Integrity requirements

Use `bench/run_pilot.py` with a new run directory for each standalone load probe; it refuses existing paths before starting k6. Optional token/load measurements must retain missingness and report availability. Server Ready is not model warm: warm initial replicas separately, and include model loading of new replicas in the scaling reaction. Observation collection times must increase strictly; for the overhead series, a collection gap above twice its recorded interval invalidates coverage. Repeated underlying kubelet timestamps remain possible and are not duplicate collection times.

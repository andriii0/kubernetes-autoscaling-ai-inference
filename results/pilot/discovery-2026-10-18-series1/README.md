# One-replica pilot: discovery and repeated confirmation

Completed on 2026-10-18 UTC (2026-10-19 local time). Eight valid runs follow [the pilot plan](../../../md/plans/measurements-and-pilot.md); the initial pre-fix diagnostic is retained separately. This completes roadmap step 16, not the later comparison of scaling modes.

## Selected rates

Use **2 requests/10 seconds (0.2/s)** for low load and **8 requests/10 seconds (0.8/s)** for the peak comparison. Both candidates have two separate five-minute confirmations in the predeclared order low-1, peak-1, low-2, peak-2. Low-load p95 is 1.430/1.432 seconds with no failures; peak p95 is 28.247/16.447 seconds. The peak is useful because both repetitions show substantial degradation while retaining hundreds of successful responses.

Peak failures differ: 13/240 timeouts (5.42%) in the first repetition, 0/240 in the second. The peak therefore reproduces latency degradation, not an identical timeout probability or a stable numerical capacity limit. The first peak's queue grows toward the timeout; the second grows then partly recovers. No cause for this variation was isolated. Keep both runs and plots; do not average their percentiles or claim a precise maximum throughput.

## Results

All rows below have valid collection, zero dropped iterations, zero unfinished client requests and zero observation collection errors. Failure counts are a subset of completed requests. Successful-response percentiles exclude timeouts; error counts remain explicit. All successful responses contain 56 output tokens.

| Run | Requests/10 s | Scheduled min | Started/completed | Successful | Timeouts | Successful mean / p95, s | CPU mean, cores | Peak MiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| [A2-rate-2](A2-rate-2/metadata.json) | 2 | 2 | 24/24 | 24 | 0 | 1.229 / 1.378 | 0.551 | 513.85 |
| [B-rate-5](B-rate-5/metadata.json) | 5 | 2 | 61/61 | 61 | 0 | 1.340 / 1.459 | 1.332 | 513.93 |
| [C-rate-10](C-rate-10/metadata.json) | 10 | 2 | 121/121 | 79 | 42 | 15.070 / 28.267 | 1.854 | 518.09 |
| [M-rate-8](M-rate-8/metadata.json) | 8 | 2 | 97/97 | 97 | 0 | 7.653 / 12.353 | 1.815 | 519.42 |
| [confirm-low-1](confirm-low-1/metadata.json) | 2 | 5 | 60/60 | 60 | 0 | 1.317 / 1.430 | 0.581 | 518.13 |
| [confirm-peak-1](confirm-peak-1/metadata.json) | 8 | 5 | 240/240 | 227 | 13 | 16.417 / 28.247 | 1.999 | 521.24 |
| [confirm-low-2](confirm-low-2/metadata.json) | 2 | 5 | 61/61 | 61 | 0 | 1.308 / 1.432 | 0.578 | 517.86 |
| [confirm-peak-2](confirm-peak-2/metadata.json) | 8 | 5 | 240/240 | 240 | 0 | 11.337 / 16.447 | 1.977 | 519.80 |

The [combined CSV](analysis/summary.csv) also records client-drain windows, source sample counts, maximum observation gaps and warnings. The longest observation collection gap is under 5.03 seconds. CPU means average available source-interval rates inside each load/client-drain window; they are not integrated CPU consumption. Peak memory is the container working set. Missing resource values remain gaps.

## Decisions made during discovery

1. `A-rate-2` initially produced 25 successful requests but failed recording validation: its last start was 1 ms after the nominal end. Preserve its original [failed report](A-rate-2/collection-check.json), metadata and analysis. Exclude it from rate selection. Re-running the current validator applies the later 1-ms policy and can now pass this same data with a warning; that is a new-policy assessment, not its original verdict. The saved metadata, collection check and first analysis retain the original failure, and the selected-run list continues to exclude A.
2. Before repeating A, allow exactly one millisecond on either timestamp boundary, retain actual timestamps/counts and emit a warning. The regression test accepts one millisecond and rejects two, on both sides. All 50 tests passed before continued discovery. This follows the timestamp precision of k6's integer-millisecond [scenario clock](https://grafana.com/docs/k6/latest/javascript-api/k6-execution/); it does not relax response-time acceptance.
3. `A2-rate-2` establishes a successful p95 of 1377.55 ms. Fix the discovery stop threshold at 2755.10 ms (twice this baseline); it is not the final application target.
4. `B-rate-5` remains below the stop threshold without failures, so run C. `C-rate-10` has 42 timeouts and successful p95 28.267 seconds: stop increasing, and skip conditional rates 20/40. k6 exit 99 records threshold failure while collection remains valid.
5. After CPU recovery, try intermediate rate 8/10 s: `M-rate-8` has 97 successes, no failures and p95 12.353 seconds. Two boundary-tolerance warnings remain visible. Record low=2 and peak=8 before the five-minute repetitions, then run the alternating confirmations without changing workload or resources.
6. Both long low runs stay around 1.43-second p95. Both long peak runs exceed 16 seconds. This supports the chosen comparison rates despite peak variability; additional discovery rates are unnecessary for this pilot. All generated requests completed on the client; server recovery is verified separately below.

## Fixed conditions and recovery

Existing `ai-lab`, namespace `inference`, one Ready Ollama replica, no HPA. Model/request payload is preserved in each run's `inputs/workload.json`: `qwen2.5:0.5b`, repeated prompt, non-streaming, maximum 64 output tokens, 1024-token context, two inference threads, temperature 0, seed 42 and a 30-second client timeout. Ollama parallelism is one. Container CPU request/limit is 2 cores; memory request/limit is 1/2 GiB. Every run retains 60 seconds idle observation, a separate warmup, measured load/client drain and 10 seconds post-load observation. No parallel tests or workload were launched during measured load; unrelated Windows activity was not audited.

The Minikube profile specifies 8 CPUs and 12288 MiB. Docker inspection confirms an 8-CPU quota and 12884901888-byte limit. Kubernetes advertises node capacity 24 CPUs and 32742912 KiB; those advertised values are not the Docker quota. No experiment settings were changed to reconcile these different scopes. Pod UID and restart count remain unchanged throughout all valid runs (the existing restart count is 2).

A timeout ends the client request; it does not certify that server work stopped. Standalone observations between runs, with no concurrent launcher observer, verify recovery using advancing source timestamps:

- [idle-after-C.jsonl](idle-after-C.jsonl): last available fresh CPU rate 0.000386 cores at 2026-10-18T21:27:10.814673+00:00.
- [idle-after-M-fresh.jsonl](idle-after-M-fresh.jsonl): last available fresh CPU rate 0.000196 cores at 2026-10-18T21:33:23.696116+00:00.
- [idle-after-peak-1.jsonl](idle-after-peak-1.jsonl): last available fresh CPU rate 0.000320 cores at 2026-10-18T21:48:05.502984+00:00.
- [idle-after-peak-2.jsonl](idle-after-peak-2.jsonl): last available fresh CPU rate 0.000158 cores at 2026-10-18T22:02:09.926662+00:00.

The first `idle-after-M.jsonl` has only repeated source snapshots and no usable CPU rate; it was retained and followed by the longer fresh-source check above. Between each low and peak confirmation, the peak run's own 60-second idle phase also records fresh CPU rates below 0.001 cores before warmup. The final recovery check shows background CPU after the last peak. The collector's `server_drain_verified=false` metadata was not rewritten: these independent observations provide the additional evidence.

## Reproduce and inspect

Each run retains raw request events/metrics, summary, cluster JSONL, before/after state, workload/script copies, metadata, console and collection check. Each has a separate analysis folder; the eight valid runs are also combined under [analysis/](analysis/README.md). Inspect [first peak](analysis/06-confirm-peak-1.png) and [second peak](analysis/08-confirm-peak-2.png) separately.

From the repository root, with the optional analysis dependencies installed, use an unused destination:

```powershell
$series = 'results/pilot/discovery-2026-10-18-series1'
$names = 'A2-rate-2', 'B-rate-5', 'C-rate-10', 'M-rate-8', 'confirm-low-1', 'confirm-peak-1', 'confirm-low-2', 'confirm-peak-2'
$runs = $names | ForEach-Object { Join-Path $series $_ }
python bench/analyze.py $runs --output-dir "$series/analysis-rerun"
```

Validation: [full regression log](verification-tests.txt), 50 tests passed after the pilot; all eight analysis p95/mean values independently match saved k6 summaries, and counts reconcile. Focused acceptance evidence is in [the gates](../../../md/plans/pilot-analysis/GATES.md).

## Remaining protocol work and limits

Roadmap step 17 must freeze the main experiment settings and justify a response-time target before mode comparison. Pilot `SLO_MS` was unset; existing k6 guards remain inference errors <=1% and zero dropped iterations. The discovery rule is not an application SLA. Do not treat the observed peak as an acceptable service target. Main steady/burst duration, mode order, per-replica preparation and invalid-run handling still require the protocol record; step 17 remains incomplete.

This is one small model, one repeated short prompt, one physical CPU host and two repetitions per candidate. Prompt caching, shared-host scheduling, source cadence and provisional observer overhead limit interpretation. No three-replica, HPA, autoscaling-benefit, Windows-wide energy or cost claim follows from this pilot.

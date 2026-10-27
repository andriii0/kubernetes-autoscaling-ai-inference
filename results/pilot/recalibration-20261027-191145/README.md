# Completed full pilot repeat

I repeated the complete one-copy rate-selection pilot on 2026-10-27 using the unchanged driver, workload, preparation and confirmation rules. It ran from 19:12:55 to 20:10:36 UTC, about 58 minutes, and again selected low = 2 and peak = 12 requests per 10 seconds. All eight runs have valid collection; both low confirmations meet the criteria and both peak confirmations miss them.

## Results

p95 covers successful responses only; timed-out completions remain separate.

| Run | Requests / 10 s | Load duration | Successful / completed | Timeouts | Successful p95, s |
|---|---:|---:|---:|---:|---:|
| 01 discovery low | 2 | 2 min | 25 / 25 | 0 | 1.125 |
| 02 discovery peak | 8 | 2 min | 97 / 97 | 0 | 1.137 |
| 03 discovery peak | 10 | 2 min | 121 / 121 | 0 | 2.363 |
| 04 discovery peak | 12 | 2 min | 144 / 144 | 0 | 20.067 |
| 05 low confirmation 1 | 2 | 5 min | 60 / 60 | 0 | 1.148 |
| 06 peak confirmation 1 | 12 | 5 min | 172 / 360 | 188 | 29.081 |
| 07 low confirmation 2 | 2 | 5 min | 61 / 61 | 0 | 1.234 |
| 08 peak confirmation 2 | 12 | 5 min | 163 / 361 | 198 | 26.612 |

All 1,229 starts have client completions: 843 succeeded and 386 timed out. There are zero unfinished requests and zero dropped starts. Peak error rates are 52.22% and 54.85%, respectively. The successful p95 excludes the 30-second timeouts, so it cannot describe all offered requests. No collection warnings were reported. Actual boundary request counts are retained.

## Comparison with the previous completed pilot

The [earlier complete search](../recalibration-20261027-172726/README.md) also selected 2/12 under the same predefined rules. Its low p95 was 0.894/1.135 seconds; peak p95 was 18.941/27.730 seconds, with 0/361 and 153/360 timeouts. This repeat has low p95 1.148/1.234 seconds and peak p95 29.081/26.612 seconds, with 188/360 and 198/361 timeouts.

Both searches therefore repeat the selected rates and severe target misses at 12, but not stable overload severity. The current repeat is harsher by error rate. A lower successful p95 in one run is not evidence of better overall service when more slow requests time out. Rate 8 remains fast in both short discovery probes. Neither search explains the old rate-8 slowdown or establishes maximum stable capacity.

## Verification and scope

The existing analyzer/collector replay accepts all eight runs. Saved manifest values and analyses match recalculation. Every archived input hash matches. Controlled workload, initial identity and model digests match within this repeat and with the previous completed search; their executable input hashes also match. [review.json](review.json) records the outcome.

The final manifest is `finished` with `selection_confirmed: true`. The background wrapper captured outer driver exit code 0; each measured child returned 0 or 99. Code 99 records a service-target miss, not invalid collection. Normal server drain after client timeouts remains unverified; any later load requires fresh recovery/quiet-state and runtime checks.

I preserved all previous runs and these raw files. Main protocol v1.1 still specifies peak 8; no setting or historical verdict changed. No HPA, additional matrix, replacement load, commit or push followed this review. The follow-up heartbeat was deleted. The old latency cause remains open in [PILOT_MAIN_DISCREPANCY.md](../../../md/PILOT_MAIN_DISCREPANCY.md).

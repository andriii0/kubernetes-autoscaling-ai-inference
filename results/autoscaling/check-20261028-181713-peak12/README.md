# Prepared preliminary HPA check at peak 12

I ran one burst on 2026-10-28 with the existing CPU-based HPA: 60% target, one to three copies and a 300-second scale-down stabilization window. Load is 2 -> 12 -> 2 requests per 10 seconds over 782 seconds, followed by 300 seconds without new requests. This is outside main protocol v1.1. All copies share one computer.

## Outcome

All 457 started requests have client completions: 453 succeeded and 4 timed out at the configured 30-second limit. Zero requests are unfinished or dropped. Collection is valid, with no fatal collection errors or warnings. The launcher/k6 exit code is 99 because successful-response latency exceeded its target; the collector exit code is 0.

Whole-run successful mean/p95/max is 10.301/23.253/29.948 seconds. The descriptive whole-run p95 target of 5 seconds fails. Whole-run errors are 4/457 (0.875%), within the 1% threshold. The saved k6 summary uses `true` to flag a failed threshold; its successful-latency flag is true and its error/drop flags are false.

| Phase, by request start | Completed | Successful | Timeouts | Successful p95, seconds |
|---|---:|---:|---:|---:|
| Low before, 0-120 s | 23 | 23 | 0 | 1.228 |
| Rise, 120-121 s | 1 | 1 | 0 | 1.116 |
| Peak, 121-421 s | 360 | 356 | 4 | 24.346 |
| Fall, 421-422 s | 1 | 1 | 0 | 12.282 |
| Low after, 422-782 s | 72 | 72 | 0 | 1.510 |

Peak errors are 4/360 (1.111%), above the 1% reference when inspected for that phase. The preliminary launcher checks whole-run error rate; I keep this phase result separate. Successful p95 excludes timeouts. A request completing after a phase boundary remains in its start phase. The rise/fall percentiles each have only one sample.

## Scaling and preparation

The saved desired/Ready trajectory is 1 -> 2 -> 3 -> 1. Times below are sampled observations from scenario start, not exact controller decision times.

- Two copies are desired and Ready at about 173.95 s, about 53 s after the peak phase starts.
- Three copies are desired and Ready at about 294.24 s, about 173 s after the peak phase starts.
- Desired copies drop from three to one at about 815.16 s, 33 s after the scheduled load ends. One Ready/non-terminating copy is observed at 820.15 s; the other two remain terminating until they disappear by 855.21 s. Scale-down was observed during post-load observation, not during the low-after phase.

Recovery checked the three existing copies before reset. The launcher selected one initial copy, waited for quiet CPU, observed 60 idle seconds and completed its warmup. Post-warmup settling included fresh metrics-server windows before HPA activation. Saved timestamps verify warmup -> quiet metrics -> HPA -> load. Newly scaled copies did not receive separate pre-load warmups.

The scheduled load window is 18:23:50.089-18:36:52.089 UTC. Finalization finished at 18:41:53 UTC; the outer wrapper exited at 18:41:54 UTC. Recovery reports success. A separate read-only snapshot after completion confirms one Ready copy and no HPA. Normal server drain after client timeouts remains unverified.

## Evidence and limits

All 254 observation timestamps strictly increase. One `missing_resource` sample at 18:38:00 UTC lacks counters for the two terminating copies, after measured load. This appears as one collection/resource-gap entry, not a failed collector or missing client request. Per-copy resources remain available, while an aggregate application resource total is not established; asynchronous readings are not summed.

Complete native logs retain 231/144/82 HTTP completions across the initial, second and third copies. The counts happen to total 457; native logs do not associate individual requests with pods or prove semantic success/drain after timeouts.

The saved [CSV/JSON analysis](../check-20261028-181713-peak12-analysis/README.md), collection check and scaling details match replay. All eleven archived input hashes match. Independent event calculations reproduce whole-run p95 23252.8 ms and peak p95 24346.25 ms; raw k6 successful latency values match event durations. [review.json](review.json) records the review. Existing raw/analysis files are preserved.

The earlier fixed-three steady check has p95 9.507 seconds at the same peak rate. This HPA burst includes the initial scaling response and has p95 24.346 seconds during peak. Different profiles, times and repetition counts prevent an isolated causal comparison. Scaling worked, but the 5-second latency target and an HPA performance benefit are not established. The historical rate-8 discrepancy remains open in [the issue record](../../../md/PILOT_MAIN_DISCREPANCY.md).

I preserved the earlier 181350 wrapper startup failure and its empty host snapshot. It stopped before run-folder creation or inference; the corrected host check ran before the orchestration interpreter. Heartbeat `hpa-12` was deleted after this completed review. No repeat, tuning, additional series, commit or push followed.

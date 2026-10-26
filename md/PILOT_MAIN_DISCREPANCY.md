# Pilot and main-series latency discrepancy

Updated: 2026-10-27.

Status: open. The discrepancy is confirmed. Request accumulation supports a queueing explanation for the large latency increase in the pilot. The physical cause of the difference in effective processing speed remains unknown.

## Problem

The one-copy pilot selected 8 requests per 10 seconds because this rate repeatedly increased response latency. The main series reused that rate, but one fixed copy met the agreed 5-second p95 target in all three steady and all three burst repetitions.

The selected peak did not reproduce the pilot's severe degradation. The main series therefore does not establish the benefit of HPA under sustained overload. Completing the planned matrix does not resolve this discrepancy.

## Confirmed evidence

The table compares the two five-minute pilot peak confirmations with the three main fixed-one/steady repetitions. p95 covers successful responses; failed requests remain separate.

| Run | Successful p95, seconds | Failed / completed | Maximum client requests in flight |
|---|---:|---:|---:|
| Pilot peak 1 | 28.247 | 13 / 240 | 24 |
| Pilot peak 2 | 16.447 | 0 / 240 | 14 |
| Main steady 1, attempt 01 | 1.094 | 0 / 240 | 2 |
| Main steady 2, attempt 12 | 2.243 | 0 / 240 | 3 |
| Main steady 3, attempt 14 | 1.498 | 0 / 240 | 2 |

At this rate, actual request starts are 1.25 seconds apart in both stages. Client requests in flight are starts without a completion yet; they include transport, waiting and execution. They are not a direct measurement of the Ollama queue.

Pilot low-load mean response times were 1.317 and 1.308 seconds without overlapping client requests. In pilot peak 1, successful mean latency by request-start 30-second groups rose from 2.80 to 29.39 seconds. Main fixed-one/steady mean response times were 0.954, 1.094 and 1.154 seconds, with little client overlap.

This pattern supports waiting accumulating when effective processing capacity is close to the arrival rate. A small difference in response-processing time can produce a much larger difference in end-to-end p95. It does not establish the physical reason for that speed difference.

## What matches and what differs

- The request payload, two-thread setting, container resources/environment, initial image ID and recorded tool versions match in the reviewed runs. Successful responses all report 56 output tokens. The main metadata records model digests explicitly; the pilot has no equivalent direct runtime model-digest record.
- Request timing and raw k6 metrics agree. The client elapsed versus HTTP-duration median difference is about one millisecond in both stages. A different percentile definition or a reduced offered request rate does not explain the gap.
- Reported model-load durations in successful pilot peak responses average about 1.2 milliseconds. These records do not support repeated cold loading as the explanation for tens-of-seconds latency.
- Preparation differs: main fixed-one/steady loads start 35-50 seconds after warmup completion, following quiet-state checks. Pilot loads start about 0.15 seconds after warmup. The later diagnostic pair tested the post-warmup wait under current conditions and did not reproduce the old slowdown; it does not isolate the historical physical cause.
- The pilot README reports an 8-CPU/12-GiB Minikube-container quota. A current read-only Docker inspection also shows that quota. The main metadata's 24 CPU describes Docker Engine capacity, not that container quota. The records do not establish an 8-to-24 CPU quota increase; current inspection cannot prove every historical quota.

## Unresolved cause and missing evidence

Historical Windows background activity, CPU frequency/power/thermal state, cgroup throttling counters and server queue/evaluation timings were not collected. Host contention, frequency changes and runtime/cache state remain hypotheses. There is no evidence sufficient to attribute the improvement to a game being closed, additional CPUs, a changed model or the new quiet-state gate.

Recorded measurement checks pass for both stages. That does not establish identical host conditions across dates or prove that the pilot rate is a stable capacity boundary for this shared computer.

## Effect on the research

Keep the completed main matrix, frozen targets, historical measurements and original verdicts. The supported conclusion is that one copy met the service targets under the main-series conditions, while an HPA advantage was not established.

Report the discrepancy and unresolved cause in the final findings. Additional load is a separate decision; this note does not authorize retuning the completed series or another 18-run matrix. Roadmap steps 21 and 22 remain complete for collection and processing. The final findings and reproduction review remain separate work.

## Authorized diagnostic check

On 2026-10-26 I authorized one pair of fixed-one/steady runs at 8 requests/10 s, five minutes each. Both use the same current launcher and common preparation; only the post-warmup quiet-state gate differs. The [procedure](plans/scaling-experiment.md#authorized-post-warmup-wait-pair-2026-10-26) fixes settings, one drawn order, stop rules and the single-pair inference limit. No peak search or main-matrix replacement is included.

### Diagnostic result

The [authorized pair](../results/diagnostics/warmup-wait-20261026-234007/README.md) completed with 481 successful requests and no failures, unfinished or dropped requests. With the quiet gate, actual delay was 50.239 seconds and p95 1.319 seconds; without it, delay was 0.142 seconds and p95 1.267 seconds. The large historical degradation did not recur in the immediate condition. This weakens the wait-alone explanation under current conditions, while one observation per condition cannot resolve order/host drift or prove the historical cause. The issue remains open.

### Interpretation after the fresh check (2026-10-27)

The fresh one-copy results agree in scale with the main series and differ sharply from the historical pilot. At the same configured 8 requests/10 s, the two fresh diagnostic p95 values are 1.267-1.319 seconds, within the main fixed-one/steady range of 1.094-2.243 seconds. The historical pilot peak confirmations had p95 16.447-28.247 seconds. This is agreement in observed performance, not an assertion that the individual results are identical.

HPA was absent in the diagnostic pair. These are two fixed-one steady checks, not a complete new pilot load search or another fixed-one/HPA comparison. Both use current common recovery/preparation; the immediate variant omits only the post-warmup gate. They do not reconstruct all historical host conditions.

On 2026-10-27, I suggested that a game, downloads or another background task may have been active during the old pilot. Resource contention is a plausible explanation for the older slowdown. This is a hypothesis I proposed, not confirmation that such activity occurred or caused the result. Historical host activity was not recorded sufficiently to test it retrospectively.

The confirmed current finding is that one copy handles this rate quickly with either post-warmup variant. The physical cause of the historical slowdown remains open; do not rewrite the old verdicts or present background activity as an established cause.

## Evidence and reproduction

- [Pilot report](../results/pilot/discovery-2026-10-18-series1/README.md).
- [Main-series run table](../results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/main-runs.csv).
- [Detailed discrepancy review and reproduction command](../results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/README.md).
- [Compared values](../results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/comparison.csv) and [30-second groups](../results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/latency-windows.csv).
- [Latency and client-overlap plot](../results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/queue-comparison.png).
- [Current quota inspection and its scope limits](../results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/current-quota-inspection.json).

This note owns the open issue and its research impact. Detailed calculations stay with the run evidence. No new load was generated to write it.

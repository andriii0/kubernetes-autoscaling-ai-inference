# Pilot and main-series latency discrepancy

Updated: 2026-10-28.

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

### Interrupted fresh rate selection (2026-10-27)

I then requested a separate rate-selection pilot. It completed two-minute probes at 2, 8 and 10 requests/10 s, with successful p95 1.067, 1.141 and 1.705 seconds. All 242 requests succeeded, with zero unfinished/dropped requests. The [review](../results/pilot/recalibration-20261027-104833/README.md) verifies saved analyses and archived inputs.

The background process disappeared before measured load at rate 12. No peak, five-minute confirmation or repeated low/peak selection was established. The raw manifest still says `running`, but process checks and the stale partial metadata show an interrupted job; the exit cause remains unknown. This is separate from the unexplained historical latency difference. These short fast results at rate 8 are consistent with the later main/diagnostic results, but they do not establish a sustained capacity boundary. I preserved the partial evidence and did not start replacement load or HPA. The follow-up automation was deleted after review.

### Completed fresh rate selection (2026-10-27)

I explicitly requested a new retry after the interrupted attempt. The [completed pilot](../results/pilot/recalibration-20261027-172726/README.md) selects low=2 and peak=12 requests/10 s. Rate 8 remained fast in discovery (p95 0.937 seconds). The two five-minute low confirmations had p95 0.894/1.135 seconds; the peak confirmations had p95 18.941/27.730 seconds. Peak 1 completed 361/361 successfully; peak 2 completed 207/360 successfully, with 153 thirty-second timeouts. All eight collection checks and saved analyses pass replay, with no dropped or unfinished requests.

The current-host search found repeated overload at 12, but not stable severity. This does not reproduce the old rate-8 slowdown or explain its physical cause. Main protocol v1.1 still uses peak 8 and its completed comparison remains unchanged. A later fixed-three/HPA check at the new rate is a separate decision; this result does not establish an HPA benefit. I retained the interrupted attempt and all unfavorable outcomes. Normal server drain after client timeouts remains unverified; any later load must pass fresh recovery/quiet-state checks.

### Second completed fresh pilot (2026-10-27)

I requested a further complete repeat under the same selection rules. The [latest pilot](../results/pilot/recalibration-20261027-191145/README.md) again selects low=2 and peak=12 requests/10 s. Low p95 is 1.148/1.234 seconds with no failures; peak p95 is 29.081/26.612 seconds with 188/360 and 198/361 thirty-second timeouts. All eight collection checks and saved analyses match replay, with zero unfinished/dropped requests. Executable input hashes, workload, initial identity and model digests match the earlier completed search.

The current-host selection and severe target misses at 12 repeat across both complete pilots; their timeout rates do not remain stable. The old rate-8 slowdown is still unexplained. More timeouts can remove slow responses from successful p95, so compare latency and errors together. This adds evidence for choosing an overload candidate in a separately agreed follow-up, not an HPA benefit or a revised main v1.1 result. No further load followed completion; the heartbeat was deleted. Raw measurements and all earlier verdicts remain unchanged.

### Three prepared copies at the new peak (2026-10-27)

I requested one preliminary fixed-three steady check at 12 requests/10 s for five minutes. The [saved check](../results/fixed-replicas/check-20261027-203849-peak12/README.md) completed 361/361 requests successfully, without dropped or unfinished work. Three individual warmups and native Service completion counts 123/118/120 are verified. Successful mean/p95/max is 4.066/9.507/14.773 seconds: no timeout occurred, but p95 still exceeds the 5-second target. Collection and independent p95/raw-k6/saved-analysis checks pass.

This observation has shorter successful latency than the four earlier one-copy peaks at rate 12; it is a single preliminary run at another time on the shared host, not proof of an isolated capacity benefit or acceptable HPA latency. The combined CPU limit also rises from 2 to 6. Both the old rate-8 discrepancy and remaining rate-12 latency need to stay explicit. The check ended with three Ready copies, no HPA and no new load; the follow-up was deleted. No main protocol or historical verdict changed.

## Evidence and reproduction

On 2026-10-28 I completed the separately authorized [prepared HPA burst](../results/autoscaling/check-20261028-181713-peak12/README.md) at 2 -> 12 -> 2 requests/10 s. Desired/Ready copies follow 1 -> 2 -> 3 -> 1; one copy is restored after load. Collection is valid: 453/457 requests succeed, four time out, and none are dropped or unfinished. Peak successful p95 is 24.346 seconds; whole-run p95 is 23.253 seconds, both above 5 seconds. Whole-run errors are 0.875%, while peak errors are 1.111%. Successful percentiles exclude the four timeouts. One missing-resource sample occurs after load during pod termination. Source hashes, saved analysis and independent request/raw-k6 calculations match; cleanup is verified. The [procedure](plans/scaling-experiment.md#authorized-prepared-hpa-check-at-peak-12-2026-10-28) and [completed status](STATUS.md#completed-prepared-hpa-check-at-peak-12) own execution details. Heartbeat `hpa-12` was deleted.

This demonstrates scaling under the new burst, not acceptable latency or an isolated HPA benefit. The earlier fixed-three run is steady and at another time; one observation per configuration cannot establish a controlled repeated comparison. Neither check explains the historical rate-8 discrepancy or revises main v1.1. I retained the earlier 181350 wrapper failure before measured-run creation, its logs/state and empty host snapshot. No repeat, tuning or new matrix followed this review.

### Controlled comparison at rate 12

I later ran the same `2 -> 12 -> 2` burst three times in fixed one, fixed three and HPA. The [completed comparison](../results/follow-up/comparison-20261110-205108-peak12/README.md) closes the traffic-profile gap between the preliminary checks. Fixed one missed every target and had 698 peak failures. HPA reduced peak failures to 89 but missed the five-second p95 target in all three repetitions. Fixed three completed all 1,080 peak requests, passed twice and missed once at 5.116 seconds.

This follow-up supports the rate-12 overload comparison. It does not explain why the historical pilot was slow at rate 8, and it does not change the main v1.1 results.

- [Pilot report](../results/pilot/discovery-2026-10-18-series1/README.md).
- [Main-series run table](../results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/main-runs.csv).
- [Detailed discrepancy review and reproduction command](../results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/README.md).
- [Compared values](../results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/comparison.csv) and [30-second groups](../results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/latency-windows.csv).
- [Latency and client-overlap plot](../results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/queue-comparison.png).
- [Current quota inspection and its scope limits](../results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/current-quota-inspection.json).

This note owns the open issue and its research impact. Detailed calculations stay with the run evidence. No new load was generated to write it.

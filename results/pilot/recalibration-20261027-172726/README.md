# Completed fresh one-copy pilot

I completed eight runs on 2026-10-27, from 17:31:47 to 18:29:08 UTC (about 57 minutes). The predefined search selected low = 2 and peak = 12 requests per 10 seconds. Both five-minute low confirmations meet the criteria; both peak confirmations miss them. This is separate from main protocol v1.1 and does not establish an HPA benefit.

## Results

p95 covers successful responses only; failed completions remain in the counts.

| Run | Rate per 10 s | Load duration | Successful / completed | Timeouts | Successful p95, s |
|---|---:|---:|---:|---:|---:|
| 01 discovery low | 2 | 2 min | 25 / 25 | 0 | 0.935 |
| 02 discovery peak | 8 | 2 min | 97 / 97 | 0 | 0.937 |
| 03 discovery peak | 10 | 2 min | 121 / 121 | 0 | 0.928 |
| 04 discovery peak | 12 | 2 min | 145 / 145 | 0 | 8.450 |
| 05 low confirmation 1 | 2 | 5 min | 61 / 61 | 0 | 0.894 |
| 06 peak confirmation 1 | 12 | 5 min | 361 / 361 | 0 | 18.941 |
| 07 low confirmation 2 | 2 | 5 min | 61 / 61 | 0 | 1.135 |
| 08 peak confirmation 2 | 12 | 5 min | 207 / 360 | 153 | 27.730 |

All 1,231 started requests completed: 1,078 succeeded and 153 timed out. There are zero unfinished requests and dropped starts. The second peak has 42.5% response failures; its p95 excludes those 30-second timeouts. Runs 03, 05 and 06 retain only the accepted one-millisecond boundary warning. Actual counts include valid scheduled boundary arrivals.

## Verification and limits

All eight collection checks pass replay. Saved analyses and manifest values match recalculation; archived hashes, controlled workload, initial identity and model digests match across runs. The four confirmations satisfy the rule fixed before load: p95 <= 5000 ms and errors <= 1% for low, with at least one criterion missed in each peak. Rates 16 and 20 were not needed or tested. [review.json](review.json) records the checks.

The final driver manifest says `finished` and `selection_confirmed: true`. Child launch codes are 0 or 99; 99 records a service-target failure. The PowerShell wrapper records driver exit, but its outer exit-code field is null. Completion is verified from the final manifest, logs and complete run evidence; an independently captured outer exit code is unavailable. Normal server drain after the final client timeouts is not verified. Check runtime readiness and quiet state before later load.

Rate 8 stayed fast, consistent with the main series and wait/no-wait diagnostic. At 12, both five-minute runs show severe degradation. This establishes an overload candidate under current conditions, not maximum stable capacity. The first peak had no timeouts and the second had 153; repeated target failure does not imply stable severity. Shared-host/runtime variation and the physical cause of the old slowdown remain unresolved.

I preserved all old and current raw records. Main protocol v1.1 still uses peak 8; I have not changed it. I ended this pilot without starting HPA or replacement load. The open issue remains in [PILOT_MAIN_DISCREPANCY.md](../../../md/PILOT_MAIN_DISCREPANCY.md).

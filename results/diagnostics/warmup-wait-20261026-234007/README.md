# Post-warmup wait diagnostic pair

I completed this two-run screening pair on 2026-10-26 UTC. It is outside main protocol v1.1 and does not replace the completed matrix. I stopped after the pair, without a new peak search.

## Controlled comparison

Both variants use the same current run_pilot.py, inference.js, workload, image/model, running container identity and requested resources. One fixed copy, no HPA, 8 requests/10 s, five-minute steady load, 60-second idle, 5-second observation, 10-second post-load period and a descriptive 5-second successful-p95 target. Common recovery, initial quiet-state checks and separate warmup precede both variants.

Only the quiet variant applies the post-warmup quiet-state gate. The drawn order was quiet, then immediate; manifest.json records that order before the first load. This does not reproduce every historical pilot condition. It isolates the post-warmup gate among the controlled settings under the current host state.

## Results

| Variant | Actual wait after warmup | Completed / failed / unfinished / dropped | Successful mean / p95 | Maximum response | First-30-second mean | Maximum client requests in flight |
|---|---:|---|---|---:|---:|---:|
| Quiet, first | 50.239 s | 240 / 0 / 0 / 0 | 1.078 / 1.319 s | 2.553 s | 0.993 s | 3 |
| Immediate, second | 0.142 s | 241 / 0 / 0 / 0 | 1.046 / 1.267 s | 1.647 s | 1.077 s | 2 |

All 481 requests succeeded. Both collections are valid, with complete scheduled duration and no warnings. The 241st request is a retained scheduled boundary arrival accepted by reconciliation, not evidence of a changed configured rate. Counts are not forced to equal 240.

In this pair, removing the extra wait did not reproduce the historical 16-28-second p95 or large client backlog. This weakens the post-warmup wait alone as a sufficient explanation under current conditions. Do not claim that waiting has no effect in every environment, or that immediate is generally faster: there is only one observation per condition and time/order/host drift is not eliminated.

## Verification and scope

Independent request-event p95 calculations match the raw successful_latency_ms values and k6 summaries. Payload/source hashes, initial container identity, model digest, Minikube-container quota and power-scheme identity match between variants. Existing analyzer output is saved separately for each run. All 1,147 result files that existed before the pair retain their bytes. The new diagnostic option does not alter archived main inputs or protocol v1.1 settings.

Pre-launch host snapshots are not continuous host measurements. Win32_Processor CurrentClockSpeed/MaxClockSpeed fields are not a trace of actual boost clocks; LoadPercentage is missing in the second snapshot and remains null. Localized power-scheme text was decoded incorrectly by the launcher; the GUID is preserved and matches, and original snapshot bytes are retained. The subsequent driver fix stores the ASCII power-scheme GUID without a localized label, uses explicit UTF-8 and treats PowerShell errors as fatal; it was not used to generate these measurements. This limitation does not affect the request-time calculation.

After the pair, one Ollama copy was Ready, HPA absent and no project load/observer process remained. Normal server drain is not independently verified. No game/other generator was found in the recorded pre-launch checks. The physical cause of the historical effective-speed difference remains open in [the issue note](../../../md/PILOT_MAIN_DISCREPANCY.md).

## Files and reproduction

- manifest.json: drawn order, settings, completion and archived runner hash.
- comparison.json/csv and review.json: measured results and independent checks.
- 01-quiet/ and 02-immediate/: raw measurements, archived inputs, preparation gates and metadata.
- Per-run analysis directories: existing analyzer output; host-before.json files: pre-launch snapshots.
- run_wait_pair.py: exact driver copy used for this pair; collector inputs are preserved per run.

To analyze saved data again, choose a new destination for the existing analyzer:

```powershell
.\.venv\Scripts\python.exe -B bench/analyze.py results/diagnostics/warmup-wait-20261026-234007/01-quiet results/diagnostics/warmup-wait-20261026-234007/02-immediate --output-dir results/diagnostics/warmup-wait-20261026-234007/analysis-rerun --no-plots
```

Any repeat would use fresh runtime checks and a new series path.

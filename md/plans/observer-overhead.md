# Observer overhead check

Date: 2026-10-16. Protocol recorded before the repeated series.

## Objective and fixed settings

Check whether the current observer adds a material response-time penalty at the existing low request rate, before increasing load. Use one warm Ollama CPU replica, no HPA, and unchanged `bench/inference.js` and `bench/observe.py`. Record both source hashes and before/after cluster snapshots for each run.

Use 2 requests per 10 seconds for 2 minutes per run. Perform four pairs in this fixed order: off/on, on/off, on/off, off/on. Each condition has four runs, with balanced ordering. Each run has three separate warmup requests followed by a 10-second pause; warmup is excluded. Wait 20 seconds after each measured run. For observer-on runs, start collection 10 seconds before k6 at the existing 5-second polling interval and keep it running through the final response. Never collect simultaneously in observer-off measured intervals.

## Acceptance and interpretation

- Save raw k6 metric exports, summaries, console output, exact run times, warmup results, configurations, hashes and exit codes per run. Save observer JSONL and errors for observer-on runs only.
- Require zero inference errors and dropped iterations, stable pod UID/restart count/image/configuration across the series, one desired/ready replica and no HPA in each before/after snapshot. Any failed condition invalidates the performance decision until inspected.
- Recalculate per-run mean and p95 latency from raw samples, verify them against summaries, and report every pair's on/off percentage change. Keep run-level observations separate; do not treat requests from one run as independent experiment repetitions.
- Freeze a provisional engineering budget of 10% for the median paired mean-latency change and 10% for the median paired p95 change. Also require no individual pair's mean penalty above 20% to proceed unchanged. This is a practical screening rule, not an equivalence test, application SLO or a claim that instrumentation has no effect.
- If the observed budget is met, retain the current observer provisionally for the pilot and continue recording its settings. If exceeded or inconsistent, inspect the pattern, reduce measurement work (first candidate: a 10-second interval, since source samples often repeat), and run a separately labelled paired series before selecting a new setting. Preserve the original series.

## Checks and output

Offline verification must check raw request totals, recomputed percentiles, expected run order/counts, source hashes, timestamps, unchanged snapshots, observer errors and coverage of each on-run measured interval. Save `runs.csv`, `pairs.csv`, `analysis.json` and an evidence-linked README under a new `results/observer-overhead-<UTC timestamp>/` folder. Keep the runner and analyzer with the data so the procedure and calculations can be inspected.

Limits: four pairs of short runs and one repeated prompt on a shared Windows host cannot establish general equivalence, rule out external load/thermal effects, measure capacity, or predict instrumentation effects near saturation. Report both order-specific patterns and spread, even if the screening rule passes.

## Verified outcome

Completed four pairs (eight runs, 195 successful requests) in `results/observer-overhead-2026-10-16-series1/`. No inference errors, dropped iterations or collection errors were observed. Cluster identities/configuration and both source hashes matched.

Median paired mean-latency change was +5.22%; median paired p95 change was +3.95%. Pair mean changes ranged from -5.79% to +6.73%; three of four were positive. The frozen practical budget was met. Retain the existing 5-second interval provisionally for pilot measurements, while recognizing the observed small penalty and the limits of four pairs. This does not establish negligible overhead near saturation.

Raw-sample calculations and validity checks passed; five analyzer tests passed, including rejection of known bad artifacts. See the saved README, `analysis.json`, `runs.csv`, `pairs.csv` and runner/analyzer sources for reproducible evidence. No instrumentation code or model settings were changed during this series.

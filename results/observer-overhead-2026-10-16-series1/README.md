# Repeated observer overhead check

Date: 2026-10-16.

The existing 5-second observer meets the frozen provisional budget in this low-load series. Retain it provisionally for pilot measurements.

## Protocol

Four paired comparisons with counterbalanced order: off/on, on/off, on/off, off/on. Each run used one warm CPU Ollama replica, the unchanged repeated prompt, 2 requests per 10 seconds and a two-minute measured interval. Three warmup requests per run were excluded. Observed runs used the existing 5-second collector; control runs had no collector. Preparation and pauses are specified in [protocol.md](protocol.md).

The engineering budget was frozen before running: median paired mean and p95 changes each at most +10%, and no individual pair's mean penalty above +20%. This is a screening rule, not a statistical equivalence test or application latency target.

## Per-pair results

| Pair | Order | Mean off (ms) | Mean on (ms) | Mean change | p95 off (ms) | p95 on (ms) | p95 change |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | off/on | 1808.24 | 1703.56 | -5.79% | 1958.40 | 1716.80 | -12.34% |
| 2 | on/off | 1614.33 | 1716.00 | +6.30% | 1744.30 | 1769.80 | +1.46% |
| 3 | on/off | 1660.17 | 1729.08 | +4.15% | 1744.90 | 1922.00 | +10.15% |
| 4 | off/on | 1691.21 | 1804.96 | +6.73% | 1747.60 | 1860.25 | +6.45% |

Median paired mean change: +5.22%. Median paired p95 change: +3.95%.
Pair mean-change range: -5.79% to +6.73%. Pair p95-change range: -12.34% to +10.15%.
Mean latency was higher with the observer in 3 of four pairs. Signs and spread should be read alongside the median.

## Validity and saved evidence

Eight valid runs, 195 successful requests, no inference errors or dropped iterations. Before/after snapshots preserve the same pod UID, restart count, model image and deployment configuration, with one ready replica and no HPA. Observer-on JSONL covers each measured interval with no source collection errors. Both source hashes match the executed versions. All runs produced the same 56-token output length.

Raw request counts, mean latency and p95 were recalculated and checked against k6 summaries by [analyze-overhead.py](analyze-overhead.py). Five analyzer tests include positive controls and rejection of incomplete series, altered summaries, restarted containers and collection errors; see `analysis-tests.txt`. Source hashes and exact UTC times are in `manifest.json` and each run's `metadata.json`.

Each numbered folder contains raw k6 samples, summary, console output, warmup responses and before/after cluster snapshots. Observer-on folders additionally contain `cluster.jsonl` and observer console/error files. [runs.csv](runs.csv), [pairs.csv](pairs.csv) and [analysis.json](analysis.json) preserve the derived results.

To reproduce analysis, run `python analyze-overhead.py .` from this directory. To repeat the series from the project root, open the current Service tunnel and run the saved `run-overhead.ps1` with `-BaseUrl` and a new `-RunDirectory`. Existing series directories are refused.

## Interpretation and limits

Four pairs of short runs on one shared computer cannot establish general equivalence or attribute every latency difference to the collector. Counterbalancing reduces simple order bias but does not control all external activity or thermal effects. Requests within a run are not independent experiment repetitions. This repeated-prompt result does not predict overhead near saturation or under different model settings.

The earlier single off/on check showed higher observed latency; these repeats replace that one-pair observation as the basis for the provisional decision. They do not establish capacity, a final p95 target or an autoscaling advantage.

## Validation maintenance on 2026-10-18

The analyzer now rejects repeated or unordered observation collection times and gaps above twice `observer_interval_seconds` (10 seconds for this series). This tolerance is a validation rule, not a measured maximum or a guarantee of fresh kubelet samples. Small collection jitter is permitted. The original measurements and saved aggregates are unchanged.

`sources/inference.js` and `sources/observe.py` preserve the exact measured source bytes, checked against the original manifest hashes before copying. The analyzer prefers these snapshots so later runtime-code fixes do not invalidate historical source identity; an altered snapshot still fails the original hash check. Real-series reanalysis for this maintenance was performed on a temporary copy. Future overhead runs save source snapshots through the run script.

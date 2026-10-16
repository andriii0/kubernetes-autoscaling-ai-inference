# Observer and resource-source verification

Date: 2026-10-16. Corrected verification of `bench/observe.py`; not a capacity benchmark.

## Procedure

Verified the existing one-replica deployment and absent HPA. Sent one separate warmup request, then ran k6 at 2 requests per 10 seconds for one minute without the observer. Started a 150-second observer session, waited 60 seconds at idle, and repeated the same one-minute load. The observer continued through the end of the request run. Request settings match `bench/inference.js`; warmup is excluded.

| Measurement | Observer off | Observer on |
|---|---|---|
| Completed successful requests | 13 | 12 |
| Response failures | 0 | 0 |
| Dropped iterations | 0 | 0 |
| Mean response latency | 1609.077 ms | 1747.833 ms |
| p95 response latency | 1643.200 ms | 1870.750 ms |

## Observation results

- 30 records; zero collection errors. Source state includes one ready replica and no HPA throughout.
- Start-to-start observation span: 145.025 seconds. Mean polling interval: 5.001 seconds; maximum: 5.016 seconds.
- Maximum collection duration: 1.734 seconds.
- 17 distinct Ollama resource timestamps and 14 valid CPU-rate differences. Repeated timestamps correctly leave CPU rate missing.
- Peak container memory working set: 573.520 MiB.
- Mean sampled CPU before the measured load: 0.15567 CPU units; during load: 0.54385; peak sampled load CPU: 0.87525. These are source-interval averages, not instantaneous peaks.

`checks.json` records an independent artifact inspection: raw source units and counter arithmetic, unchanged pod/restart identity, UTC timestamps, coverage, ready replicas, raw request totals and percentile calculations. Re-run it with `python .\verify.py .` from this directory. `metadata.json` preserves actual run times, request configuration, tool versions, source hashes and exit codes. Cluster snapshots preserve deployment configuration and image identity.

`baseline-requests.json` / `baseline-summary.json` contain the observer-off run; `requests.json` / `summary.json` contain the observer-on run. `cluster.jsonl` contains both raw and normalized resource observations. Console files, warmup, before/after snapshots and unit-test output are kept alongside them. `negative-checks.json` describes real missing-context and existing-file tests.

## Limitations

Only one short run per condition was performed. Latency was higher with the observer; the comparison cannot establish negligible overhead or attribute this difference reliably. Repeat paired checks before increasing load. Resource series refresh less often than polls, and each API read has its own time window. k6 metric timestamps normally describe completion of the metric emission; correlated per-request start/outcome records remain future work. CPU/memory observations do not prove cost or energy savings. No pilot rate selection or autoscaling experiment was performed.

The earlier `../observation-check-2026-10-16/` run omitted Deployment records because the initial implementation filtered Deployment metadata using the pod label selector. Its artifacts were preserved; this corrected run supersedes it.

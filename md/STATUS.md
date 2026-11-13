# Project status

Updated: 2026-11-13. I completed the 18-run main v1.1 series and the separate nine-run controlled peak-12 comparison. Findings and the reproduction check are documented. All 24 roadmap steps are complete under their recorded criteria; Portflow submission still needs confirmation. The latest maintenance task, [test coverage and status cleanup](plans/test-coverage.md), is complete.

## Completed main v1.1 comparison

All 5,189 requests across 18 runs succeeded, with no dropped or unfinished requests. All modes met the agreed targets at peak 8 requests/10 s, including fixed one. HPA scaled, but this series did not show that extra copies were needed. The [combined analysis](../results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/README.md) owns the tables, plots and validation; the [series record](../results/main/series-2026-10-25-v1.1/README.md) retains the pause and restart history.

## Completed controlled peak-12 comparison

I completed all nine accepted runs with the same burst profile. Fixed three met the peak targets in 2/3 repetitions and had no peak errors. Fixed one and HPA met them in 0/3. HPA reduced peak failures from 698 to 89 out of 1,080 requests per mode, but missed the five-second successful-response p95 target in every repetition. All HPA runs grew to three copies and later reduced capacity. See the [comparison report](../results/follow-up/comparison-20261110-205108-peak12/README.md) for values and timing.

The comparison had two interruptions after valid load: an assessment-format mismatch and missing rotated log records. I corrected the assessment adapter and recovered 25 records into a separate derived attempt 07. The original failed attempt remains intact. The [recovery report](../results/follow-up/comparison-20261110-205108-peak12/LOG_RECOVERY.md) and [continuation plan](plans/peak12-resume.md) record the checks and collector-version boundary. The [earlier stopped comparison](../results/follow-up/comparison-20261110-192050-peak12/manifest.json) is also preserved.

## Pilots and preliminary checks

The original pilot selected 2/8 requests per 10 s. Its severe slowdown did not recur in the main series or in the wait/no-wait diagnostic pair. Two later completed pilots selected 2/12, with different timeout severity. I retain the interrupted search and both completed pilots. The [discrepancy note](PILOT_MAIN_DISCREPANCY.md) owns this history and its evidence links; the original physical cause remains unresolved.

### Completed prepared HPA check at peak 12

The separate [preliminary HPA burst](../results/autoscaling/check-20261028-181713-peak12/README.md) collected valid data and restored one copy after scaling. It missed the latency target. The [fixed-three preliminary check](../results/fixed-replicas/check-20261027-203849-peak12/README.md) used steady traffic, so these two checks are not a matched comparison. The later controlled nine-run comparison supplies that evidence. Startup failures and raw records remain preserved.

## Implementation and verification

The benchmark prepares each mode, archives inputs, collects request and cluster records, checks collection, and produces assessments and plots. A target miss is separate from invalid or incomplete evidence. Missing CPU coverage stays visible. The [architecture](ARCHITECTURE.md), [scaling procedure](plans/scaling-experiment.md), [collection plan](plans/measurements-and-pilot.md) and [benchmark review fixes](plans/bench-review-fixes.md) own implementation details and historical verification.

Inference Lab has Runs and Results tabs, configurable single-pilot settings, continuation of an existing main v1.1 series, saved plots and per-run/series notes. Results distinguish collection failure from a target miss and retain recovered and original attempts separately. Saved-data browsing and dry-run paths have local checks. Live experiment launch through the UI remains unverified. See the [UI plan](plans/inference-lab.md) and [setup guide](GETTING_STARTED.md#inference-lab).

The [test review](plans/test-coverage.md) added UI backend tests to root discovery and inexpensive browser checks. All 210 Python tests and five browser tests passed. The tests use temporary files, simulated cluster observations and local HTTP fixtures; they do not establish current cluster readiness.

## Documentation and reproduction

Research v0.10 and its PDF include the measured SQ4 answer and controlled overload comparison. I aligned the Notion findings, experiment log, pilot results, technology decisions and PDP with this evidence. Current sources and editing ownership are in [docs/README.md](../docs/README.md). The editable FigJam C1/C2/C3 views describe the prototype; older exported diagrams and course documents remain historical.

The [step-24 check](../results/reproduction/check-2026-11-06/README.md) passed from a clean clone and new Minikube profile on the same Windows host, including a short live check and saved main-analysis replay. This is a fresh-setup check, not reproduction by another person or on another machine.

## Remaining work and limits

- I still need to confirm submission of the current evidence to Fontys Portflow.
- All copies share one computer. Fixed one has 2 CPU available and fixed three up to 6; this is not an equal-CPU-budget comparison.
- Complete application CPU totals are unavailable for the main HPA runs. Resource gaps, sampled replica timing and model warmup limit the interpretation; I do not claim energy or cost savings.
- Successful-response p95 excludes failures and timeouts. I report those outcomes separately, alongside dropped and unfinished requests. Pod Ready does not establish that its model is warm, and native logs do not prove normal server drain.
- Saved evidence does not prove that Docker, Kubernetes or the model is running now. Runtime checks are required before any separately authorized experiment.

The planned measurements are complete. The optional [custom-metric HPA extension](plans/custom-metric-hpa.md) now has an installed Envoy 1.35.0 -> Prometheus 3.5.0 -> Adapter 0.12.0 -> Custom Metrics API chain in ai-lab. The [installed-chain check](../results/custom-metric/cluster-check-20261113-160100/README.md) passed three controlled requests, observed 0 -> 3 -> 2 -> 1 -> 0, verified source freshness and matched all gateway request IDs. Two fresh zeros and the existing backend CPU quiet gate passed afterward. I preserved the first checker failure and fixed its handling of Adapter's core API version `/v1`; all 16 focused tests passed. Read-only live PromQL checks suppressed stale/missing sources. Real configurations and image IDs are archived in the report.

I added opt-in launcher/cleanup integration, continuous signal and gateway-log collection, raw-signal replay and the separate two-target preparation driver. All 240 Python tests passed before launch. Historical integrity checks passed. [Both authorized preparations](../results/custom-metric/preparation-20261113-165340/README.md) completed with valid collection and cleanup. Both thresholds qualified for scaling; target 1 missed the latency goal, while target 2 met it. The predeclared smallest-qualifying rule selected target 1, not the better observed latency. I preserve this difference explicitly.

A review-only `protocol_version` mismatch stopped progression after the first valid load. I preserved the stop, corrected only the derived assessment view, passed 31 focused tests and replayed the first run, then continued target 2 without repeating load. The preparation's final live check confirmed no HPA or load generator, one Ready Ollama copy, and three Ready metric-stack components without restarts.

The final full suite passed all 241 tests. Its preceding run exposed intermittent timing failures in the existing accelerated HPA fixture; the unchanged test then passed separately and in the full repeat. Both suite outputs and the test limitation are retained in the preparation report. Final historical integrity checks passed.

## Active CPU/request HPA comparison

The [first comparison](../results/custom-metric/comparison-20261113-180650/README.md) stopped with 0/6 accepted runs. Its first CPU load was interrupted after 404 of 782 seconds when Prometheus time was about 0.78 seconds ahead of Windows. I preserve the partial run, 29 unfinished client requests, original manifest and archived sources.

The [clock correction](../results/custom-metric/clock-fix-20261113/README.md) passed 254 Python tests, six browser tests, both archived preparation replays and installed collection/cleanup checks. I use the same bounded one-second clock allowance as preflight, retain the ten-second source-age limit, and save query time bounds. Five installed zero samples included a simulated -0.8-second observer offset. Cleanup passed; 245 protected files were unchanged.

I launched [comparison v2](../results/custom-metric/comparison-20261113-192512/README.md) at 19:25:13 UTC (20:25 Berlin) on 13 November. I verified the exact command lines of launcher PID 24292 and actual interpreter/driver PID 42856 against this new directory. The startup snapshot recorded attempt 01 CPU in recovery quiet with no errors and 0/6 completed. Both arms keep the same infrastructure, CPU 60% versus request target 1, in CPU/custom, custom/CPU, CPU/custom order. The new driver archives and requires the exact verified collector-version boundary. I leave it unattended after startup and do not create more checks.

Results now has a Custom metrics group with an editable folder description and preserved attempt/series notes. I verified it in the live UI. Historical comparisons retain their data and settings. External OpenCode review remained blocked by access to its log file; verification was local.

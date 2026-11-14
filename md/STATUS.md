# Project status

Updated: 2026-11-14. I completed the 18-run main v1.1 series and the separate nine-run controlled peak-12 comparison. Findings and the reproduction check are documented. All 24 roadmap steps are complete under their recorded criteria; Portflow submission still needs confirmation. The latest maintenance task, [test coverage and status cleanup](plans/test-coverage.md), is complete.

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

Research v0.11 and its PDF include the measured SQ4 answer and controlled overload comparison. I aligned the Notion findings, experiment log, pilot results, technology decisions and PDP with this evidence. Current sources and editing ownership are in [docs/README.md](../docs/README.md). The editable FigJam C1/C2/C3 views describe the prototype; older exported diagrams and course documents remain historical.

The [step-24 check](../results/reproduction/check-2026-11-06/README.md) passed from a clean clone and new Minikube profile on the same Windows host, including a short live check and saved main-analysis replay. This is a fresh-setup check, not reproduction by another person or on another machine.

## Remaining work and limits

- I still need to confirm submission of the current evidence to Fontys Portflow.
- All copies share one computer. Fixed one has 2 CPU available and fixed three up to 6; this is not an equal-CPU-budget comparison.
- Complete application CPU totals are unavailable for the main HPA runs. Resource gaps, sampled replica timing and model warmup limit the interpretation; I do not claim energy or cost savings.
- Successful-response p95 excludes failures and timeouts. I report those outcomes separately, alongside dropped and unfinished requests. Pod Ready does not establish that its model is warm, and native logs do not prove normal server drain.
- Saved evidence does not prove that Docker, Kubernetes or the model is running now. Runtime checks are required before any separately authorized experiment.

## CPU/request HPA comparison

I retired the [13 November series](../results/custom-metric/comparison-20261113-192512/README.md) with four accepted cells. CPU cell 5 failed five times; cell 6 never started. All attempts remain saved. The last failure recorded a 1.384-second clock difference. The Hyper-V clocksource did not prevent it; the physical cause remains unresolved.

The active [reliability plan](plans/clock-and-run-reliability.md) adds a monotonic request timer, paired observer clocks, shared experiment ownership and recovery-baseline reuse. New preparation and all six comparison cells will run in a new directory. I will not combine them with the old four. The one-second clock bound remains strict.

Verification passed: 288 Python tests, six browser tests, unchanged replay of the old four cells and 33 live idle observations over three minutes. The [verification record](../results/custom-metric/clock-check-20261114-final/verification.json) records the scope. These checks do not prove that the host clock problem is permanently fixed. No new model load had started at this checkpoint.

The [Notion experiment log](https://app.notion.com/p/417c7c697bfd8049a916f48c59ff1e75) was updated earlier on 14 November with the stopped retry history. The new timing implementation and fresh startup are not yet added there.

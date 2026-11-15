# Project status

Updated: 2026-11-15. I completed the 18-run main v1.1 series, separate nine-run controlled peak-12 comparison and six-run CPU/request HPA extension. Findings and the reproduction check are documented. All 24 roadmap steps are complete under their recorded criteria; Portflow submission still needs confirmation. The latest [custom-result review fixes](plans/custom-results-review.md) are complete.

## Completed main v1.1 comparison

All 5,189 requests across 18 runs succeeded, with no dropped or unfinished requests. All modes met the agreed targets at peak 8 requests/10 s, including fixed one. HPA scaled, but this series did not show that extra copies were needed. The [combined analysis](../results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/README.md) contains the tables, plots and validation; the [series record](../results/main/series-2026-10-25-v1.1/README.md) keeps the pause and restart history.

## Completed controlled peak-12 comparison

I completed all nine accepted runs with the same burst profile. Fixed three met the peak targets in 2/3 repetitions and had no peak errors. Fixed one and HPA met them in 0/3. HPA reduced peak failures from 698 to 89 out of 1,080 requests per mode, but missed the five-second successful-response p95 target in every repetition. All HPA runs grew to three copies and later reduced capacity. See the [comparison report](../results/follow-up/comparison-20261110-205108-peak12/README.md) for values and timing.

The comparison had two interruptions after valid load: an assessment-format mismatch and missing rotated log records. I corrected the assessment adapter and recovered 25 records into a separate derived attempt 07. The original failed attempt remains intact. The [recovery report](../results/follow-up/comparison-20261110-205108-peak12/LOG_RECOVERY.md) and [continuation plan](plans/peak12-resume.md) record the checks and collector-version boundary. The [earlier stopped comparison](../results/follow-up/comparison-20261110-192050-peak12/manifest.json) is also preserved.

## Pilots and preliminary checks

The original pilot selected 2/8 requests per 10 s. Its severe slowdown did not recur in the main series or in the wait/no-wait diagnostic pair. Two later completed pilots selected 2/12, with different timeout severity. The interrupted search and both completed pilots remain available. The [discrepancy note](PILOT_MAIN_DISCREPANCY.md) documents this history and links to its evidence; the original physical cause remains unresolved.

### Completed prepared HPA check at peak 12

The separate [preliminary HPA burst](../results/autoscaling/check-20261028-181713-peak12/README.md) collected valid data and restored one copy after scaling. It missed the latency target. The [fixed-three preliminary check](../results/fixed-replicas/check-20261027-203849-peak12/README.md) used steady traffic, so these two checks are not a matched comparison. The later controlled nine-run comparison supplies that evidence. Startup failures and raw records remain preserved.

<a id="implementation-and-verification"></a>

## Implementation

I refined the [C1-C4 architecture project in Architect](diagrams/architect/README.md) on 15 November. C1 contains the researcher, experiment and Kubernetes platform. In C3, Analysis + comparisons points to Saved results reader with `Reads saved assessment`. C4, now called `Detailed code map`, covers all 34 production Python modules and 14 classes, browser/workload JavaScript and the Go timer. I removed external library cards and limited method rows to architectural operations. The diagram index links the validated models and PNG/SVG exports at revisions 3, 2, 2 and 7.

The benchmark prepares each mode, archives inputs, collects request and cluster records, checks collection, and produces assessments and plots. A target miss is separate from invalid or incomplete evidence. Missing CPU coverage stays visible. The [architecture](ARCHITECTURE.md), [scaling procedure](plans/scaling-experiment.md), [collection plan](plans/measurements-and-pilot.md) and [benchmark review fixes](plans/bench-review-fixes.md) own implementation details and historical verification.

Inference Lab has Runs and Results tabs, configurable single-pilot settings, continuation of an existing main v1.1 series, saved plots and per-run/series notes. Results distinguish collection failure from a target miss and retain recovered and original attempts separately. Saved-data browsing and dry-run paths have local checks. Live experiment launch through the UI remains unverified. See the [UI plan](plans/inference-lab.md) and [setup guide](GETTING_STARTED.md#inference-lab).

The [test review](plans/test-coverage.md) added UI backend tests to root discovery and inexpensive browser checks. All 210 Python tests and five browser tests passed. The tests use temporary files, simulated cluster observations and local HTTP fixtures; they do not establish current cluster readiness.

## Documentation and reproduction

On 15 November I reviewed all ten project-related Notion pages, clarified historical preparation and startup checkpoints, and updated the PDP extension, main-protocol scope and local setup labels. Preparation previews now show parent Notes. Existing plots cover both fresh preparations and all six comparison runs; reproducible PNG/SVG overviews show preparation and paired policy outcomes separately. The local Python and Edge browser checks passed. See the [follow-up record](plans/custom-results-review.md#notes-and-documentation-follow-up).

Research v0.12 (15 November 2026) and its PDF include the measured SQ4 answer, controlled overload comparison and separate six-run CPU/request comparison. The Notion findings, general and custom-metric logs, technology decisions and research outline now include this completed extension. Earlier pilot and PDP records remain separate. Current sources and editing locations are listed in [docs/README.md](../docs/README.md). The editable FigJam C1/C2/C3 views describe the prototype; older exported diagrams and course documents remain historical.

The [step-24 check](../results/reproduction/check-2026-11-06/README.md) passed from a clean clone and new Minikube profile on the same Windows host, including a short live check and saved main-analysis replay. This is a fresh-setup check, not reproduction by another person or on another machine.

## Remaining work and limits

- I still need to confirm submission of the current evidence to Fontys Portflow.
- All copies share one computer. Fixed one has 2 CPU available and fixed three up to 6; this is not an equal-CPU-budget comparison.
- Complete application CPU totals are unavailable for the main HPA runs. Resource gaps, sampled replica timing and model warmup limit the interpretation; I do not claim energy or cost savings.
- Successful-response p95 excludes failures and timeouts. I report those outcomes separately, alongside dropped and unfinished requests. Pod Ready does not establish that its model is warm, and native logs do not prove normal server drain.
- Saved evidence does not prove that Docker, Kubernetes or the model is running now. I check the runtime before starting another experiment.

## CPU/request HPA comparison

I retain the [13 November series](../results/custom-metric/comparison-20261113-192512/README.md) with four accepted cells and five failed CPU-cell-5 attempts. Cell 6 never started. The later [16:05 cycle](../results/custom-metric/series-20261114-150236/README.md) also stopped, at 16:38 Berlin on 14 November: target 1 passed collection and cleanup, target 2 failed the clock check, and no comparison cell started.

The later journal investigation correlates all four clock failures with Ubuntu systemd-timesyncd initial synchronization. The last measured clock step was about +1.548 seconds. Monotonic request timing remains useful but does not fix this separate host/guest clock conflict.

The [evening series](../results/custom-metric/series-20261114-191048/README.md) completed both fresh preparations and all six comparison cells at 23:24:35 Berlin on 14 November. The predeclared rule selected target 1. Active-request HPA improved peak on-time success in all three pairs without increasing errors, but met the service targets in only 1/3 runs; CPU met them in 0/3. The result report contains the values, source records and capacity tradeoff. These results are separate from the old four accepted cells and the afternoon preparation.

The background process restored Ubuntu synchronization to enabled/active and exited successfully. The temporary guard prevented the observed failure during this cycle; it is not a permanent clock fix or proof of absolute UTC accuracy. The [reliability plan](plans/clock-and-run-reliability.md) retains the investigation, pre-load failures and restoration evidence. The one-second clock bound and ten-second freshness bound remain unchanged.

The [review-fix plan](plans/custom-results-review.md) records the completed corrections to policy comparison, unfinished-run status, registry persistence and documentation. Python and browser checks passed, and recalculating both preparations and all six comparison assessments reproduced the saved results. Result previews, the policy table and the Research PDF were also checked.

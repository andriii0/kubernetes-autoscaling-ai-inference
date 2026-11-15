# Completed CPU/request HPA comparison

I completed fresh target preparation and all six accepted comparison runs on 14 November 2026. The worker finished at 23:24:35 Berlin with exit code 0, no recorded errors, successful cleanup and Ubuntu time synchronization restored to enabled/active. A valid result can still miss the response targets.

## Results

| Run / pair | HPA policy | Peak success within 5 s | Peak errors | Successful peak p95, s | Targets | Evidence |
|---|---|---|---|---|---|---|
| 01 / 1 | CPU 60% | 37/360 | 86/360 | 28.912 | fail | [attempt-01-cpu](comparison-new/attempt-01-cpu/metadata.json) |
| 02 / 1 | Active requests 1 | 296/360 | 0/360 | 6.978 | fail | [attempt-02-active-1](comparison-new/attempt-02-active-1/metadata.json) |
| 03 / 2 | Active requests 1 | 345/360 | 0/360 | 4.820 | pass | [attempt-03-active-1](comparison-new/attempt-03-active-1/metadata.json) |
| 04 / 2 | CPU 60% | 95/360 | 59/360 | 28.355 | fail | [attempt-04-cpu](comparison-new/attempt-04-cpu/metadata.json) |
| 05 / 3 | CPU 60% | 41/360 | 49/360 | 28.322 | fail | [attempt-05-cpu](comparison-new/attempt-05-cpu/metadata.json) |
| 06 / 3 | Active requests 1 | 262/360 | 0/360 | 11.361 | fail | [attempt-06-active-1](comparison-new/attempt-06-active-1/metadata.json) |

Each run started and completed 457 requests, including 360 starts in the 300-second peak. There were no dropped or unfinished requests. All peak errors were timeouts. The p95 excludes errors; the on-time fraction includes every peak start in its denominator.

Across the three CPU runs, 173/1,080 peak requests succeeded within five seconds (16.0%) and 194/1,080 failed (18.0%). Across the request-policy runs, 903/1,080 succeeded within five seconds (83.6%) and none failed. CPU met the targets in 0/3 runs; the request policy met them in 1/3. Run-level successful peak p95 ranged from 28.322 to 28.912 seconds for CPU and 4.820 to 11.361 seconds for requests. These are ranges of individual run p95 values, not pooled percentiles.

The paired on-time improvements were +71.944, +69.444 and +61.389 percentage points, without an increase in errors in any pair. This meets the predeclared descriptive improvement rule. Three pairs do not establish statistical significance or a guarantee that the request policy meets the latency target.

Three Ready copies were first observed 215.39–220.36 seconds after peak start with CPU, versus 20.12–25.02 seconds with the request policy. Ready does not mean the model is warm. Over the three 782-second load windows per arm, sampled Ready capacity totals were 5,357.27 replica-seconds for CPU and 5,797.40 for requests (+8.2%). This measures capacity over time, not consumed CPU, energy or cost. Full application CPU totals are unavailable where source coverage is incomplete. All copies share one computer.

## Preparation and common conditions

Fresh target-1 and target-2 preparation both passed collection, cleanup and the declared scaling qualification. Their successful peak p95 values were 16.409 and 26.167 seconds, with zero and nine peak errors respectively. The predeclared rule selects the smallest qualifying target, so I retained target 1; it does not select the fastest observed latency. These preparations are separate from the six comparison runs.

Both arms used the same Envoy route, Prometheus/Adapter infrastructure, model, workload, 2-CPU limit per replica and 1–3 replica bounds. CPU retained its 60% target. The request policy used one active client request per replica. The gateway count is not Ollama's internal queue. The burst was 2 → 12 → 2 requests per 10 seconds, over 782 seconds, with 300 seconds of post-load observation. Targets were successful peak p95 ≤5 seconds and peak errors ≤1%, with no dropped or unfinished work.

The six runs retained identical archived source hashes. Every run passed the recorded gateway, collection and cleanup checks. Source sampling remained five seconds, maximum permitted source age ten seconds, and the clock allowance one second. See the [manifest](comparison-new/manifest.json), [paired summary](comparison-new/comparison-summary.json), [fresh preparation](preparation-new/manifest.json) and [workflow](workflow.json). The [comparison overview plot](comparison-new/primary-p95.png) and [preparation overview plot](preparation-new/primary-p95.png) are derived from these saved summaries; each run also retains its own PNG/SVG analysis plot. Each run archives the source and analysis files used for its measurements.

## Clock environment and preserved history

Preparation began at 20:14:37 Berlin after 36 strict clock observations over three minutes passed; comparison began at 21:02 Berlin. The independent Windows task was AI-Inference-Fresh-20261114-191048. Its worker temporarily masked Ubuntu systemd-timesyncd while keeping Ubuntu alive. Docker/WSL host-relative synchronization remained active. The worker restored the prior enabled/active service state on exit. This was a temporary experiment condition, not proof of permanent clock repair or absolute UTC accuracy.

The launch used the monotonic timing implementation and hidden Windows child-process windows. Verification before launch passed 154 focused tests. See [verification](../launch-20261114-191048/verification.json), [startup](../launch-20261114-191048/startup.json) and [worker](../launch-20261114-191048/worker.json).

The [retired four-cell series](../comparison-20261113-192512/README.md), [stopped afternoon cycle](../series-20261114-150236/README.md) and pre-load failures remain separate. I did not pool their measurements with these six cells. The older fixed/CPU peak-12 comparison used a different request path and timing environment; its CPU error count is context, not a matched causal comparison with this series.

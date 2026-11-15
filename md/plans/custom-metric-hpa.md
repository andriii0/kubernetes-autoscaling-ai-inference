# Custom-metric HPA comparison

Status (15 November): the [fresh evening series](../../results/custom-metric/series-20261114-191048/README.md) completed both preparations and all six accepted cells. Active-request HPA met the paired improvement rule, but passed service targets in 1/3 runs versus CPU 0/3. The earlier stopped cycles remain separate. The [reliability plan](clock-and-run-reliability.md) documents timing and restoration; the clock guard remains strict. The checkpoints and recovery sections below are historical records through the last old-series failure, not current progress. The preparation and outcome rules remain the declared procedure.

## Implementation checkpoint

Envoy, Prometheus and Prometheus Adapter are installed. The launcher supports both policies through the same gateway, continuous source and access-log collection, source freshness checks, cleanup and archived-input verification. The preparation and six-cell drivers and comparative analysis are implemented.

Both threshold preparations passed collection, cleanup and the declared scaling check. Target 1 missed the latency target; target 2 met it. The predeclared rule selected target 1. The [preparation report](../../results/custom-metric/preparation-20261113-165340/README.md) retains the results, assessment correction and tests.

The [container check](../../results/custom-metric/container-check-20261113-b4116a3d/README.md) and [installed-chain check](../../results/custom-metric/cluster-check-20261113-160100/README.md) retain the functional verification and failed setup attempts. The [clock correction](../../results/custom-metric/clock-fix-20261113/README.md) introduced a bounded one-second allowance while keeping the ten-second source-age limit. It passed 254 Python tests, six browser checks and installed idle/cleanup checks. It does not admit a larger clock difference.

## Comparison and interruption history

The [first comparison](../../results/custom-metric/comparison-20261113-180650/README.md) stopped on the earlier clock check with no accepted cells. The separate [comparison v2 report](../../results/custom-metric/comparison-20261113-192512/README.md) documents the four accepted results, the kubectl crash, the application interruption and the latest pre-load stop. Target misses count as valid results when collection is complete.

Explicit continuation revalidates the accepted prefix against archived inputs, preserves the previous manifest and writes each replacement to a separate retry directory. It rejects workload and collector changes. Only comparison-driver and archived-review-helper changes may be recorded at continuation. Its original verification passed 51 focused and 263 full Python tests; the later interruption recovery passed 17 continuation tests. The report links those outputs.

The Windows task launch was independent of Codex: the saved process ancestry reaches the Schedule service. The task used Limited privileges, no triggers and no automatic restarts. It finished after the clock failure and deleted itself. The check after that failure found no experiment process or HPA. The subsequent valid cleanup and new continuation are recorded below.

## Recovery check on 14 November

The saved clock bounds changed abruptly between 23:04:01 and 23:04:06 UTC on 13 November. Prometheus was then about 1.015 seconds ahead of the Windows receive time. Live clocks were aligned again before I changed any clock setting. I could not establish the underlying host/guest trigger from the available logs. I did not change system clocks, restart the infrastructure, weaken the one-second guard or modify collectors.

Before launch, 36 idle observations over three minutes passed, followed by the existing backend CPU quiet and two fresh gateway-zero checks. All 53 focused tests passed. The accepted-prefix replay retained cells 1-4 and listed only cells 5-6. All 596 pre-existing non-Markdown series files matched their saved hashes before launch; the continuation intentionally updates the manifest and keeps its previous version in the resume directory.

At 2026-11-13T23:47:28.942016+00:00, the continuation was running with four of six cells accepted. `attempt-05-cpu-retry-03` had reached measured CPU load: 11 requests started and 10 completed. The final active-1 cell follows only if the CPU cell passes full collection and cleanup. This snapshot confirms load startup, not either remaining result. The [recovery record](../../results/custom-metric/comparison-20261113-192512/resume-check-clock-20261114/README.md) contains the evidence.

## Repair after retry 03

Retry 03 stopped during load at 23:48:56 UTC on 13 November after 19 completed requests. The clock offset exceeded one second again; cleanup passed. The three-minute idle check did not establish a lasting fix. No fifth or sixth result is accepted.

I repaired continuation between cells and the Results treatment of superseded attempts, with regression tests. The trace did not establish the physical trigger of the clock jump. The temporary Hyper-V clocksource is a provisional mitigation. Workload and collectors remain unchanged; the four accepted results passed replay before the new continuation.

## Recovery after the host reboot on 14 November

The host rebooted after the stopped retry 03. Docker and ai-lab were stopped when work resumed. All three metric containers restarted when the existing cluster was restored. I will archive that state and renew only those pods under the unchanged Deployment specifications. I will record their old and new identities explicitly; every image digest, stack configuration, node resource limit, backend configuration and model digest must still match preparation.

The comparison driver may use this explicit instance-renewal record only on continuation between complete pairs. It must reject an unrecorded identity change. The collector remains unchanged and continues to reject any restart or identity change within a run. The first four results remain intact; both cells in pair 3 will share the recovered environment. This adds a session boundary to report with the final comparison, not a new target-selection opportunity.

Verification passed: all 269 Python tests, 60 idle observations over five minutes, full cleanup, four-cell replay and 737 unchanged protected files. At 2026-11-14T12:05:07.884164+00:00, the independent continuation was running `attempt-05-cpu-retry-04` in measured CPU load with four of six cells accepted. 44 requests had started and 38 had completed, more than two minutes after the first measured request, with no recorded collection errors. The active-1 cell follows only after this CPU cell passes full load, post-load, collection and cleanup checks. This confirms startup, not an accepted fifth result. The [repair record](../../results/custom-metric/comparison-20261113-192512/resume-repair-20261114/README.md) contains the evidence.

## Latest failure and protocol boundary

The series stopped again at 12:12:00 UTC (13:12 Berlin) on 14 November. Attempt 05 retry 04 recorded 393 started and 392 completed requests, with no summary. The clock guard failed again; the saved observation near 12:10:30 UTC shows Prometheus about 1.384 seconds ahead of the Windows receive time. Full cleanup passed. Four cells remain accepted; cell 6 never started.

The Hyper-V clocksource was still selected at the subsequent runtime check, so the mitigation did not prevent recurrence. No experiment process or continuation task remained; HPA was absent and one Ollama copy was Ready. No new load was started. The cause of the clock jump remains unresolved.

The host recovery changed instance identities, the timing environment and the continuation procedure. The first four runs retain their own validated evidence, but matching images/configuration alone does not establish that a later recovered pair forms an unchanged six-cell protocol. The original frozen-configuration rule requires an explicit decision about that boundary. I must resolve it, together with the clock failure, before treating further runs as the final comparison. A fresh complete series under stable settings is the conservative option; it has not been launched.

## Historical remaining work after the old-series stop

1. Clock alignment and the existing backend quiet/fresh-zero checks passed before continuation. Keep the one-second allowance and ten-second source-age limit; stop if the discrepancy recurs. Its underlying trigger remains unproven.
2. The independent task has exited. Do not infer authorization for another retry from its earlier startup; resolve the clock failure and continuation boundary first. Use separate attempt folders. Preserve the four accepted cells and every failed attempt. Keep the model, resources, collectors, workload, targets and observation interval unchanged.
3. Accept a cell only after full load, post-load, collection and cleanup checks pass. Stop on invalid evidence; do not automatically replace a failed run.
4. Review all six accepted outcomes together under the predeclared rule below. Keep startup confirmation separate from run acceptance.

The continuation now handles a preflight failure after accepting a cell without repeating its load. A regression test covers this state. Results retains superseded failed attempts but excludes them from the completion verdict when an accepted replacement exists. All 267 Python tests passed after the changes; only the test fixture sampling interval changed from 50 to 200 ms. The real sampling interval remains five seconds.

The [documentation correction plan](notion-evidence.md#review-corrections-2026-11-14) covers current wording, Notion, Research and preservation of preparation errors. It does not change the experiment or start another attempt.

## Small research and choice

I reviewed the official sources below on 13 November 2026. My choice is **request concurrency measured at an Envoy gateway, exposed through Prometheus Adapter to the existing Kubernetes HPA**. I keep Minikube and Ollama. This is a suitable architecture for a focused extension, not a verified two-day delivery estimate or a claim that it is the best serving platform in general.

I used four criteria: relevance to accumulating work, availability without changing model serving, preservation of the CPU-HPA comparison, and implementation/verification effort.

### What Google and AWS document

- **AWS SageMaker** supports `ConcurrentRequestsPerModel` and `ConcurrentRequestsPerCopy` as high-resolution scaling metrics. They include requests queued inside model containers and track streaming requests through the last token; updates are published every 10 seconds. This supports concurrency as a practical inference scaling signal. My gateway counter will not have exactly the same scope as SageMaker's container metric. [AWS scaling policies](https://docs.aws.amazon.com/sagemaker/latest/dg/endpoint-auto-scaling-add-code-define.html)
- **Google GKE** recommends model-server queue size for throughput-oriented scaling and batch size for tighter latency goals. Its guide also says CPU metrics are normally relevant to CPU workloads. Its GPU/continuous-batching examples do not establish that CPU is a bad signal for my CPU-only Ollama setup. I borrow the idea of measuring outstanding work, not Google's numerical thresholds. [GKE inference autoscaling](https://docs.cloud.google.com/kubernetes-engine/docs/best-practices/machine-learning/inference/autoscaling)
- **Google Cloud Run** uses request concurrency alongside CPU as scaling inputs. It is a separate managed platform, not the same algorithm or runtime as my local HPA. [Cloud Run autoscaling](https://docs.cloud.google.com/run/docs/about-instance-autoscaling)

### Metric comparison

| Candidate | What it tells me | Decision for this extension |
|---|---|---|
| CPU utilization | How busy the allocated CPU is | Keep as the comparison policy. It is already implemented and relevant to this CPU workload. |
| Active requests at the gateway | How many HTTP requests have arrived and remain active | Select. It observes demand before those requests finish and does not require replacing or modifying Ollama. |
| Internal waiting queue | How many requests are waiting rather than executing | A useful inference signal, but my pinned deployment has no verified exporter for it. I will not invent queue length by subtracting replica count from gateway concurrency. |
| Requests per second | Arrival rate | Easy to interpret, but the same rate can be cheap or expensive depending on processing time. Concurrency also reflects requests remaining active longer. |
| TTFT: time to first token | How long the client waits for the first generated token | Useful as an outcome for a streaming service, but not selected as this experiment's control signal. My current non-streaming workload does not measure it. |
| End-to-end p95 | Tail response latency | Retain as an outcome. It is based on completed requests and needs enough samples; changing the control signal does not require changing this target. |
| Batch size, GPU/KV-cache usage | Model-server batching or accelerator pressure | Poor fit for the current CPU setup with `OLLAMA_NUM_PARALLEL=1`. Changing the server/hardware would broaden the experiment. |

These selections are my engineering judgement, informed by the vendor guidance and the actual project configuration. A request counter can react to accumulating work; whether it improves this burst is the question to measure.

### Why I am not adding TTFT now

`bench/workload.json` explicitly sets `stream: false`, and `bench/inference.js` reads one completed JSON response. Ollama supports streaming NDJSON, but measuring client TTFT would require enabling streaming and recording receipt of the first non-empty generated text chunk. HTTP headers, time to first byte, model-load duration and the full response duration are not interchangeable with TTFT. [Ollama streaming](https://docs.ollama.com/api/streaming)

That would change the client/response contract in both arms and require new event validation. TTFT could then be an extra outcome, alongside total latency and failures. I would not substitute a first-token target for the existing five-second full-response target, or estimate historical TTFT from saved non-streaming responses. For this short extension I keep the current workload and focus on the scaling signal.

### Platform and integration comparison

| Option | Fit and tradeoff | Choice |
|---|---|---|
| Existing Kubernetes HPA + Prometheus Adapter | Keeps the same HPA controller and explicit HPA manifest. Needs Prometheus and resource-to-metric mapping, but no new scaling controller. | Select. It gives the narrowest policy comparison within this repository. |
| KEDA + Prometheus scaler | A valid alternative: KEDA exposes the signal and manages an HPA. It supports thresholds and HPA behavior settings, but adds ScaledObject ownership and another controller to lifecycle/cleanup. | Do not add it for this single metric. It becomes more attractive if I later need several event sources or scale-to-zero. |
| KEDA HTTP Add-on | Supplies HTTP interception and scaling integration without writing a gateway. The project currently describes itself as beta; its request handling and lifecycle would need verification too. | Useful alternative, but not my first choice for a short controlled change to an existing plain Deployment/HPA experiment. Beta status alone is not evidence that it is unreliable. |
| Knative Serving | Supports concurrency/RPS through its default KPA autoscaler and adds a serving abstraction around the workload. | Too broad here: it changes more than the HPA signal and request instrumentation. |
| Cloud Run or SageMaker | Managed alternatives with documented request-aware scaling. | Use as research references, not a migration target. Changing hardware and platform would prevent isolating this local HPA policy change. |

Sources: [Kubernetes HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/), [Prometheus Adapter](https://github.com/kubernetes-sigs/prometheus-adapter), [adapter mapping configuration](https://github.com/kubernetes-sigs/prometheus-adapter/blob/master/docs/config.md), [KEDA Prometheus scaler](https://keda.sh/docs/2.21/scalers/prometheus/), [KEDA HPA configuration](https://keda.sh/docs/2.21/reference/scaledobject-spec/), [HTTP Add-on status](https://github.com/kedacore/http-add-on), [Knative metrics](https://knative.dev/docs/serving/autoscaling/autoscaling-metrics/).

For the gateway I choose **Envoy rather than a new proxy implementation**. Its HTTP connection manager exposes `downstream_rq_active`, a gauge of active requests, and its admin endpoint exports Prometheus metrics. I use one dedicated inference listener and keep admin/health traffic outside its counter. The saved container and installed-chain checks verify this configuration. [Envoy HTTP statistics](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_conn_man/stats), [Prometheus export](https://www.envoyproxy.io/docs/envoy/latest/operations/admin).

This changes the earlier upstream-operation proposal: the chosen metric counts **active client-facing requests at Envoy**. After a client disconnects, Ollama might still be computing, so this counter is not all remaining model work. I will record that limitation and test disconnect behavior before accepting the setup.

## Question and signal

I want to test whether HPA using outstanding inference requests adds capacity sooner and improves burst outcomes compared with my CPU policy.

The exposed metric is `inference_gateway_active_requests`: the total active client-facing requests on Envoy's dedicated inference listener. The verified Prometheus source is `envoy_http_downstream_rq_active` with `inference_listener="inference"`; scrape labels include the gateway pod UID. It is not a measurement of Ollama's internal queue or work remaining after a client disconnects.

I would use one Envoy replica before the existing Ollama Service. Prometheus would scrape its `/stats/prometheus` endpoint, and Prometheus Adapter would expose a custom Object metric associated with the gateway Service. The HPA would target the Ollama Deployment with `AverageValue`, expressing the desired active requests per Ollama replica. This must use the total gateway gauge, not an average per gateway pod, and must not count the same metric more than once.

I will consider only thresholds **1 and 2 active requests per replica**, using the preparation rule below. `OLLAMA_NUM_PARALLEL=1` does not establish either threshold as optimal. Ignoring controller tolerance and scaling constraints, a total of 6 active requests with target 2 would request 3 replicas. This illustrates the setting, not measured capacity or a vendor recommendation.

I would not use successful-response p95 as the control signal: it arrives after completions, needs a sampling window and excludes timeout failures. CPU, p95, errors and replica observations would still be collected under both policies.

## Common request and metric paths

```text
k6 -> Envoy -> existing Ollama Service -> Ollama pods
Envoy /stats/prometheus -> Prometheus -> Prometheus Adapter -> HPA -> Ollama Deployment
```

Both policies use the same gateway and running metrics stack. The CPU arm retains the 60% CPU-request utilization target. The custom arm uses only the selected active-request metric; combining CPU and custom signals would answer a different question.

### Request routing and proof

I will keep `ollama` as the backend Service and scaling target, and introduce a separate gateway Service as the client entry point. `runtime.service_url()` currently opens `minikube service ollama`, while `autoscaling.Session.prepare()` requires the backend Service to be `ollama`. I must separate the client entry point from the backend identity checks; replacing every service name with the gateway would break those checks.

The preparation driver opens a gateway tunnel and passes its URL as `--base-url`. The comparison must use the same route in both arms. Existing checks of Ollama selectors, endpoints, image and pod identity stay in place. Single-copy warmup uses that base URL through Envoy, remains labelled as preparation and is excluded from measured request counts. The counter must return to two fresh zeros before HPA activation.

For this experiment only, k6 will send its existing request ID in an HTTP header which Envoy logs. The same instrumentation is used in both arms. Archive the client URL, gateway configuration, backend Service/endpoints and access logs. Before comparison, reconcile each measured client request ID with exactly one gateway request record, check that forwarding uses only the Ollama backend, and retain upstream failure/reset fields. Verify no automatic retries. Keep native Ollama reconciliation as a separate backend check. A request that fails to reach Envoy is a transport outcome to explain, not an absent record to silently ignore.

The gateway must retain the request body, status and response, forward requests concurrently, avoid retries, and preserve the existing no-connection-reuse routing to Ollama. Envoy supports disabling upstream keep-alive with `max_requests_per_connection: 1`; I would verify this with HTTP/1.1 and per-pod traffic evidence. Existing per-pod warmup stays outside measured load. I would explicitly configure timeouts so the proxy does not introduce a shorter deadline than the existing 30-second client timeout. [Envoy protocol options](https://www.envoyproxy.io/docs/envoy/latest/api-v3/config/core/v3/protocol.proto)

The dedicated listener accepts only generation traffic. Client disconnects, upstream timeouts, cancellations and gateway restarts need explicit tests and timestamps. A zero gauge does not prove that Ollama has drained; retain the existing recovery/quiet gates. Missing or stale scrapes must produce unavailable metric evidence, not a fabricated zero. Keep the admin endpoint internal, collect gateway access logs, and reject a preparation run if the gateway restarts or becomes a bottleneck.

### Metric validity and admission checks

These rules were checked during preparation and frozen for the comparison:

- Scrape and observe every 5 seconds. Accept a source sample only when it is no more than **10 seconds old**, comes from the current gateway instance, and belongs to the dedicated inference listener. Save source scrape time and receipt time separately; a fresh adapter response timestamp must not hide an old Prometheus value. Check clock alignment before using this age rule.
- Require a healthy scrape target and exactly the expected series before aggregation. Missing, duplicate, negative, non-finite or stale values are errors, not zero. Do not use a query fallback that substitutes zero for missing series.
- Before activation, require two consecutive fresh zero samples after warmup and after the previous attempt's cleanup, plus the existing CPU quiet gates. Verify the adapter value against its source sample and require HPA to report the chosen metric and active scaling. Preserve the CPU arm's existing readiness checks.
- Test against a controllable HTTP backend: hold three requests open and observe a gauge of three; finish one and observe two; finish the rest and observe zero. Test HTTP errors, client cancellation, an upstream response longer than the client deadline, and a gateway restart. Exclude health/admin traffic and prove that requests are not retried.
- For a client timeout, save the gateway reset/completion and any later backend completion. Require the counter to follow active gateway requests correctly. Continued Ollama work is a recorded scope limitation, not evidence that the counter itself is wrong. Keep preparation blocked until the existing backend quiet checks pass.
- During either comparison arm, a source older than 10 seconds, failed metric mapping or gateway/metrics-component restart stops the attempt through normal cleanup and prevents the next launch. Preserve all data and label the policy comparison incomplete. Client measurements already collected may remain valid; they do not establish a complete comparison run. Do not silently resume, replace the run or feed a synthetic metric.

Freshness is enforced in the query/adapter path and in observation. The saved checks cover stale and missing values; any later violation stops the attempt.

### Bounded threshold preparation

After functional checks passed, I ran one separately saved prepared burst for target 1, then one for target 2. Both use the same 782-second 2 -> 12 -> 2 profile, 300-second post-load observation, infrastructure and clean-start rules as the comparison. These are two additional preparation runs, not part of the six comparative runs.

A candidate qualifies if collection and cleanup pass, HPA remains at one desired/Ready replica throughout the initial 120-second low phase, and during the peak it requests at least two replicas and a second replica becomes Ready before the peak ends. These are stability and mechanism checks; passing the five-second latency target is not a selection condition.

If both qualify, choose the smaller target; if only one qualifies, choose that target. If neither qualifies, stop this extension and report the result. Invalid collection or failed cleanup stops preparation for review rather than disqualifying a threshold on performance grounds. Keep all attempts. Do not add candidates or repeats to search for a better-looking result.

Freeze the chosen target, query, freshness rule, component versions/resources, timeout settings, sampling and HPA behavior before the comparative series. A later configuration change creates a new protocol revision and requires a new decision about the series; it cannot silently replace one of the six cells.

## Implementation responsibilities

I can keep Ollama, Qwen, generation settings, the k6 burst, latency/error formulas and existing backend log reconciliation. The new experiment adds request-ID forwarding and gateway reconciliation to both arms. I cannot obtain this signal simply by changing the current HPA threshold.

| Component | Implemented responsibility |
|---|---|
| Deployment | Pinned Envoy, Prometheus and Adapter configurations, bounded resources and separate CPU/custom HPA manifests. |
| Launcher and routing | Explicit policy selection and gateway routing, separate backend identity checks, request-ID forwarding and archived route configuration. |
| HPA readiness | The opt-in Object-metric readiness helper is connected to the extension session and has local tests. The original CPU readiness path remains available. Both preparation runs verified the complete lifecycle. |
| Observation and archive | Save Envoy access logs, raw gauge samples, source/scrape/receipt times, HPA-reported values, errors, policy and infrastructure hashes. Enforce the metric contract and retain existing CPU/memory and desired/Ready replica records. |
| Comparison driver | Reuse preparation, load, cleanup and analysis through a separate six-cell protocol. Do not overwrite or repurpose the completed nine-cell manifest or its source checks. |
| Analysis | Saved per-run successful p95/error assessments, on-time success fraction, sampled replica-seconds and signal, HPA-decision and Ready timelines. The final paired summary requires all six accepted cells. |
| Tests | Verify the configured gateway against concurrent success/error/cancellation, no retries and connection reuse; test counter reset, missing/stale metrics, metric readiness, policy archival and cleanup. Keep existing tests passing. |

I would not build a custom autoscaling controller or a custom Kubernetes metrics API server for this extension.

## Frozen comparison series

- Two policies, three repetitions each: CPU/custom, custom/CPU, CPU/custom. Record this order before starting.
- The same 2 -> 12 -> 2 requests/10 s burst: 120 s low, 1 s rise, 300 s peak, 1 s fall, 360 s low.
- Both use min 1/max 3, identical scale-up behavior and 300-second downscale stabilization, the same model and 2 CPU per Ollama copy, initial warmup and quiet gates, and 300 seconds of post-load observation.
- Use the 5-second sampling and 10-second source-age contract above. Record the actual metrics-server window, adapter query behavior and HPA sync interval before freezing settings; do not assume the two signal paths update equally quickly.
- Reset to one Ready, warmed copy before each run. Verify healthy metric collection, an empty gateway and completed prior work before the next attempt. Record preparation failures separately.
- Judge the peak using successful-response p95 <= 5 s and errors <= 1%, and retain the whole-run error check. Keep dropped/unfinished requests and collection validity separate from target attainment.
- Report all three results per arm using the outcome and timing rules below. Do not pool requests across repetitions and hide per-run differences.
- Existing Fixed-1/Fixed-3 evidence supplies context only. This new series answers which HPA policy performs better through this common request path; it does not make a new three-mode capacity comparison.

### Outcome and timing rules

I will retain the existing pass/fail targets. To compare the policies without letting successful-response p95 hide failures, I will also calculate:

- **Peak on-time success fraction:** successful requests with client duration <= 5,000 ms divided by all client requests started in the peak. Assign requests by start time, including late completions. Errors, timeouts and unfinished requests do not enter the numerator. Report dropped starts separately; a run with dropped/unfinished work cannot become a complete accepted comparison just because this fraction looks good.
- **Requested and Ready capacity over time:** sampled desired and Ready replica-seconds, plus time at 1, 2 and 3 replicas, over the same scheduled 782-second load window. Desired count is a request for capacity; Ready count excludes warming or unhealthy copies. Neither is exact allocated or consumed CPU. Report post-load separately. Integrate only covered intervals, disclose gaps and sampling uncertainty, and do not call replica-seconds measured CPU use, energy or cost.
- **Reaction stages for two and three replicas:** first observed metric value that calls for that capacity under the configured target, first observed HPA desired count reaching it, and first observed Ready count reaching it. Save raw times relative to peak start. A missing event stays missing; an event before peak is reported as such. Observation times are sampled bounds, not exact controller decision times. Ready still does not mean a loaded model.

Show the on-time fraction, errors/timeouts and successful p95 side by side for each repetition, with each arm's median and range. Show paired differences using the predeclared run pairs. I will describe a consistent service improvement only if the custom arm improves the on-time fraction in all three pairs without increasing peak error fraction in any pair. Otherwise I will report mixed or unchanged results rather than choose a winner from the best run. This is a descriptive rule for a small experiment, not a statistical significance claim. Any capacity increase is reported as a tradeoff, even when service improves.

The timing comparison is between two complete HPA policy/signal paths. Different sampling windows and metric-specific controller handling can contribute to an earlier desired count. I will not attribute all improvement to the metric's meaning, or confuse an earlier HPA decision with faster pod/model startup.

The six comparative load/post-load windows take at least 108.2 minutes; the two threshold-preparation windows add 36.1 minutes. This is about 2 hours 24 minutes before warmup, quiet gates, functional checks and review. Failures add time and are retained. The interruptions added time; this original estimate is not a completion forecast.

## Original time budget and acceptance

1. First half-day checkpoint: aim for a working signal path and passing local functional tests, including routing and the metric contract. Inspect resource headroom and give Envoy, Prometheus and the adapter explicit, identical resource settings in both arms. This checkpoint is a limit on the attempt, not a promise of delivery.
2. Proceed to separately approved threshold preparation only if that chain works and enough time remains for two preparation runs, six comparative runs, cleanup and second-day review. Otherwise retain the work as an uncompleted extension. Freeze configuration and the selected threshold after preparation; a missed checkpoint is not a reason to skip checks.
3. Run the separately approved six-cell comparison in new paths. Stop on invalid collection, changed configuration or failed cleanup; retain valid target misses and every failed attempt.
4. Leave the second day for evidence verification, charts and a short findings addition. Success means a valid comparison, even if neither policy meets the latency target.

Planning verification: I inspected `deploy/hpa.yaml`, `deploy/ollama.yaml`, `bench/inference.js`, `bench/workload.json`, the launcher, HPA readiness and the existing peak-12 driver. The official sources are linked above. The sources support the architecture choice; they do not prove local compatibility or overhead. The installed-chain checkpoint now verifies basic Kubernetes compatibility, versions, exported labels, freshness and resource headroom. Each remaining run must still pass its own collection and cleanup checks.

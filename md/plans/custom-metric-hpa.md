# Custom-metric HPA comparison

Status: the clock correction and Results grouping are verified, and comparison v2 is launched in a new folder. Both threshold preparations are preserved and target 1 remains selected. The first comparison stopped during attempt 01 on a clock-check failure, with 0/6 accepted runs. Historical evidence and settings remain unchanged.

### Authorized clock correction and retry

I traced the stop to Prometheus evaluation times about 0.78 seconds ahead of Windows. The initial clock check permits one second, but continuous validation permitted no future offset. The source samples were fresh. The load stopped at 404 of 782 seconds, leaving 29 unfinished client requests; I retain this attempt as incomplete.

I will use the same bounded one-second clock allowance throughout collection and readiness, retain the ten-second source-age limit in Prometheus's clock, and save query send/receive bounds even on failure. Two cleanup zeros must come from scrapes after the boundary including the clock allowance. Missing/stale values, larger clock offsets, restarts, mapping faults and failed cleanup still stop the run.

Acceptance: regression checks cover the saved 0.78-second trigger, excessive offset, stale source, empty/missing values, clock bounds and post-boundary zeros. I will replay both archived preparations without changing them, record the exact collector-version boundary, run a short installed collector/cleanup check, and launch a new six-cell comparison only after these pass. The model, workload, CPU/request thresholds, resources and ordering remain fixed. Results will group this evidence under Custom metrics with separate author notes. No commit or push is authorized.

The [clock correction check](../../results/custom-metric/clock-fix-20261113/README.md) passed: 254 Python tests, six browser tests, both preparation replays, five installed zero observations including a simulated -0.8-second observer offset, and complete cleanup. All 245 protected files were unchanged. Comparison v2 requires the exact verified old/new collector hashes; the selected target stays 1. The Custom metrics folder and notes were also checked in the live UI.

I launched [comparison-20261113-192512](../../results/custom-metric/comparison-20261113-192512/README.md) at 19:25:13 UTC. Launcher PID 24292 and interpreter/driver PID 42856 had matching command lines. The startup snapshot showed attempt 01 CPU in recovery quiet, no errors and 0/6 completed. This is startup evidence, not a completed result. I leave the series unattended as requested.

## Implementation checkpoint

### Authorized next stage

The six-run comparison is now authorized after the completed preparation. I will implement and test its separate driver and outcome analysis, then launch it in the background in a new directory. Order is CPU/custom, custom/CPU, CPU/custom; the selected request threshold remains 1. Both arms use the same gateway and metrics stack. Invalid collection, changed inputs or failed cleanup stops the driver without replacements. I will verify startup and leave the run unattended as requested; no job-monitoring automation is created because the current app instructions prohibit it. No commit or push is authorized.

I added `run_custom_comparison.py` and `analyze_custom_comparison.py`. Each run retains its successful-response p95, errors/timeouts, on-time success fraction and CPU coverage. The analysis also records sampled desired/Ready replica-seconds over the load and post-load windows separately, missing intervals, and signal/desired/Ready times relative to peak. The final summary retains all three pairs and applies the predeclared descriptive improvement rule. The driver verifies preparation from archived inputs, freezes comparison sources/configuration, checks the shared stack, model, backend image/configuration and host limits before each launch, and stops without replacing invalid runs. The new comparison metadata flag changes labels and archives only; the collector and workload remain identical to preparation.

Before launch, I will archive both the initial full-test failure (an existing fixed-three log-count fixture) and its verification repeat. The new focused checks cover both full six-cell progression and early stop on failed cleanup. External delegation remains unavailable after the previously recorded OpenCode filesystem permission failure; I have not bypassed it with another provider.

### Preserved first comparison launch

I launched [comparison-20261113-180650](../../results/custom-metric/comparison-20261113-180650/README.md) after 248 passing tests in the full repeat, 38 passing focused checks, preparation replay and live preflight. Driver PID 48160 started at 18:06:51 UTC on 13 November; attempt 01 CPU was confirmed in recovery quiet with 0/6 completed. The comparison archive records the preparation-to-comparison source boundary. I verified startup only and leave it unattended; the driver's internal collection and cleanup checks remain active. No six-run outcome is available at this checkpoint.

That first comparison subsequently stopped during load on the clock guard. Its manifest and incomplete attempt remain preserved; it is not the current retry.

The preceding authorization covered launcher integration and the two preparation bursts only. Those runs are complete and preserved below.

Before load I require tests of opt-in isolation, source freshness and restart detection, log failure, cleanup failure and the threshold qualification rule. During collection I bracket each Adapter request with source observations. A scrape crossing this short bracket is retained and retried within a bounded check; stale, missing or invalid sources are failures. This avoids treating two different valid scrapes as a mapping fault.

I implemented these checks in `custom_metric_run.py` and `prepare_custom_metric.py`. The launcher requires explicit `--custom-metric-policy`; it retains the existing backend checks and archives the additional sources and rendered configuration. The collector checks component identity and configuration, keeps gateway log streams, and rejects observation gaps above 10 seconds. Cleanup deletes the experiment HPA, restores one Ready copy, checks backend CPU quiet and requires two fresh gateway zeros. Offline review replays the raw signal and reconciles gateway IDs before qualifying a threshold.

All 240 Python tests passed in the final pre-launch check (64.338 seconds); the 30 focused tests also passed. The live idle collector check in `results/custom-metric/collector-check-20261113-164700` recorded three fresh zero samples with collection taking 0.45-0.48 seconds each. This is an idle timing check, not measured load overhead. Integrity verification preserved 120 historical files and matched the previous aggregates.

I launched [the two-target preparation](../../results/custom-metric/preparation-20261113-165340/manifest.json) at 16:53:13 UTC on 13 November. Its driver PID is 45792. The first saved phase is recovery quiet; this launch record does not establish a completed load or scaling result.

Target 1 subsequently completed with valid collection and cleanup and met the mechanism qualification rule, while missing the latency target. The driver then stopped at an assessor interface mismatch (`protocol_version`). I reproduced it offline, added the extension version only to the derived assessment view, passed 31 focused tests and replayed the saved evidence. I preserved the original stopped manifest and source archive and recorded both driver hashes before continuing target 2. The [preparation report](../../results/custom-metric/preparation-20261113-165340/README.md) owns the measurements and interruption history. No load was repeated.

Target 2 also completed with valid collection, cleanup and mechanism qualification, and met the service targets. I retain both measured outcomes. The [frozen inputs](../../results/custom-metric/preparation-20261113-165340/frozen-inputs.json) record configuration, component identities and source hashes; the final manifest selects target 1 by the original rule. This is a threshold-admission result, not evidence that target 1 is the best policy. Final runtime has no HPA or generator, one Ready Ollama copy and the installed metrics stack. The six-cell comparison and its additional outcome/capacity analysis remain unimplemented and unstarted.

After completion, all 241 Python tests passed in a full repeat. I retained the preceding accelerated-fixture timing failures and passing repeat in the preparation report; neither experimental settings nor validation limits were changed. Historical integrity verification passed again.

I added [the stack renderer](../../bench/custom_metric_stack.py), [signal validation](../../bench/custom_metrics.py) and [a read-only installed-stack check](../../bench/check_custom_metric.py). The renderer creates a new folder with Envoy, Prometheus and Adapter configuration, bounded resource settings, separate CPU/custom HPA manifests and SHA256 hashes. It never applies resources or starts load. The launcher retains its original CPU policy by default; the extension requires an explicit policy argument.

I selected Envoy 1.35.0, Prometheus 3.5.0 and Prometheus Adapter 0.12.0 and retained those versions for deployment. The [installed-chain report](../../results/custom-metric/cluster-check-20261113-160100/README.md) records Kubernetes 1.37.0, real image IDs, resource headroom and the checked signal path. These are explicit versions, not a claim about the latest releases. The local Adapter uses a generated serving certificate and `insecureSkipTLSVerify` for its own custom-metrics API registration, following the upstream example. It does not replace metrics-server. I checked all 21 resource names and API ownership before using `kubectl create`; the renderer itself does not install or check ownership.

The adapter query requires one healthy, fresh, nonnegative finite source series. Old, missing or duplicate data produces no metric. Local checks additionally retain the original scrape time, verify the current gateway identity and compare the Adapter value with its source. Two zero observations must come from distinct scrapes after the preparation boundary. The opt-in session attaches these checks to continuous collection and cleanup.

I extended HPA readiness with an opt-in Object-metric check and added optional forwarding of k6 request IDs. The launcher removes ambient `GATEWAY_REQUEST_IDS`, so existing runs do not enable the new header accidentally. Its explicit extension option sets the header in either policy and archives the additional sources.

I verified the Prometheus configuration and ten positive/negative PromQL cases with the official Prometheus 3.5.0 `promtool`, after checking its archive SHA256. The targeted 61 Python tests passed, including real k6 request-ID forwarding against a local HTTP fixture. [The explicit container check](../../tests/check_custom_metric_containers.py) covers the configured Envoy gauge, concurrent requests, errors, cancellation, client timeout, health exclusion, no retries, separate upstream connections and restart. **The container check passed on 13 November 2026:** [accepted evidence](../../results/custom-metric/container-check-20261113-b4116a3d/README.md). I retained three failed fixture attempts and corrected IPv4 host lookup, asynchronous access-log collection and the Docker-assigned port after restart. The accepted run verified 0 -> 3 -> 2 -> 0, 503/timeout/cancellation behavior, health exclusion, no retries, separate connections, complete request-ID reconciliation and a zero gauge after restart. All 15 focused custom-metric unit tests also passed. The later installed-chain checkpoint below adds Kubernetes deployment and end-to-end signal evidence. The container check alone does not establish the installed API path.

The full 225-test Python suite passed in 62.228 seconds without skips. Its first run exposed a historical replay test that compared saved source hashes with the changed checkout. I gave that test a temporary reference tree copied from the saved inputs; production continuation still rejects an unrecorded source change. No historical input or hash was updated. The integrity check preserved 120 protected evidence files, reproduced the saved observer-overhead aggregates and resolved 277 local links. External review did not run because the configured OpenCode catalog attempt failed on access to its log file; these are local verification results.

I can render and inspect a candidate without touching Kubernetes:

```powershell
.\.venv\Scripts\python.exe -B bench/custom_metric_stack.py --output-dir <new-bundle-folder>
.\.venv\Scripts\python.exe -B -m unittest tests.bench.test_custom_metrics
```

The explicit container check uses disposable containers and a controlled HTTP backend:

```powershell
.\.venv\Scripts\python.exe -B tests/check_custom_metric_containers.py --output-dir <new-check-folder>
```

### Installed-chain checkpoint

I created only `stack.json` and left the HPA manifests unapplied. The [deployment check](../../results/custom-metric/cluster-check-20261113-160100/README.md) passed idle validation and three concurrent, longer diagnostic requests: the signal grew to three and returned to zero through Prometheus, Adapter and the Custom Metrics API. Two new zero scrapes and the existing CPU quiet gate passed after completion. Configuration, image IDs, access logs, timestamps, the initial failed checker attempt and its narrow `/v1` compatibility correction are archived with that check. All 16 focused tests passed. Read-only tests against the installed Prometheus suppressed missing and stale source values rather than returning zero.

Ollama's configuration and container identity were unchanged; HPA remained absent and the reproduction profile remained stopped. This proves a working installed signal path, not autoscaling behavior or comparison readiness.

The launcher, continuous logs, source-age/restart stop rules, archive and preparation driver now have local and two-run live verification. The six-run comparison driver and its additional comparative analysis remain outside this completed preparation launch.

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

For the gateway I choose **Envoy rather than a new proxy implementation**. Its HTTP connection manager already exposes `downstream_rq_active`, a gauge of active requests, and its admin endpoint exports Prometheus metrics. I would use one dedicated inference listener and keep admin/health traffic outside its counter. This avoids implementing concurrency accounting in application code, although configuration and failure tests are still needed. [Envoy HTTP statistics](https://www.envoyproxy.io/docs/envoy/latest/configuration/http/http_conn_man/stats), [Prometheus export](https://www.envoyproxy.io/docs/envoy/latest/operations/admin).

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

Both policies use the same gateway and running metrics stack. The CPU arm retains the 60% CPU-request utilization target. The custom arm uses only the proposed outstanding-request metric; combining CPU and custom signals would answer a different question.

### Request routing and proof

I will keep `ollama` as the backend Service and scaling target, and introduce a separate gateway Service as the client entry point. `runtime.service_url()` currently opens `minikube service ollama`, while `autoscaling.Session.prepare()` requires the backend Service to be `ollama`. I must separate the client entry point from the backend identity checks; replacing every service name with the gateway would break those checks.

The preparation driver opens a gateway tunnel and passes its URL as `--base-url`. The comparison must use the same route in both arms. Existing checks of Ollama selectors, endpoints, image and pod identity stay in place. Single-copy warmup uses that base URL through Envoy, remains labelled as preparation and is excluded from measured request counts. The counter must return to two fresh zeros before HPA activation.

For this experiment only, k6 will send its existing request ID in an HTTP header which Envoy logs. The same instrumentation is used in both arms. Archive the client URL, gateway configuration, backend Service/endpoints and access logs. Before comparison, reconcile each measured client request ID with exactly one gateway request record, check that forwarding uses only the Ollama backend, and retain upstream failure/reset fields. Verify no automatic retries. Keep native Ollama reconciliation as a separate backend check. A request that fails to reach Envoy is a transport outcome to explain, not an absent record to silently ignore.

The gateway must retain the request body, status and response, forward requests concurrently, avoid retries, and preserve the existing no-connection-reuse routing to Ollama. Envoy supports disabling upstream keep-alive with `max_requests_per_connection: 1`; I would verify this with HTTP/1.1 and per-pod traffic evidence. Existing per-pod warmup stays outside measured load. I would explicitly configure timeouts so the proxy does not introduce a shorter deadline than the existing 30-second client timeout. [Envoy protocol options](https://www.envoyproxy.io/docs/envoy/latest/api-v3/config/core/v3/protocol.proto)

The dedicated listener accepts only generation traffic. Client disconnects, upstream timeouts, cancellations and gateway restarts need explicit tests and timestamps. A zero gauge does not prove that Ollama has drained; retain the existing recovery/quiet gates. Missing or stale scrapes must produce unavailable metric evidence, not a fabricated zero. Keep the admin endpoint internal, collect gateway access logs, and reject a preparation run if the gateway restarts or becomes a bottleneck.

### Metric validity and admission checks

These are proposed experiment rules, to verify during preparation and freeze before comparison:

- Scrape and observe every 5 seconds. Accept a source sample only when it is no more than **10 seconds old**, comes from the current gateway instance, and belongs to the dedicated inference listener. Save source scrape time and receipt time separately; a fresh adapter response timestamp must not hide an old Prometheus value. Check clock alignment before using this age rule.
- Require a healthy scrape target and exactly the expected series before aggregation. Missing, duplicate, negative, non-finite or stale values are errors, not zero. Do not use a query fallback that substitutes zero for missing series.
- Before activation, require two consecutive fresh zero samples after warmup and after the previous attempt's cleanup, plus the existing CPU quiet gates. Verify the adapter value against its source sample and require HPA to report the chosen metric and active scaling. Preserve the CPU arm's existing readiness checks.
- Test against a controllable HTTP backend: hold three requests open and observe a gauge of three; finish one and observe two; finish the rest and observe zero. Test HTTP errors, client cancellation, an upstream response longer than the client deadline, and a gateway restart. Exclude health/admin traffic and prove that requests are not retried.
- For a client timeout, save the gateway reset/completion and any later backend completion. Require the counter to follow active gateway requests correctly. Continued Ollama work is a recorded scope limitation, not evidence that the counter itself is wrong. Keep preparation blocked until the existing backend quiet checks pass.
- During either comparison arm, a source older than 10 seconds, failed metric mapping or gateway/metrics-component restart stops the attempt through normal cleanup and prevents the next launch. Preserve all data and label the policy comparison incomplete. Client measurements already collected may remain valid; they do not establish a complete comparison run. Do not silently resume, replace the run or feed a synthetic metric.

I will implement and test freshness enforcement in the query/adapter path as well as observation; checking age only in the final report would not prevent HPA from using stale input. If this contract cannot be implemented reliably in the time available, the comparison does not start.

### Bounded threshold preparation

After functional checks pass, I will use one separately saved prepared burst for target 1, then one for target 2. Both use the same 782-second 2 -> 12 -> 2 profile, 300-second post-load observation, infrastructure and clean-start rules as the comparison. These are two additional preparation runs, not part of the six comparative runs.

A candidate qualifies if collection and cleanup pass, HPA remains at one desired/Ready replica throughout the initial 120-second low phase, and during the peak it requests at least two replicas and a second replica becomes Ready before the peak ends. These are stability and mechanism checks; passing the five-second latency target is not a selection condition.

If both qualify, choose the smaller target; if only one qualifies, choose that target. If neither qualifies, stop this extension and report the result. Invalid collection or failed cleanup stops preparation for review rather than disqualifying a threshold on performance grounds. Keep all attempts. Do not add candidates or repeats to search for a better-looking result.

Freeze the chosen target, query, freshness rule, component versions/resources, timeout settings, sampling and HPA behavior before the comparative series. A later configuration change creates a new protocol revision and requires a new decision about the series; it cannot silently replace one of the six cells.

## Changes needed

I can keep Ollama, Qwen, generation settings, the k6 burst, latency/error formulas and existing backend log reconciliation. The new experiment adds request-ID forwarding and gateway reconciliation to both arms. I cannot obtain this signal simply by changing the current HPA threshold.

| Component | Proposed work |
|---|---|
| Deployment | Add Envoy configuration, a small Prometheus instance, adapter mapping and separate custom HPA manifest. Check available CPU/memory first. Pin images/chart versions and configuration. No custom proxy code, Grafana or full monitoring bundle is required. |
| Launcher and routing | Add explicit opt-in policy/manifest and client gateway selection. Keep the Ollama backend identity checks separate from the client URL. Add experiment-only request-ID forwarding and archive both routes. The frozen main-protocol path remains unchanged. |
| HPA readiness | The opt-in Object-metric readiness helper is connected to the extension session and has local tests. The original CPU readiness path remains available. Live preparation is checking the complete lifecycle. |
| Observation and archive | Save Envoy access logs, raw gauge samples, source/scrape/receipt times, HPA-reported values, errors, policy and infrastructure hashes. Enforce the metric contract and retain existing CPU/memory and desired/Ready replica records. |
| Comparison driver | Reuse preparation, load, cleanup and analysis through a separate six-cell protocol. Do not overwrite or repurpose the completed nine-cell manifest or its source checks. |
| Analysis | Keep existing successful p95/error assessments. Add on-time success fraction, sampled replica-seconds and the separate signal, HPA-decision and Ready timelines defined below. Include common monitoring overhead in the limits. |
| Tests | Verify the configured gateway against concurrent success/error/cancellation, no retries and connection reuse; test counter reset, missing/stale metrics, metric readiness, policy archival and cleanup. Keep existing tests passing. |

I would not build a custom autoscaling controller or a custom Kubernetes metrics API server for this extension.

## Proposed series

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

The six comparative load/post-load windows take at least 108.2 minutes; the two threshold-preparation windows add 36.1 minutes. This is about 2 hours 24 minutes before warmup, quiet gates, functional checks and review. Failures add time and are retained. Two-day feasibility is not yet verified.

## Two-day limit and acceptance

1. First half-day checkpoint: aim for a working signal path and passing local functional tests, including routing and the metric contract. Inspect resource headroom and give Envoy, Prometheus and the adapter explicit, identical resource settings in both arms. This checkpoint is a limit on the attempt, not a promise of delivery.
2. Proceed to separately approved threshold preparation only if that chain works and enough time remains for two preparation runs, six comparative runs, cleanup and second-day review. Otherwise retain the work as an uncompleted extension. Freeze configuration and the selected threshold after preparation; a missed checkpoint is not a reason to skip checks.
3. Run the separately approved six-cell comparison in new paths. Stop on invalid collection, changed configuration or failed cleanup; retain valid target misses and every failed attempt.
4. Leave the second day for evidence verification, charts and a short findings addition. Success means a valid comparison, even if neither policy meets the latency target.

Planning verification: I inspected `deploy/hpa.yaml`, `deploy/ollama.yaml`, `bench/inference.js`, `bench/workload.json`, the launcher, HPA readiness and the existing peak-12 driver. I read the official sources linked above directly after the search tool returned no results. The sources support the architecture choice; they do not prove local compatibility or overhead. The installed-chain checkpoint now verifies basic Kubernetes compatibility, versions, exported labels, freshness and resource headroom. This does not replace the remaining collection, cleanup and comparative-run acceptance checks.

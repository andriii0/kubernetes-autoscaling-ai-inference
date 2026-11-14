# Decisions

Updated: 2026-11-12. Local implementation summary for contributors and agents. [Technology Decisions in Notion](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a) owns the detailed technology research; the Word research and its PDF own the orchestration-platform comparison. Accepted choices do not imply measured superiority. Numeric main settings are agreed in [main experiment methodology v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd); the main matrix and controlled peak-12 follow-up are complete; [STATUS.md](STATUS.md) owns current progress.

## 1. Use one Kubernetes prototype after comparing alternatives

Accepted. Compare alternatives first, then implement one platform. Kubernetes supplies replica control, service routing, declared resources and HPA. Nomad remains an alternative; Swarm needs an additional scaling integration and Compose is a fixed-capacity reference. See section 6 (SQ3) of the [research document](<../docs/PDP Research document.pdf>). A second complete prototype is outside the initial scope.

## 2. Use Minikube with Docker on the existing Windows computer

Accepted for the local prototype. Image loading, metrics and Windows Service access have saved local verification. kind and k3d remain viable alternatives without a measured performance ranking. Detailed comparison: [Notion section 6](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a). Revisit if required deployment, access or measurements stop being repeatable.

## 3. Use the verified Ollama/Qwen CPU baseline for the first experiment

Accepted baseline: Ollama, `qwen2.5:0.5b`, CPU, one repeated prompt, maximum 64 output tokens, context 1024, two inference threads, temperature 0 and seed 42. Saved checks establish feasibility, not model quality or comparative capacity. Alternatives, evidence and reconsideration criteria: [Notion sections 1-3](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a). Protocol v1.1 retains this baseline for the main series.

## 4. Bundle model weights into a local image

Implemented. `app/Dockerfile` pins the Ollama base image by digest and includes downloaded weights; Minikube loads the image locally and the Deployment uses `imagePullPolicy: Never`. Each replica still loads its own model into memory. Mounted storage or a registry-delivered image are alternatives for another environment. Keep `app/models/` out of Git; preparation is in the setup guide.

## 5. Use k6 for controlled request arrivals

Implemented. k6 arrival-rate scenarios schedule requests independently of response completion; `RATE` means requests per 10 seconds. Keep successful latency, response errors and dropped starts separate. The repeated prompt may benefit from caching. Alternatives and rationale: [Notion section 4](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a).

## 6. Separate the scaling signal from resource measurements

Implemented and verified. Use metrics-server for HPA input and direct kubelet `/metrics/resource` for CPU time and memory working set. The standard-library observer invokes `kubectl` and preserves raw values, source timestamps, errors and gaps. See [OBSERVATION.md](OBSERVATION.md) and [metrics-server's limitations](https://github.com/kubernetes-sigs/metrics-server). Source refresh and sequential reads limit precision; this does not measure power or cost savings.

<a id="7-retain-a-5-second-observer-interval-provisionally"></a>

## 7. Retain a 5-second observer interval

Accepted provisionally for the pilot, which has now completed, based on the checked low load: the [overhead report](../results/observer-overhead-2026-10-16-series1/README.md) records the measurements and budget decision. Protocol v1.1 retains the same 5-second interval. This does not prove negligible overhead near saturation. Record settings per run; if collection becomes disruptive, diagnose and version any protocol change instead of silently changing the interval.

<a id="8-keep-the-three-mode-scaling-comparison-as-planned-work"></a>

## 8. Compare three capacity policies on the same host

Selected: fixed one replica, fixed three replicas and CPU-based HPA bounded to 1-3, all on one physical computer. Each copy has a 2-CPU limit, so fixed one can use up to 2 CPU while fixed three can use up to 6 CPU on the same node. This compares capacity policies, not equal total CPU budgets. The main peak-8 series did not establish an HPA advantage because one fixed copy also met the targets. In the later [controlled peak-12 follow-up](../results/follow-up/comparison-20261110-205108-peak12/README.md), fixed one was overloaded, HPA reduced failures but missed the latency target in all three runs, and fixed three handled the burst best.

Use [deploy/hpa.yaml](../deploy/hpa.yaml) for the policy retained in main protocol v1.1: CPU utilization target 60% of requests and a 300-second downscale stabilization window. Default scale-up behavior is retained. These are starting settings, not measured optima. The peak-12 result shows the tradeoff: HPA can improve completion while extra copies start, but its CPU reaction was too slow to keep this short burst within five seconds. This does not rank other HPA policies or scaling signals.

## 9. Keep one project documentation tree

Accepted. `README.md` is the entry point; `AGENTS.md` contains work rules; `md/` contains technical context, local summaries, meeting notes and plans. Detailed technology research is maintained in Notion. `docs/README.md` identifies the working Word document, PDF exports, editing sources and course references. Earlier Word versions and generation scripts stay in the separate authoring workspace. Keep original measurements and run READMEs under `results/`. Fontys Portflow submission is still required; a GitHub copy does not replace it.

The repository is private. Keep weights, caches and credentials out of Git. Preserve measured script and result bytes: `.gitattributes` excludes `bench/inference.js` and `results/` from line-ending conversion so historical hashes remain valid.

## 10. Distinguish server readiness from a warm model

Status: accepted for the first scaling experiment. The existing `/api/tags` probe confirms that the Ollama API can accept traffic; it does not certify that the model is resident or has generated an answer. Warm every initial replica with a successful generation before the measured interval. New replicas created during autoscaling receive requests while cold, and their model loading is part of the measured scaling reaction. Record Kubernetes Ready transitions separately from response observations. For autoscaled pods, native logs show the first observed HTTP response, not a verified first successful generation; never call the Ready transition the model-ready time. A future model-warming startup/readiness gate would be a different protocol and must be evaluated separately. The deployment probe is unchanged.

## 11. Freeze main experiment protocol v1.1

I accepted this on 2026-10-21. The [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) owns the numeric agreement and rationale. Retain the pilot workload and rates; use primary successful-response p95 <= 5000 ms and errors <= 1%. Zero dropped starts is a condition of complete offered load, separate from service targets. The latency target is a study assumption for a short complete answer, with a predefined 10000-ms sensitivity check on the same data. It is not an external user requirement or a guarantee that HPA will pass.

Primary latency covers the full steady run or full burst peak, assigned by request start. The initial HPA reaction is included in both; growth to three copies is not required. Primary resource comparison covers the common scheduled interval; client drain and later observation are separate. Preserve system failures and distinguish them from missing measurements. Initial models are warmed; new HPA copies load during traffic. No routine rollout restart is required. Step 18 retains its original preliminary three-copy check; the full repeated comparison belongs to step 21. The main matrix is unchanged and does not require another step-18 series. The existing launcher, analyzer and shared configuration implement these rules, with local tests. `main_protocol.py` owns agreement-specific validation and preparation; `analyze.py` owns run assessments and resource calculations. Both reuse the existing observation and request records. No new service or matrix orchestrator is needed. Historical runs retain their original inputs, thresholds and verdicts.

Version 1.1 clarifies the 1.0 agreement before any main run (affected main runs: 0). Settle after initial warmup using fresh low CPU; before HPA, also exclude warmup from the metrics-server measurement window. Compare estimated CPU core-seconds and observed peak memory per instance with coverage, not only sampled CPU means. Use the fixed assessment fields in Notion; incomplete request accounting cannot pass. Keep existing unfinished-request validation and distinguish system failures from missing measurements. The low-load overhead evidence remains provisional even though the 5-second interval is fixed for this protocol.

## 12. Use a dependency-free local browser UI

I chose Python's standard-library loopback server and plain HTML/CSS/JavaScript for Inference Lab on 2026-11-10. This reuses the existing Python environment and browser. A packaged desktop framework would add installation and runtime dependencies for this single-screen utility. The UI reads the existing evidence format and calls the existing launchers; it does not introduce another measurement format or assessment algorithm.

I expose Run series as v1.1 continuation. The existing driver cannot initialize a new series, and its executable-hash checks remain authoritative. A future explicit `--new-series` option could exclusively create a directory and reuse the existing matrix/execution rules. That extension is proposed, not implemented. The [UI plan](plans/inference-lab.md) owns the preset, verification and remaining limits.

## 13. Keep the request-metric extension on native HPA

I chose an Envoy active-request gauge, Prometheus and Prometheus Adapter for the optional extension. Both policy arms will use the same gateway and metrics infrastructure. This retains the existing HPA controller and model server while changing the scaling signal. KEDA or Knative would add another controller or serving lifecycle to this comparison. I do not use p95 or TTFT as its control signal; the gateway measures active client-facing requests, not Ollama's internal queue or compute left after a disconnect.

The [extension plan](plans/custom-metric-hpa.md) records the selected versions, freshness rules and acceptance criteria. The metric chain, continuous collection, cleanup, threshold preparation and six-cell comparison driver are implemented. Both preparations are complete; the comparison has four accepted cells and is stopped. Target 1 remains selected. [STATUS.md](STATUS.md#cpurequest-hpa-comparison) records the current blocker. Historical policies and evidence retain their original meaning.

## 14. Separate elapsed time from calendar time

I use a local k6 runtime with a small Go timer (`time.Since`) for new request durations. Stock k6 2.2.0 exposes wall-clock-derived run and HTTP timings, so they do not solve clock steps. I pin k6, xk6 and Go versions, verify the local binary hash and archive the timer sources. UTC timestamps remain necessary for matching client, gateway and cluster records. A monotonic timer does not repair Windows/WSL clock alignment.

New threshold preparation uses `active-requests-preparation-v2`; new comparison uses `active-requests-comparison-v3`. The one-second Prometheus/observer limit and ten-second freshness limit remain. New observations also compare wall and monotonic intervals, with a 50-ms allowance plus the measured uncertainty of each paired read. A failed clock check still stops the run.

I keep the stopped 13 November series as separate evidence. The final comparison starts with new preparation and six new cells. I will not join them to the old four. One shared local lock covers CLI/UI preparation, child launchers, k6 and cleanup. The new-series driver stops on failure and does not retry automatically. See the [reliability plan](plans/clock-and-run-reliability.md).


### Temporary clock environment for the new 14 November cycle

I retain both stopped cycles separately. The saved Ubuntu journal links the clock steps to systemd-timesyncd, while Docker/WSL follows host time. For [this new launch](../results/custom-metric/launch-20261114-191048/launch-request.json), I temporarily mask Ubuntu's separate synchronizer while keeping that distribution alive. The worker restores the prior service state after completion or failure. This establishes one host-relative time domain during the experiment; it does not certify absolute UTC accuracy. I keep the existing clock/freshness limits, workload and HPA settings. No persistent host time configuration is changed.

# Decisions

Updated: 2026-10-18. Local implementation summary for contributors and agents. [Technology Decisions in Notion](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a) owns the detailed technology research; the Word research and its PDF own the orchestration-platform comparison. Accepted choices do not imply measured superiority. Numeric experiment settings remain provisional.

## 1. Use one Kubernetes prototype after comparing alternatives

Accepted. Compare alternatives first, then implement one platform. Kubernetes supplies replica control, service routing, declared resources and HPA. Nomad remains an alternative; Swarm needs an additional scaling integration and Compose is a fixed-capacity reference. See section 6 (SQ3) of the [research document](<../docs/PDP Research document.pdf>). A second complete prototype is outside the initial scope.

## 2. Use Minikube with Docker on the existing Windows computer

Accepted for the local prototype. Image loading, metrics and Windows Service access have saved local verification. kind and k3d remain viable alternatives without a measured performance ranking. Detailed comparison: [Notion section 6](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a). Revisit if required deployment, access or measurements stop being repeatable.

## 3. Use the verified Ollama/Qwen CPU baseline for the first experiment

Accepted baseline: Ollama, `qwen2.5:0.5b`, CPU, one repeated prompt, maximum 64 output tokens, context 1024, two inference threads, temperature 0 and seed 42. Saved checks establish feasibility, not model quality or comparative capacity. Alternatives, evidence and reconsideration criteria: [Notion sections 1-3](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a). Freeze final settings after the pilot.

## 4. Bundle model weights into a local image

Implemented. `app/Dockerfile` pins the Ollama base image by digest and includes downloaded weights; Minikube loads the image locally and the Deployment uses `imagePullPolicy: Never`. Each replica still loads its own model into memory. Mounted storage or a registry-delivered image are alternatives for another environment. Keep `app/models/` out of Git; preparation is in the setup guide.

## 5. Use k6 for controlled request arrivals

Implemented. k6 arrival-rate scenarios schedule requests independently of response completion; `RATE` means requests per 10 seconds. Keep successful latency, response errors and dropped starts separate. The repeated prompt may benefit from caching. Alternatives and rationale: [Notion section 4](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a).

## 6. Separate the scaling signal from resource measurements

Implemented and verified. Use metrics-server for HPA input and direct kubelet `/metrics/resource` for CPU time and memory working set. The standard-library observer invokes `kubectl` and preserves raw values, source timestamps, errors and gaps. See [OBSERVATION.md](OBSERVATION.md) and [metrics-server's limitations](https://github.com/kubernetes-sigs/metrics-server). Source refresh and sequential reads limit precision; this does not measure power or cost savings.

## 7. Retain a 5-second observer interval provisionally

Accepted provisionally for the pilot, which has now completed, based on the checked low load: the [overhead report](../results/observer-overhead-2026-10-16-series1/README.md) records the measurements and budget decision. This does not prove negligible overhead near saturation. Record settings per run; consider a 10-second interval if collection becomes disruptive.

## 8. Keep the three-mode scaling comparison as planned work

Selected: fixed one replica, fixed three replicas and CPU-based HPA bounded to 1-3, all on one physical computer. The [fixed-three check](../results/fixed-replicas/check-2026-10-20-series1/README.md) and [HPA mechanism check](../results/autoscaling/check-2026-10-20-series1/README.md) have saved preliminary evidence. The repeated main comparison remains unfinished.

Use [deploy/hpa.yaml](../deploy/hpa.yaml) for the preliminary policy: CPU utilization target 60% of requests and a 300-second downscale stabilization window. Default scale-up behavior is retained. These are starting settings, not measured optima. The [scaling plan](plans/scaling-experiment.md#2-hpa-setup-and-checks) owns execution; detailed alternatives remain in [Notion section 5](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a). The first run verifies reactions but does not establish an autoscaling advantage. Freeze the main protocol before repeated comparisons.

## 9. Keep one project documentation tree

Accepted. `README.md` is the entry point; `AGENTS.md` contains work rules; `md/` contains technical context, local summaries, meeting notes and plans. Detailed technology research is maintained in Notion. `docs/README.md` identifies the working Word document, PDF exports, editing sources and course references. Earlier Word versions and generation scripts stay in the separate authoring workspace. Keep original measurements and run READMEs under `results/`. Fontys Portflow submission is still required; a GitHub copy does not replace it.

The repository is private. Keep weights, caches and credentials out of Git. Preserve measured script and result bytes: `.gitattributes` excludes `bench/inference.js` and `results/` from line-ending conversion so historical hashes remain valid.

## 10. Distinguish server readiness from a warm model

Status: accepted for the first scaling experiment. The existing `/api/tags` probe confirms that the Ollama API can accept traffic; it does not certify that the model is resident or has generated an answer. Warm every initial replica with a successful generation before the measured interval. New replicas created during autoscaling receive requests while cold, and their model loading is part of the measured scaling reaction. Record Kubernetes Ready transitions separately from response observations. For autoscaled pods, native logs show the first observed HTTP response, not a verified first successful generation; never call the Ready transition the model-ready time. A future model-warming startup/readiness gate would be a different protocol and must be evaluated separately. The deployment probe is unchanged.

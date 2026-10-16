# Decisions

Updated: 2026-10-16. Accepted choices are distinguished from provisional baseline settings and planned work. Unmeasured comparisons remain unmeasured.

## 1. Use one Kubernetes prototype after comparing alternatives

Status: accepted. Compare orchestration options first, then implement one platform. Kubernetes provides replica control, resource declarations, service routing and HPA capabilities for the intended experiment. Nomad with its Autoscaler remains a viable alternative; Swarm requires an additional scaling controller, and Compose is useful for fixed capacity. A second complete prototype would expand the initial research scope.

This is a capability-based choice, not a measured performance ranking. The full comparison is in [research/platform-choice.md](research/platform-choice.md).

## 2. Use Minikube with Docker on the existing Windows computer

Status: accepted for the local prototype. Minikube supports the existing Docker environment, local image loading and the metrics-server addon. Its compatibility has been checked locally. kind and k3d remain alternatives; no speed or memory advantage over them has been measured. Revisit if Minikube prevents repeatable deployment or required measurements.

## 3. Retain the verified Ollama/Qwen CPU baseline provisionally

Status: working baseline, with remaining decision research open. Current code uses Ollama, `qwen2.5:0.5b`, one repeated short prompt, at most 64 output tokens, a 1024-token context, two inference threads, temperature 0 and seed 42. This combination has returned valid local responses and provides fixed initial conditions.

Alternatives include llama.cpp, vLLM, Transformers, different model sizes and GPU execution; they are discussed in [GETTING_STARTED_RU.md](GETTING_STARTED_RU.md#research-alternatives). There is no completed comparative evaluation establishing this baseline as optimal. Model/server/hardware justification and final numeric settings still need completion before the main series. Keep technology reasons here and freeze experiment settings in the planned `md/plans/experiment-protocol.md`.

## 4. Bundle model weights into a local image

Status: implemented. `app/Dockerfile` pins the Ollama base image by digest and copies pre-downloaded model files. The image is loaded into Minikube; `imagePullPolicy: Never` uses that local image. This avoids an internet model download on every replica start. A mounted model volume or registry-delivered image are alternatives for a different environment.

Weights stay out of Git under `app/models/`; preparation remains in the setup guide. Each replica still loads the model into its own memory, so image reuse does not remove model startup time.

## 5. Use k6 for controlled request arrivals

Status: implemented. k6 is the active load generator; the Python load-test file remains a starter. Arrival-rate scenarios let scheduled traffic remain independent of response completion. Locust, JMeter and a custom Python generator are alternatives discussed in the guide.

Record successful-response latency, response errors and dropped starts separately. The repeated prompt controls input conditions but may benefit from caching; it is not representative of all user requests. The first main experiment settings will be chosen after the pilot.

## 6. Separate the scaling signal from resource measurements

Status: implemented and verified locally. Keep metrics-server observations for interpreting HPA input. Read kubelet `/metrics/resource` directly for accumulated CPU time and memory working set, retaining raw values, source timestamps and errors. This follows [metrics-server's monitoring limitations](https://github.com/kubernetes-sigs/metrics-server); metric units are defined in the [Kubernetes reference](https://kubernetes.io/docs/reference/instrumentation/metrics/).

The Python standard-library collector invokes installed `kubectl`; Prometheus and a Kubernetes Python client are alternatives if storage/query needs or subprocess overhead justify them. No new collector dependency was added. Source refresh and sequential reads limit temporal precision; these measurements do not establish power or cost savings.

## 7. Retain a 5-second observer interval provisionally

Status: accepted for the next pilot at the checked low load. Four paired observer-off/on comparisons produced 195 valid responses, a median paired mean-latency change of +5.22% and p95 change of +3.95%, within the pre-recorded practical budget. See [the overhead report](../results/observer-overhead-2026-10-16-series1/README.md).

A 10-second interval remains an alternative if collection becomes disruptive. This small low-load series is not an equivalence proof and does not establish negligible overhead near saturation. Record collector settings with every run.

## 8. Keep the three-mode scaling comparison as planned work

Status: planned. Compare fixed one replica, fixed three replicas and HPA between one and three on the same physical computer. CPU-based HPA is the initial candidate; other resource or queue-based signals remain alternatives. HPA is not yet configured and its suitability has not been measured.

## 9. Keep one project documentation tree

Status: accepted, 2026-10-16. Root `AGENTS.md` contains agent instructions and root `README.md` is the entry point. Current documentation, decisions, research, meeting notes and plans live under `md/`. Result-specific READMEs and original evidence stay with their runs. The separate document-authoring workspace keeps Word artifacts and points here for code/project state.

Fontys Portflow remains the required portfolio destination. The student requested a GitHub copy of the code and Markdown documentation on 2026-10-16; that does not replace Portflow submission.

The repository is private. Model weights, caches and local credentials are ignored. `.gitattributes` defaults source/document text to LF, but preserves the original bytes of the measured `bench/inference.js` and files in `results/`. The measured load script originally uses Windows line endings; converting them would invalidate historical source hashes even though the JavaScript behavior is unchanged.

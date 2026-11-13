# Architecture

Updated: 2026-11-12. This describes the implemented local prototype. Preliminary checks, the 18-run main matrix and controlled peak-12 comparison have saved evidence; this is not a check of current runtime availability.

## Runtime flow

1. `bench/inference.js` runs in k6 on Windows. It schedules calls at a configured rate per 10 seconds and posts a non-streaming request to `/api/generate`.
2. A Minikube Service tunnel exposes the Ollama Service at a Windows localhost address. The port can change when the tunnel restarts.
3. The Service in namespace `inference` routes requests to pods labelled `app=ollama`. `deploy/ollama.yaml` defaults to one replica; a preliminary check manually scaled it to three.
4. The pod runs Ollama from `ai-inference:0.1` with bundled `qwen2.5:0.5b` weights. Ollama loads the model into its own process memory and generates the response using CPU.
5. k6 checks the completed response and records full-response duration and errors. Token counts and model-load durations are recorded only when valid, with separate availability rates. Scheduled work the generator cannot start is counted separately as dropped iterations.

The cluster is the existing Docker-backed Minikube profile `ai-lab`, configured with 8 CPU units and 12 GiB RAM on one Windows computer. These are local environment settings, not production capacity evidence. Each Ollama replica requests and is limited to 2 CPU units; memory request is 1 GiB and limit is 2 GiB. The current readiness probe checks `/api/tags`; it does not prove that the model has been loaded, so warmup is separate.

## Components and files

| Component | Implementation | Responsibility |
|---|---|---|
| Model image | `app/Dockerfile` and local ignored `app/models/` | Pin the Ollama base image and bundle downloaded weights |
| Application deployment | `deploy/ollama.yaml` | Declare the Deployment, resource settings, readiness probe and NodePort Service |
| Load generator | `bench/inference.js` | Generate steady/burst traffic and collect request metrics; short probes and five-minute one-replica steady confirmations have run; one preliminary autoscaling burst is saved; the main matrix is complete |
| Workload settings | `bench/workload.json` | Share the exact request payload and k6 execution settings between warmup and measured load |
| Pilot launcher | `bench/run_pilot.py` | Exclusively create a run folder; validate fixed one/three-copy state or use the autoscaling lifecycle; orchestrate idle observation, warmup, k6, post-load observation and reconciliation; retain partial failures |
| Main-series continuation | `bench/run_series.py` | Replay and skip completed attempts; manage a Service tunnel and call the existing launcher/analyzer sequentially; stop for incomplete data without automatic replacements |
| Peak-12 comparison | `bench/run_peak12_comparison.py` and `bench/resume_peak12.py` | Run the fixed comparison order, assess saved cells, retain failed attempts and continue only an accepted consecutive prefix |
| Peak-12 plots | `bench/plot_peak12.py` | Build saved-data plots from the accepted manifest entries without rerunning load or changing assessments |
| Local experiment UI | `lab/server.py`, `lab/results.py`, `lab/jobs.py`, `lab/launch.py`, `lab/static/` | Browse saved results, show scoped metrics and plots, serialize UI jobs and adapt existing pilot/continuation commands |
| Warmup-wait diagnostic | `bench/run_wait_pair.py` | Run the separately authorized two-run preparation check through the existing launcher; archive order/settings and host snapshots; keep diagnostic evidence outside the main matrix |
| Shared runtime | `bench/runtime.py` | Run child processes, own the Service tunnel and record pre-launch host state for the scenario drivers |
| Protocol preparation | `bench/main_protocol.py` | Define the matrix and frozen argument checks; prepare replicas, check runtime configuration and wait for quiet state |
| Autoscaling lifecycle | `bench/autoscaling.py` and `deploy/hpa.yaml` | Reset/warm the initial copy, attach HPA, validate dynamic state, stream logs by UID, and restore one copy |
| Fixed replica preparation | `bench/fixed_replicas.py` | Warm each selected pod through the API proxy; verify Service endpoints, stream prepared-run logs and aggregate per-pod completion counts |
| Collection validator | `bench/pilot_records.py` | Check request counters and observation coverage/stability; report archive issues as warnings without modifying raw evidence |
| Shared records | `bench/records.py` | Read JSONL, interpret timestamps and percentiles, and validate fixed replica identities without importing lifecycle modules |
| Observer | `bench/observe.py` | Read Kubernetes and kubelet through `kubectl`; save raw state, source timings, CPU/memory and errors as JSONL |
| Local tests | `tests/bench/` and `tests/bench/fixtures.py` | Check parsing, missing data, failures, lifecycle cleanup, source archives and analysis using temporary evidence and local HTTP servers |
| Run analysis | `bench/analyze.py` | Reconcile saved evidence, calculate phase assessments and resource estimates, and produce CSV/JSON summaries plus aligned plots; optional Matplotlib is used only for plotting |
| Main comparison | `bench/summarize_main.py` | Replay all 18 main attempts and reuse the analyzer for per-run/group/phase/resource/scaling tables and plots; retain incomplete resource totals |
| Offline verification | Scripts saved in result directories | Recalculate and validate the completed observation/overhead checks |
| Evidence | `results/<run>/` | Keep configurations, raw measurements, summaries, snapshots and console output together |

Ollama and k6 are the active inference and load-generation runtime; unused Python scaffolding has been removed. `bench/analyze.py` supports fixed and autoscaling runs, including phase results, HPA/Ready timelines and per-pod resource records. The main comparison and controlled peak-12 follow-up have saved analyses and findings. The [reproduction check](../results/reproduction/check-2026-11-06/README.md) verified setup and analysis on the same Windows host.

## Local UI flow

I added Inference Lab on 2026-11-10. I run it with `python -B -m lab`. A standard-library HTTP server binds to Windows loopback and serves plain HTML/CSS/JavaScript. The browser requests a catalog and selected details from `lab/results.py`. That reader uses saved metadata, collection checks, phase assessments, request events and PNGs. It retains missing metrics and distinguishes collection failures from target misses. Reading results does not invoke the analyzer or modify evidence.

`lab/jobs.py` owns one active UI job and streams its output into ignored `.inference-lab/` files. A Windows file lock excludes a second UI server. A process check blocks live starts while another experiment is detected. The pilot adapter owns the existing runtime Service tunnel and calls `bench/run_pilot.py`, then CSV/JSON analysis. Series jobs call `bench/run_series.py` directly and retain its continuation, archive and stop rules. Pilot dry run validates real launcher arguments; series dry run uses the driver's saved-evidence replay. The UI plan records [verification and limits](plans/inference-lab.md).

## Measurement flow

`run_pilot.py` keeps the existing CLI and separates parsing, metadata, input archives, preparation, load and finalization into functions. Its outer `try/finally` owns cleanup. Scenario drivers use `runtime.py`; record readers and identity checks in `records.py` have no dependency on lifecycle or analysis modules. Phase assessments and resource estimates belong to `analyze.py`. The bench import graph has no cycles, including imports inside functions.

The observer reads selected pods, namespace Deployments/HPA, nodes and metrics-server data. It separately queries each selected pod's node at `/api/v1/nodes/<node>/proxy/metrics/resource`. Deployment metadata may not carry the pod label, so Deployment reads cover the namespace.

Direct kubelet series provide accumulated CPU core-seconds, memory working set and source timestamps. CPU rates use differences between valid consecutive source samples; first samples, repeated timestamps and reset counters remain missing. Instance identity includes pod UID, restart count and container start time. Raw data, read timings and source errors remain in `cluster.jsonl`; failed reads are not zero usage. See [OBSERVATION.md](OBSERVATION.md) for the schema and units.

Metrics-server data describes the scaling signal. Direct node metrics describe the Minikube Linux node, including Kubernetes services; they do not measure the whole Windows host, electrical energy or monetary cost. The observer targets a 5-second polling interval, but underlying samples refresh independently.

For a pilot, the launcher reuses the observer in one background thread and saves the initial/final snapshots itself. The same observer instance retains CPU-counter continuity. Separate warmup generations precede k6 and stay out of measured request totals. For three copies, each pod receives a direct API-proxy warmup. Service endpoint snapshots and native per-pod Ollama completion logs verify measured traffic distribution. Pod counts do not identify individual client requests. Resource plots and summaries retain each pod's own source timestamps. k6 emits paired request starts/completions into `request-events.jsonl`; its raw metric export and summary are retained independently for reconciliation. All use UTC timestamps. The configured load window, client-completion period and orchestration/process times are kept separate. A completed timeout does not prove that server-side work drained.

Collection integrity is separate from load thresholds: status `thresholds_failed` can retain valid evidence, while missing/mismatched request records or a failed observer invalidate collection. Tool-version and archive-hash problems are warnings; the duplicate before/after snapshots are inspection aids rather than additional validation inputs. Procedure and file schema: [pilot plan](plans/measurements-and-pilot.md#2-saved-run-format). Current verification is recorded in [STATUS.md](STATUS.md).

## Main protocol and follow-up evidence

The [main experiment methodology v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) owns the frozen peak-8 matrix. The completed main series compares fixed one, fixed three and automatic one-to-three replicas under steady and burst traffic. The separate [controlled peak-12 follow-up](../results/follow-up/comparison-20261110-205108-peak12/README.md) runs the same overload burst in all three modes. Its recovery report preserves the log-rotation incident and collector source boundary. All replicas share the same physical computer.

`--protocol-version 1.1` selects main-series behavior in the existing launcher, for every fixed/autoscaling and steady/burst combination. `bench/main_protocol.py` owns argument/matrix checks, pre-mode recovery, fresh-CPU settling and runtime identity records. `bench/analyze.py` owns primary-phase assessment and scheduled-window resource calculations, using the saved observer and request-validation records. Main fixed-mode logs establish activity without requiring server/client equality after timeouts; the preliminary rule is unchanged. assessment.json retains system terminations/restarts and not_assessable partial attempts. Analysis additionally exports assessments.json and primary-resources.json; historical client-drain summaries remain unchanged. Local tests verify these paths; STATUS.md records saved progress and limits.

The work currently uses Kubernetes YAML and scripts; no Terraform provisioning or production cloud deployment exists. See [ROADMAP.md](ROADMAP.md), [STATUS.md](STATUS.md) and [DECISIONS.md](DECISIONS.md).

Server/API readiness and model warmup are separate states. Initial replicas must finish a generation before measurement. A new replica created during scaling can accept a request before its model is warm; that request includes loading delay. Record the Ready transition separately from response observations. Native server logs identify the first observed HTTP response per pod, but do not prove its semantic success or associate it with an individual client request.

I updated the [C1 and C2 FigJam views](https://www.figma.com/board/KaoXEMPbKjCy1gOwdFdrUE/Kubernetes-PE) on 2026-10-28 to describe the implemented local prototype. C2 shows the experiment runner, k6, Service, Ollama, observer, local results and analysis, with Kubernetes as the supporting platform. The Service is a Kubernetes network object, not a separate application process. HPA and analysis are implemented; the diagram does not certify current runtime availability or an HPA performance benefit. This file owns the implementation detail and STATUS.md owns verified progress.

The [C3 view](https://www.figma.com/board/KaoXEMPbKjCy1gOwdFdrUE/Kubernetes-PE?node-id=30-56) expands the C2 experiment runner. It groups the existing functions and helpers into run control, settings/archive, preparation, observation, load control and final checks/cleanup. These components run within the Python launcher; k6 is a child process, and Kubernetes and run files are external dependencies. Mode preparation uses `main_protocol.py`, `fixed_replicas.py` and `autoscaling.py`; main-run assessment uses `analyze.py`. Arrows show responsibilities and calls, not execution order or a new code structure.

## Optional request-metric extension

`bench/custom_metric_stack.py` renders isolated Envoy/Prometheus/Adapter resources and separate CPU/Object HPA manifests into a new directory. `bench/custom_metrics.py` checks source freshness, identity, gateway request IDs and Object-metric readiness. `bench/check_custom_metric.py` performs one read-only check of the installed signal path and saves failure evidence. These three tools do not apply resources or launch measurements.

The installed chain exposes active client requests at Envoy through Kubernetes Custom Metrics API. The opt-in `bench/custom_metric_run.py` integration routes both policies through the same gateway, continuously collects the signal and gateway logs, and restores one copy after each run. `bench/prepare_custom_metric.py` owns threshold preparation; `bench/run_custom_comparison.py` runs the separate six-cell CPU/request comparison, and `bench/analyze_custom_comparison.py` assesses saved outcomes. The original CPU experiment remains available without the extension options. The [active plan](plans/custom-metric-hpa.md) records verification and remaining work.

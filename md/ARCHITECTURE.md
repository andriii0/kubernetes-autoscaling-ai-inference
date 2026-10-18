# Architecture

Updated: 2026-10-19. This describes the implemented local prototype; autoscaling remains planned.

## Runtime flow

1. `bench/inference.js` runs in k6 on Windows. It schedules calls at a configured rate per 10 seconds and posts a non-streaming request to `/api/generate`.
2. A Minikube Service tunnel exposes the Ollama Service at a Windows localhost address. The port can change when the tunnel restarts.
3. The Service in namespace `inference` routes requests to pods labelled `app=ollama`. `deploy/ollama.yaml` currently requests one replica.
4. The pod runs Ollama from `ai-inference:0.1` with bundled `qwen2.5:0.5b` weights. Ollama loads the model into its own process memory and generates the response using CPU.
5. k6 checks the completed response and records full-response duration and errors. Token counts and model-load durations are recorded only when valid, with separate availability rates. Scheduled work the generator cannot start is counted separately as dropped iterations.

The cluster is the existing Docker-backed Minikube profile `ai-lab`, configured with 8 CPU units and 12 GiB RAM on one Windows computer. These are local environment settings, not production capacity evidence. Each Ollama replica requests and is limited to 2 CPU units; memory request is 1 GiB and limit is 2 GiB. The current readiness probe checks `/api/tags`; it does not prove that the model has been loaded, so warmup is separate.

## Components and files

| Component | Implementation | Responsibility |
|---|---|---|
| Model image | `app/Dockerfile` and local ignored `app/models/` | Pin the Ollama base image and bundle downloaded weights |
| Application deployment | `deploy/ollama.yaml` | Declare the Deployment, resource settings, readiness probe and NodePort Service |
| Load generator | `bench/inference.js` | Generate steady/burst traffic and collect request metrics; short probes and five-minute one-replica steady confirmations have run; burst/multimode verification is pending |
| Workload settings | `bench/workload.json` | Share the exact request payload and k6 execution settings between warmup and measured load |
| Pilot launcher | `bench/run_pilot.py` | Exclusively create a run folder; validate one-replica state; orchestrate idle observation, warmup, k6, post-load observation and reconciliation; retain partial failures |
| Collection validator | `bench/pilot_records.py` | Check request counters and observation coverage/stability; report archive issues as warnings without modifying raw evidence |
| Observer | `bench/observe.py` | Read Kubernetes and kubelet through `kubectl`; save raw state, source timings, CPU/memory and errors as JSONL |
| Observer tests | `bench/test_observe.py` | Check parsing, counter resets, missing data, failures and output-file protection |
| Pilot analysis | `bench/analyze.py` | Reconcile saved evidence and produce CSV/JSON summaries plus aligned plots; optional Matplotlib is used only for plotting |
| Offline verification | Scripts saved in result directories | Recalculate and validate the completed observation/overhead checks |
| Evidence | `results/<run>/` | Keep configurations, raw measurements, summaries, snapshots and console output together |

`app/inference.py` and `bench/load_test.py` remain starter functions; Ollama and k6 are the active runtime. `bench/analyze.py` implements pilot analysis, not the future multi-replica scaling analysis.

## Measurement flow

The observer reads selected pods, namespace Deployments/HPA, nodes and metrics-server data. It separately queries each selected pod's node at `/api/v1/nodes/<node>/proxy/metrics/resource`. Deployment metadata may not carry the pod label, so Deployment reads cover the namespace.

Direct kubelet series provide accumulated CPU core-seconds, memory working set and source timestamps. CPU rates use differences between valid consecutive source samples; first samples, repeated timestamps and reset counters remain missing. Instance identity includes pod UID, restart count and container start time. Raw data, read timings and source errors remain in `cluster.jsonl`; failed reads are not zero usage. See [OBSERVATION.md](OBSERVATION.md) for the schema and units.

Metrics-server data describes the scaling signal. Direct node metrics describe the Minikube Linux node, including Kubernetes services; they do not measure the whole Windows host, electrical energy or monetary cost. The observer targets a 5-second polling interval, but underlying samples refresh independently.

For a pilot, the launcher reuses the observer in one background thread and saves the initial/final snapshots itself. The same observer instance retains CPU-counter continuity. A separate warmup generation precedes k6 and stays out of measured request totals. k6 emits paired request starts/completions into `request-events.jsonl`; its raw metric export and summary are retained independently for reconciliation. All use UTC timestamps. The configured load window, client-completion period and orchestration/process times are kept separate. A completed timeout does not prove that server-side work drained.

Collection integrity is separate from load thresholds: status `thresholds_failed` can retain valid evidence, while missing/mismatched request records or a failed observer invalidate collection. Tool-version and archive-hash problems are warnings; the duplicate before/after snapshots are inspection aids rather than additional validation inputs. Procedure and file schema: [pilot plan](plans/measurements-and-pilot.md#2-saved-run-format). Current verification is recorded in [STATUS.md](STATUS.md).

## Planned changes

Pilot rate selection and its summaries/plots are complete; [saved evidence](../results/pilot/discovery-2026-10-18-series1/README.md) selects low=2 and peak=8 requests per 10 seconds. The numeric main protocol, HPA configuration, three-replica comparison and main-series analysis remain unfinished. The intended main matrix compares fixed one replica, fixed three replicas and automatic one-to-three replicas under steady and burst traffic. All replicas share the same physical computer.

The work currently uses Kubernetes YAML and scripts; no Terraform provisioning or production cloud deployment exists. See [ROADMAP.md](ROADMAP.md), [STATUS.md](STATUS.md) and [DECISIONS.md](DECISIONS.md).

Server/API readiness and model warmup are separate states. Initial replicas must finish a generation before measurement. A new replica created during scaling can accept a request before its model is warm; that request includes loading delay. Record the Ready transition and the first successful generation separately. The C4 views describe target architecture. Their saved status annotations predate pilot analysis; HPA and the main comparison remain planned, while current implementation state is recorded here and in STATUS.md.

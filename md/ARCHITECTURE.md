# Architecture

Updated: 2026-10-16. This describes the implemented local prototype; autoscaling remains planned.

## Runtime flow

1. `bench/inference.js` runs in k6 on Windows. It schedules calls at a configured rate per 10 seconds and posts a non-streaming request to `/api/generate`.
2. A Minikube Service tunnel exposes the Ollama Service at a Windows localhost address. The port can change when the tunnel restarts.
3. The Service in namespace `inference` routes requests to pods labelled `app=ollama`. `deploy/ollama.yaml` currently requests one replica.
4. The pod runs Ollama from `ai-inference:0.1` with bundled `qwen2.5:0.5b` weights. Ollama loads the model into its own process memory and generates the response using CPU.
5. k6 checks the completed response and records full-response duration, errors, output-token count and model-load duration. Scheduled work the generator cannot start is counted separately as dropped iterations.

The cluster is the existing Docker-backed Minikube profile `ai-lab`, configured with 8 CPU units and 12 GiB RAM on one Windows computer. These are local environment settings, not production capacity evidence. Each Ollama replica requests and is limited to 2 CPU units; memory request is 1 GiB and limit is 2 GiB. The current readiness probe checks `/api/tags`; it does not prove that the model has been loaded, so warmup is separate.

## Components and files

| Component | Implementation | Responsibility |
|---|---|---|
| Model image | `app/Dockerfile` and local ignored `app/models/` | Pin the Ollama base image and bundle downloaded weights |
| Application deployment | `deploy/ollama.yaml` | Declare the Deployment, resource settings, readiness probe and NodePort Service |
| Load generator | `bench/inference.js` | Generate steady/burst traffic and collect request metrics; only short steady checks have run |
| Observer | `bench/observe.py` | Read Kubernetes and kubelet through `kubectl`; save raw state, source timings, CPU/memory and errors as JSONL |
| Observer tests | `bench/test_observe.py` | Check parsing, counter resets, missing data, failures and output-file protection |
| Offline verification | Scripts saved in result directories | Recalculate and validate the completed observation/overhead checks |
| Evidence | `results/<run>/` | Keep configurations, raw measurements, summaries, snapshots and console output together |

`app/inference.py`, `bench/load_test.py` and `bench/analyze.py` are starter functions. They are not the running inference server, active load generator or completed general analysis pipeline.

## Measurement flow

The observer reads selected pods, namespace Deployments/HPA, nodes and metrics-server data. It separately queries each selected pod's node at `/api/v1/nodes/<node>/proxy/metrics/resource`. Deployment metadata may not carry the pod label, so Deployment reads cover the namespace.

Direct kubelet series provide accumulated CPU core-seconds, memory working set and source timestamps. CPU rates use differences between valid consecutive source samples; first samples, repeated timestamps and reset counters remain missing. Instance identity includes pod UID, restart count and container start time. Raw data, read timings and source errors remain in `cluster.jsonl`; failed reads are not zero usage. See [OBSERVATION.md](OBSERVATION.md) for the schema and units.

Metrics-server data describes the scaling signal. Direct node metrics describe the Minikube Linux node, including Kubernetes services; they do not measure the whole Windows host, electrical energy or monetary cost. The observer targets a 5-second polling interval, but underlying samples refresh independently.

## Planned changes

HPA configuration, a three-replica comparison, pilot rate selection, correlated per-request events and a reusable analysis pipeline remain unfinished. The intended main matrix compares fixed one replica, fixed three replicas and automatic one-to-three replicas under steady and burst traffic. All replicas share the same physical computer.

The work currently uses Kubernetes YAML and scripts; no Terraform provisioning or production cloud deployment exists. See [ROADMAP.md](ROADMAP.md), [STATUS.md](STATUS.md) and [DECISIONS.md](DECISIONS.md).

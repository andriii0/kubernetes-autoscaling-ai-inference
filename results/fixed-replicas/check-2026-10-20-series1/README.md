# Preliminary three-copy check

Date: 2026-10-20 UTC. This checks three fixed copies after the one-copy pilot. It is not the main comparison and does not set an acceptable response-time target.

## Setup and results

The existing `ai-lab` cluster was stopped, while Docker was running. It was restarted with `minikube start -p ai-lab`. The Ollama Deployment was scaled to three. Docker retained its 8-CPU/12-GiB limit. Each copy has a 2-CPU limit and a 1-GiB memory request/2-GiB limit. No HPA targets the Deployment.

The model image, request settings, k6, kubectl/server, Docker and Minikube version records match the saved one-copy peak run. All successful measured responses have 56–56 output tokens. Every copy finished its own warmup generation through the Kubernetes pod proxy before load. Warmup times include the API proxy and CLI; they are not direct service-response timings. Ready transitions and generation completion times are in each `warmup.json`.

Both checks sent 8 requests per 10 seconds through the real Service tunnel. The 30-second check came first. Each run retained 60 seconds of idle observation, per-pod warmup, scheduled load/client completion and 10 seconds afterward. No new latency threshold was set; the existing error<=1% and zero-drop guards remained active. I ran no concurrent tests or benchmarks during measurement; unrelated Windows activity was not audited.

| Run | Scheduled seconds | Success/total | Failures | Mean, seconds | p95, seconds |
|---|---:|---:|---:|---:|---:|
| [service-check](service-check/metadata.json) | 30 | 25/25 | 0 | 1.050 | 1.089 |
| [peak-1](peak-1/metadata.json) | 300 | 241/241 | 0 | 1.056 | 1.109 |

Both collections reconcile and have zero dropped or unfinished client requests and no observation errors. Pod identities and restart counts stay fixed during each check. The old pod had three earlier restarts after cluster startup; the new pods had zero. Those existing counts are not restarts during measurement.

## Traffic and resources

The Service's saved endpoint slices match the three selected ready pods. Native Ollama access logs count generation completions during the k6 process interval. Per-pod totals match completed client requests, and HTTP status counts match client HTTP statuses. Readiness GETs and earlier warmups are excluded. This is aggregate distribution evidence, not an individual client-request-to-pod mapping. Missing logs, unmatched counts or a pod with no measured requests invalidate the three-copy check.

| Pod | Five-minute requests | Mean CPU, cores | Peak memory, MiB |
|---|---:|---:|---:|
| ollama-7db4f544df-zw88n | 90 | 0.742 | 856.33 |
| ollama-7db4f544df-rkglm | 85 | 0.631 | 524.43 |
| ollama-7db4f544df-fwc9h | 66 | 0.543 | 520.34 |

Kubelet updates the pods at different source times. The plots and `analysis/per-replica-resources.json` keep each pod's own timestamps. Total resource fields remain empty when samples do not align. CPU means average available source intervals; they do not measure Windows-wide energy or cost.

## Interpretation and limits

The saved one-copy five-minute peak runs had p95 28.247 and 16.447 seconds, with 13 and 0 timeouts. This three-copy check has p95 1.109 seconds and 0 failures. It is a preliminary observation from one repetition on a different date, not a controlled repeated main comparison. Three copies also have a larger combined CPU budget. The repeated prompt may use caching.

The runtime is left at three copies. The source Deployment file still defaults to one; applying it resets that count. The temporary Service tunnel is closed after verification. The final response-time/error targets, main protocol, repeat order, HPA and full comparison remain unfinished. Roadmap steps 17 and 18 remain open pending the agreed comparison procedure.

## Reproduce

Follow [fixed replica preparation](../../../md/plans/fixed-replicas.md) and [the execution procedure](../../../md/plans/scaling-experiment.md#1-manual-replica-comparison). Open a new Service tunnel and supply its current address; use new output paths:

```powershell
python bench/run_pilot.py --base-url "$env:BASE_URL" --replicas 3 --rate 8 --duration 30s --run-dir results/fixed-replicas/NEW/service-check
python bench/run_pilot.py --base-url "$env:BASE_URL" --replicas 3 --rate 8 --duration 5m --run-dir results/fixed-replicas/NEW/peak-1
python bench/analyze.py results/fixed-replicas/NEW/service-check results/fixed-replicas/NEW/peak-1 --output-dir results/fixed-replicas/NEW/analysis
```

Each run archives its exact executable inputs, configuration snapshots, warmups, logs and measurements. Historical pilot files were preserved. See [analysis](analysis/README.md), [raw peak events](peak-1/request-events.jsonl), [warmups](peak-1/warmup.json), [Service endpoints](peak-1/service-route.json) and [collection check](peak-1/collection-check.json). Portflow submission remains separate.

All 59 bench tests passed, including failed warmup, restart, wrong endpoints, missing logs and malformed HTTP-200 response cases. After collection, I refined the validator to compare server/client HTTP statuses independently of model-response success. Both live runs remain valid under the original and refined rules; their archived inputs are unchanged. [Independent verification](verification.json) compares event-derived mean/p95 with k6 and saved analysis, and records source changes after measurement.

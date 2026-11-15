# Preliminary HPA check

Run date: 2026-10-20 UTC. This is one mechanism check before the frozen main protocol.

## Conditions

The existing ai-lab Minikube cluster ran Ollama/Qwen2.5 0.5B on CPU. Each copy requested and was limited to 2 CPU cores; memory request/limit was 1/2 GiB. The cluster's Docker limits were 8 CPU units and 12 GiB. All copies shared one Windows host. The saved workload keeps the prompt, 64-token maximum, context 1024, two threads, temperature 0 and seed 42.

The launcher reset to one copy, observed idle for 60 seconds and separately warmed the initial model. It attached HPA (1-3 copies, CPU utilization target 60%, downscale stabilization 300 seconds), then required two numeric CPU/ScalingActive one-copy samples. New copies received normal Service traffic without separate warmups. The burst used 2 -> 8 -> 2 requests per 10 seconds over 782 seconds. After k6 finished, collection continued for 300 seconds without new requests. That period is separate from low traffic.

## Request results

Client counts: 336 started, 336 completed and 336 successful; no failed, unfinished or dropped requests. Successful-response mean: 2.848 s; p95: 9.007 s; maximum: 13.987 s. Successful latency excludes failed responses; the error counts must be read alongside it. Request-start time determines the phase; a request can finish in a later phase.

| Phase | Seconds | Completed | Successful | Failed | Successful p95, s |
|---|---:|---:|---:|---:|---:|
| low-before | 0-120 | 23 | 23 | 0 | 1.545 |
| rise | 120-121 | 1 | 1 | 0 | 1.350 |
| peak | 121-421 | 240 | 240 | 0 | 9.972 |
| fall | 421-422 | 0 | 0 | 0 | missing |
| low-after | 422-782 | 72 | 72 | 0 | 1.546 |

## Scaling observations

Growth confirmed: True. Reduction confirmed: True.

- growth: desired 1 -> 2 at 186.8 s; matching non-terminating running count at 186.8 s.
- growth: desired 2 -> 3 at 307.0 s; matching non-terminating running count at 307.0 s.
- reduction: desired 3 -> 1 at 772.8 s; matching non-terminating running count at 772.8 s.

Pods marked for deletion are excluded from the non-terminating running count; their first absence is recorded separately. These times come from sampled HPA/pod state, not an exact trace of controller decisions. See [scaling.json](analysis/scaling.json) for conditions, CPU scaling signals, Ready/creation/deletion observations and the separate no-new-request period.

| UID prefix | Pod | HTTP responses after load start | First observed HTTP response, UTC |
|---|---|---:|---|
| 7b9728ed | ollama-7db4f544df-rkglm | 187 | 2026-10-20T15:25:59.392864556Z |
| c643e131 | ollama-7db4f544df-w2f4c | 86 | 2026-10-20T15:29:06.264332724Z |
| d31b5463 | ollama-7db4f544df-xqzvb | 63 | 2026-10-20T15:31:04.958827480Z |

Server logs show HTTP completions and aggregate per-pod activity. They do not identify individual client requests or prove a nonempty model answer. Client semantic success comes from the request events. Timeouts may leave server processing after the client finishes; equal client/server counts are not required here. Server-side drain remains unproven.

## Collection and verification

Collection valid: True. Collection errors: []. Resource-gap samples: 0. Log coverage complete: True.

Before load, all 76 bench tests passed, including negative cases and a shortened real-k6 burst against simulated Kubernetes. Kubernetes accepted a server dry-run of the HPA manifest. Event calculations agree with k6 and analysis, and archived inputs match their hashes. See [verification.json](verification.json), [preflight.json](preflight.json) and [test output](bench-tests-before-load.txt).

Per-pod resource summaries use their own source clocks. Asynchronous CPU rates are not summed, and missing values stay missing. See [per-replica-resources.json](analysis/per-replica-resources.json) and the [aligned plot](analysis/01-burst-1.png).

Restoration succeeded: HPA was removed and one ready copy remained. [Recovery diagnostics](burst-1/recovery.json) are separate from collection validity.

After final code review, all 79 tests passed. Review tightened apply timestamps, route evidence, phase boundaries and log shutdown. The current collector differs from the archived run version; [verification.json](verification.json) lists those files. Both the original and current validators accept the saved run. Raw inputs and the original collection verdict remain unchanged.

## Limits

One run can verify observed scaling transitions and the collection path. It cannot establish an HPA performance advantage. The repeated fixed-one/fixed-three/autoscaling comparison, accepted latency target and final protocol remain unfinished. This experiment measures container/node resources, not Windows-wide energy or cost.

Raw evidence: [burst-1](burst-1/metadata.json), [collection check](burst-1/collection-check.json), [analysis summary](analysis/summary.csv).

I saved the report and graph in [Notion](https://app.notion.com/p/3fec7c697bfd81738d08d5527424af20), section HPA check.

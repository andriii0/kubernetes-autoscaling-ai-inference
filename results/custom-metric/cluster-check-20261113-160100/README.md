# Installed custom-metrics chain check

I deployed and checked Envoy -> Prometheus -> Prometheus Adapter -> Kubernetes Custom Metrics API in `ai-lab` on 13 November 2026. The chain passed the idle and three-request checks. I did not install an HPA or run a comparative series.

## Installation

I first checked every proposed resource name and all APIService registrations. There were no conflicts. `bundle/stack.json` passed server-side validation, then `kubectl create` created its 21 infrastructure resources. The separate `bundle/hpa-*.json` files were not applied. Original inputs, configuration hashes, server validation and creation output remain in this folder.

The server is Kubernetes 1.37.0. The node advertises 24 CPU and about 31 GiB, but Docker actually limits this Minikube container to 8 CPU and 12 GiB. I used the Docker limits when checking headroom. The new stack requests 0.3 CPU and 320 MiB in total, with combined limits of 1.5 CPU and 1 GiB. An idle snapshot after the check showed about 5 millicores and 89 MiB for the three components; this is a snapshot, not an overhead study.

I retained the candidate versions. Actual image identities are saved in `image-identities.json`:

| Component | Version | Image digest |
|---|---|---|
| Envoy | 1.35.0 | `sha256:cfe1c570e72aa4207853a37bd1c32c808a0036a351b16f73732dcfd0e5775175` |
| Prometheus | 3.5.0 | `sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996` |
| Prometheus Adapter | 0.12.0 | `sha256:932eae60e2bcf9c4660d6442da066ef1a79b4ea7cc232c61c7303069216ca006` |

`installed-objects.json` contains the effective resources. All three pods were Ready with zero restarts at the end. The custom-metrics API and the original metrics-server API were both available.

## First checker failure

API discovery initially reported unavailable while the Adapter was starting, then became available without a configuration change. The first idle check still failed: Adapter 0.12.0 returned the core Service API version as `/v1`, while my validator accepted only `v1`. The namespace, Service name and metric value were correct.

I retained [that failed check](idle-attempt-01/check.json), accepted only the two core-v1 spellings, and added a regression test that still rejects another group, version, kind, namespace or name. All 16 focused unit tests passed. [The second idle check](idle-attempt-02/check.json) passed. `inputs/` holds the pre-fix source; `verified-inputs/` and `checker-fix-sha256.json` record the correction. No deployed configuration needed changing.

## Three controlled inference requests

[The functional request check](requests-attempt-01/result.json) passed. I sent exactly three concurrent, non-streaming requests through Envoy to the existing Ollama Service. All returned HTTP 200, completed output and 512 generated tokens. Client durations were 11.861, 30.992 and 21.564 seconds.

These are diagnostic requests, not the benchmark workload: I used a longer prompt/output limit and a 90-second client timeout so that five-second scrapes could observe active work. I did not change Ollama's Deployment, resources or Service. I make no latency-target or capacity claim from these requests.

The verified signal sequence was `0 -> 3 -> 3 -> 2 -> 1 -> 1`, followed by fresh zeros. Each accepted observation matched Prometheus with the Custom Metrics API and checked the gateway pod UID and original source timestamp. Across ten validated observations, the oldest source sample was about 5.39 seconds old, below the 10-second limit. No sample failed validation.

I required two distinct zero scrapes after the final client response. The existing backend quiet gate passed before and after the requests. All three client IDs matched exactly one gateway access record; the native Ollama log is also retained separately in `backend-log.json`. The gateway count does not establish that the backend has drained, and its IDs do not add request-ID attribution to native Ollama logs.

`live-query-failure-checks.json` checks the same PromQL against the running Prometheus: the current source returned a sample, a source pinned 30 seconds in the past returned no sample, and a deliberately missing source returned no sample. Neither case produced an invented zero. These were read-only query tests, not a live outage of the installed Adapter.

## Preserved state and limits

Ollama's Deployment spec, Service spec, pod UID and container ID matched the initial snapshots. Its existing restart count remained three; the new components did not restart. HPA remained absent. `ai-lab-repro24` remained stopped. I closed the temporary local gateway port-forward and left the requested infrastructure running.

This establishes the installed signal path with a few real requests. It does not establish HPA behavior, sustained overhead, recovery from an installed-stack outage or full experiment collection. The Adapter API registration still uses the documented local self-signed TLS setup. Continuous collection, source/configuration-change detection during a run, cleanup integration, the separate comparison driver and analysis remain outside this deployment check.

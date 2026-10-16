# Cluster and resource observation

`observe.py` uses Python's standard library and the installed `kubectl`. It only reads the explicitly selected cluster. Defaults are context `ai-lab`, namespace `inference`, and selector `app=ollama`.

```powershell
python .\bench\observe.py .\results\my-run\cluster.jsonl --duration 150
```

The output must be a new file. Without `--duration`, stop with Ctrl+C. Options `--interval` (default 5 seconds) and `--timeout` (default 5 seconds per command) must be positive. Collection time is included in the target interval; slow collections may overrun it. An in-progress collection finishes before the duration stop is checked, so the duration is not a hard subprocess deadline.

Exit codes: 0 means at least one sample and no collection errors; 1 means collection errors or no complete samples; 2 means an argument or output-file error. Recorded collection errors remain visible even if a later sample succeeds.

## JSONL record

Each line contains `schema_version: 1`, a UTC `time`, `collection_finished_at`, collection duration/overrun, context, namespace and selector, followed by:

- `pods`, `deployments`, `hpa`, `nodes`: raw Kubernetes JSON. Deployments and HPA include the whole selected namespace because their own labels need not match pod labels. Pod conditions, desired/available replicas, restarts, image identity and requested/limited resources remain available for analysis.
- `resources`: raw metrics-server response, including its measurement timestamps and windows. This is the scaling signal, not resource accounting.
- `kubelet`: per-node raw `/metrics/resource` text and parsed resource series, obtained through `/api/v1/nodes/<node>/proxy/metrics/resource`.
- `resource_usage`: normalized records for selected application containers and their nodes. Other containers on the node remain in the raw payload but are excluded from normalized application records.
- `sources`: start/end UTC times for each sequential API read. A sample is not an atomic cluster snapshot.
- `errors`: source-specific errors; failed API reads are `null`, never zero. Malformed kubelet payloads remain saved for diagnosis. A kubelet-reported scrape error also invalidates that sample's derived resource observations.

An empty HPA list is valid before autoscaling is configured. Missing resource series for running containers, or missing node CPU/memory, are reported. A Ready pod is an operational readiness observation; it does not prove that a newly started model has finished loading.

## Units and scope

`cpu_usage_seconds_total` is accumulated CPU core-seconds. `cpu_cores` is its difference divided by the difference between source timestamps in seconds. A value of 2 means an average of two CPU units over that source interval. If source timestamps are unavailable, collection monotonic time is used and `cpu_clock` records that fallback. CPU differences reset on changed pod UID, restart count or container start time, missing samples, and counter resets. First observations, repeated timestamps and invalid intervals produce `null` CPU rates.

`memory_working_set_bytes` is a working-set measurement in bytes, not the container's memory limit, Windows RAM usage or a complete memory-accounting total. Divide by 1,048,576 to display MiB. CPU requests and limits remain in the raw pod specification; usage is not a percentage of the node unless the chosen denominator is explicitly applied.

The node measurements describe the Minikube Linux node. They include Kubernetes services and observer-related API work; they do not measure the whole Windows computer or electrical energy. Five-second polling may return repeated underlying resource samples. Preserve those source timestamps; do not interpolate missing CPU measurements into zeros.

## Verification

```powershell
python -m unittest discover -s bench -p test_observe.py -v
```

Tests cover unit interpretation, stale timestamps, counter resets, restarts/replacements, missing and malformed data, scrape errors, source timeouts, unrelated pods, empty HPA lists, nonzero failure exits, and protection against overwriting output.

The first live check is saved in `results/observation-check-2026-10-16-verified/`. See that directory's README for measurements and limitations. Pilot rate selection, per-request event records and automated result analysis are separate remaining work.

Sources: [kubelet resource metrics](https://kubernetes.io/docs/reference/instrumentation/metrics/), [metrics-server limitations](https://github.com/kubernetes-sigs/metrics-server).

## Repeated overhead check

Four counterbalanced low-load pairs are saved in [the overhead report](../results/observer-overhead-2026-10-16-series1/README.md). Median paired mean latency changed by +5.22% and p95 by +3.95%. The existing 5-second observer meets the frozen provisional budget in this low-load series. Retain it provisionally for pilot measurements. This screening result does not prove negligible overhead at higher load or general equivalence.

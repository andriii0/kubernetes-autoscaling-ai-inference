# Project status

Updated: 2026-10-18. The integrated collector has a saved low-load check; this is not a capacity pilot.

## Verified

- Integrated collection now validates one-replica state, observes idle state, warms the model, runs k6 and reconciles request/resource records. Archive/version diagnostics warn; duplicate snapshots are not revalidated.
- [Live collection check](../results/pilot/20261018T202951240Z-collection-check/README.md): 12 successful paired requests, 29 observations, no failed/dropped/unfinished work or collection errors.
- The current bench suite has 43 passing tests. [Targeted negative-test verification](plans/data-collection/verify-tests.py) confirms disabled unfinished-request, time-order and gap checks are caught. The revised lifecycle case passed ten repeats; the original isolated failure was not reproduced.

- One ready Ollama CPU replica in the existing `ai-lab` cluster; no HPA. Restart count stayed unchanged during the final check.
- `bench/observe.py` saves read-only cluster state, metrics-server scaling input, raw kubelet resource series and normalized CPU/memory values. It preserves source timestamps and errors, detects invalid counter differences, and refuses to overwrite existing files.
- 16 focused tests passed. Real CLI checks confirmed a missing context returns 1 and an existing output file returns 2 without changing it.
- [Live verification](../results/observation-check-2026-10-16-verified/README.md): 30 samples, zero collection errors, and 12 successful measured requests. Original metrics and request aggregates were cross-checked independently.
- Roadmap steps 14 and 15 are complete. Steps 1-12 remain complete from earlier evidence; step 13 is still open.
- [Repeated overhead verification](../results/observer-overhead-2026-10-16-series1/README.md): four pairs, 195 requests, paired median mean change +5.22% and p95 change +3.95%. The practical budget was met; this is not proof of general equivalence.

## Remaining

- Remaining technology research in `md/DECISIONS.md` is still open; the final experiment protocol has not been frozen.
- `bench/analyze.py` is still a starter; pilot summaries and plots are not implemented.
- Increasing-load pilot, selected low/peak rates, latency target, three-replica comparison and autoscaling experiments remain unfinished.

## Next step

Finish minimal pilot analysis. The repeated observer-overhead check meets the provisional low-load budget; retain the 5-second interval while recording it in pilot metadata. Then execute independent one-replica probes at 2, 5 and 10 requests per 10 seconds, inspecting each result before increasing load. Follow `md/plans/measurements-and-pilot.md` and finish decision records before the main comparison.

## Limits

The verification is a short warm-model check on one physical computer. The initial observer-off/on pair was followed by four counterbalanced pairs. Even these repeats cannot establish general equivalence, capacity or an autoscaling advantage. Direct metrics describe the Minikube node and selected containers, not Windows-wide resource usage or electrical energy. Raw samples update less often than the target 5-second polling interval.

## Documentation and version control

Canonical documentation now lives under `md/`, with root `AGENTS.md` and `README.md` as entry points. Setup and observation guides, platform research and teacher feedback are included. Result evidence remains alongside each run. Word authoring artifacts stay in the separate document workspace; required portfolio submission remains Fontys Portflow.

The code directory is now a Git repository on branch `main`, with private GitHub repository [andriii0/kubernetes-autoscaling-ai-inference](https://github.com/andriii0/kubernetes-autoscaling-ai-inference). The first snapshot includes source, Markdown and saved experiment evidence; downloaded model weights, caches and credential/environment files are excluded.

Documentation migration checks passed: 55 local links/anchors and 21 focused tests. A flaky test was corrected to read all JSONL records rather than assume a timing-dependent single record. Runtime scripts and original evidence were unchanged. Source/document text defaults to LF; the measured load script and `results/` retain their original bytes so historical source hashes remain valid.

# Project status

Updated: 2026-10-19. The one-replica pilot completed on 2026-10-18 UTC, including two five-minute confirmations at each selected rate. Collection and analysis have saved evidence; this does not certify runtime availability at a later time.

## Implemented and verified

- The saved local baseline is one Ollama CPU replica, reached through its Kubernetes Service, with k6 generating requests. See the [deployment check](../results/smoke-2026-10-04/smoke.json) and [load check](../results/k6-smoke-2026-10-04/README.md).
- `bench/observe.py` records cluster state, metrics-server scaling input and direct kubelet resource measurements, preserving errors and missing values. See the [live verification](../results/observation-check-2026-10-16-verified/README.md).
- The observer setting was retained provisionally for the completed pilot; the [overhead report](../results/observer-overhead-2026-10-16-series1/README.md) owns the measurements and limits. See [DECISIONS.md](DECISIONS.md#7-retain-a-5-second-observer-interval-provisionally) for the accepted setting.
- The pilot launcher refuses existing run paths, optional k6 measurements retain missingness, and historical analysis validates observation times. Completed checks and evidence-preservation results are in the [integrity plan](plans/measurement-integrity.md) and [verification record](plans/measurement-integrity/GATES.md).
- `bench/run_pilot.py` integrates initial state validation, idle observation, separate model warmup, k6 load, post-load observation and final reconciliation. Workload settings are shared; per-request events and run context are saved. Missing/mismatched archive hashes and failed version diagnostics now warn rather than invalidate measurements; duplicate boundary snapshots are no longer revalidated. Evidence: [live collection check](../results/pilot/20261018T202951240Z-collection-check/README.md) and [test verification](plans/data-collection/GATES.md).
- `bench/analyze.py` produces pilot CSV/JSON summaries and aligned PNG/SVG plots. Six focused tests and raw/k6 comparisons verify the calculations; Matplotlib is an optional analysis dependency.
- [The saved pilot](../results/pilot/discovery-2026-10-18-series1/README.md) selects low=2 and peak=8 requests/10 s, with two five-minute repetitions each. Low p95 is about 1.43 s; peak p95 is 16.45-28.25 s, with variable timeouts. All eight valid runs reconcile. An initial timestamp-boundary diagnostic remains excluded; the bounded 1-ms recording fix has a regression test. All 50 tests passed after the pilot.

## Remaining work and limits

- The numeric protocol, HPA configuration, three-replica comparison and main autoscaling experiment are unfinished. `bench/load_test.py` and `app/inference.py` remain starters; main scaling analysis is future work.
- The numeric experiment protocol and latency target must be frozen after the pilot. Server Ready and first successful generation are distinct; the extra per-replica timeline instrumentation is still planned.
- All replicas share one computer. The pilot selects useful comparison rates, not a precise stable capacity limit, general equivalence or an autoscaling advantage. Resource measurements cover the Minikube node and selected containers, not Windows-wide energy or cost.
- Research v0.7 and C4 describe the accepted protocol and target architecture. `docs/PDP.pdf` is historical; the current practical scope is inference-only in Notion. Export/submission ownership is in [docs/README.md](../docs/README.md); required Portflow submission is not confirmed by local storage.

## Next action

Active plan: [Measurements and pilot load tests](plans/measurements-and-pilot.md). The [pilot discovery series](../results/pilot/discovery-2026-10-18-series1/README.md) is complete. Next, record and freeze `md/plans/experiment-protocol.md` (roadmap step 17), using the selected rates and an explicitly justified latency/error target. Then verify three replicas; recheck live state when resuming. The simple English [getting started guide](GETTING_STARTED.md) owns setup commands and points to the plans; the future [scaling experiment procedure](plans/scaling-experiment.md) preserves the detailed later steps and is not yet active. Milestones and completion criteria remain in [ROADMAP.md](ROADMAP.md).

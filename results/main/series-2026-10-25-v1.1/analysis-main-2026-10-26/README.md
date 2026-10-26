# Completed main-series analysis

All 18 planned cells are included. See main-runs.csv for individual runs and mode-profile.csv for all three p95 values and their median. A median of run p95 values is not a pooled request percentile. Request counts and primary phases remain explicit. Raw files and existing per-attempt outputs are read only.

To reproduce from the repository root, select a new output directory:

```powershell
.\.venv\Scripts\python.exe -B bench/summarize_main.py results/main/series-2026-10-25-v1.1 --output-dir results/main/series-2026-10-25-v1.1/analysis-rerun
```

The command writes the group/run/resource/phase/scaling CSV files, replay validation and PNG/SVG plots. It refuses an existing destination. --no-plots retains all CSV/JSON outputs without Matplotlib.

The existing analyzer produces the aligned per-run latency/outcome/Ready/CPU/memory plots and historical whole-run summary. These use completion timestamps for plotted points; primary phases use request-start membership in primary-phases.csv and the primary-p95 plot. All points in that plot are actual repetitions. The 5-second target applies to primary successful p95, not every individual response. Error acceptance is assessed separately.

CPU core-seconds are source-interval estimates for the scheduled window only. Incomplete application totals remain empty. Per-instance observed memory peaks are not summed. Node data includes Kubernetes and is not added to application consumption. Ready copy-seconds use a left-step interpolation of observed state; they describe available capacity, not CPU consumption, reservation or cost.

Frozen workload/input hashes, initial model digests/image IDs and recorded runtime fields match. The docker_limits field was obtained from docker info: it describes the engine scope, not an independently inspected Minikube-container quota. Profile settings and Kubernetes capacity are separate scopes.

The series spans interruptions and a cluster restart before attempt 11. Repetition 2 steady straddles that restart. Main targets were retained, while the severe historical pilot degradation did not repeat; these data do not isolate its cause. Shared-host drift, repeated prompt/prefix caching, a small model and three repetitions limit causal or production conclusions. Keep all outcomes; do not retune this series to force a scaling benefit.

validation.json records replay results and warnings. Target passes do not establish an HPA advantage or full resource coverage. Normal server drain, Windows-wide energy and monetary savings are not verified. The final Notion findings and reproduction review remain separate project steps.

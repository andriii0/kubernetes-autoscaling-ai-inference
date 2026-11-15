# AI Inference Autoscaling

This is an independent research project about scaling AI inference when request load changes. The work starts with a short comparison of container orchestration platforms, then uses one selected platform for a local prototype and repeatable measurements. It is separate from the SUE group infrastructure.

## Practical research question (SQ4)

How effectively does Kubernetes autoscale this local AI inference service as traffic changes, and what limits did I observe? The [Research Document](<docs/PDP Research document.docx>) also compares platforms for inference and agent workloads. The practical tests cover inference only.

The [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd), agreed on 2026-10-21, defines the main acceptance targets and comparison rules. The 5-second successful-response p95 target is an explicit study assumption for a short complete answer, not a validated user requirement. The completed main series compares a fixed number of inference instances with automatic scaling under steady and burst traffic. It records request latency, throughput, errors, resource use, replica count and observed scaling reaction.

## Inference Lab

I use this local Windows UI to browse saved series and runs, inspect metrics and plots, and call the existing launchers. From the checkout root:

```powershell
.\.venv\Scripts\python.exe -B -m lab
```

The browser opens at `http://127.0.0.1:8765`. Browsing needs only Python 3.12+; no cluster or additional Python packages are needed. The Runs tab offers a configurable pilot and existing v1.1 continuation. Dry run is selected initially. The Results tab browses saved evidence. See [UI setup and limits](md/GETTING_STARTED.md#inference-lab), [Runs](md/assets/inference-lab-runs.png) and [Results](md/assets/inference-lab.png).

## Documentation

Start with [current status](md/STATUS.md) for progress, the [setup guide](md/GETTING_STARTED.md) for commands, or [Fontys documents](docs/README.md) for research, PDP, diagrams and saved feedback.

- [Roadmap](md/ROADMAP.md): milestones and completion criteria.
- [Status](md/STATUS.md): verified progress and remaining work.
- [Architecture](md/ARCHITECTURE.md): implemented components and runtime flow.
- [Decisions](md/DECISIONS.md): choices, alternatives and limitations; [detailed technology decisions in Notion](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a) explains Qwen, Ollama, CPU, k6 and CPU-based HPA.
- [Getting started](md/GETTING_STARTED.md).
- [Task plans](md/plans/) and [teacher feedback](md/meeting/teacher-feedback.md).

## Project layout

- `docs/`: collected Fontys documents, PDF exports and course references; see its index for ownership.
- `md/`: technical context, concise decisions, meeting notes and task plans. Detailed technology research is maintained in Notion.
- `app/`: Ollama image definition and local ignored model weights.
- `deploy/`: reproducible local environment and deployment configuration.
- `bench/`: load generation, observation, and result analysis.
- `lab/`: local Results browser and experiment-launch adapters; `tests/lab/` checks its readers and controls.
- `tests/bench/`: local collection, lifecycle and analysis tests with shared fixtures.
- `results/`: run settings, raw measurements, and generated figures.

The [Findings](https://app.notion.com/p/40fc7c697bfd81bbb00fcf67a8c3d00c) answer SQ4 using the saved main series, controlled peak-12 follow-up and separate CPU/request comparison.

## Research workflow

I defined one inference workload and two load profiles, compared suitable orchestration platforms and documented the choice. I then built the local environment, ran a pilot and fixed the model, request format, resource limits and latency target before the main series. The saved raw data and configuration let me replay the analysis and check the findings.

## Current state

The separate [six-run CPU/request HPA comparison](results/custom-metric/series-20261114-191048/README.md) is complete. Active-request HPA improved peak on-time success in all three pairs, but met all service targets in only 1/3 runs versus CPU 0/3. Its preparation, clock environment and capacity tradeoff stay separate from the earlier experiments.

The implemented path uses Ollama for inference, k6 for load generation and `bench/observe.py` for cluster/resource observations. The 18-run main matrix at peak 8 is complete. [Comparative tables and plots](results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/README.md) show that all three modes met the targets, including one fixed copy. The later [controlled peak-12 comparison](results/follow-up/comparison-20261110-205108-peak12/README.md) uses the same burst for fixed one, fixed three and HPA, with three repetitions per mode. Fixed three handled the overload best; HPA reduced failures but missed the five-second latency target in all three repetitions. The [step 24 reproduction check](results/reproduction/check-2026-11-06/README.md) passed in a fresh setup on the same Windows host. See [STATUS.md](md/STATUS.md) for current verification and limits.

The 5,189 successful requests belong only to the 18 main v1.1 runs at peak 8 requests/10 s. The later rate-selection pilots selected low 2 and peak 12. Their preliminary fixed-three and HPA checks used different traffic and were not directly comparable. The final peak-12 follow-up fixes that gap by running the same burst in all three modes. It remains separate from protocol v1.1 and does not replace the main series.

Saved checks are available for [deployment](results/smoke-2026-10-04/smoke.json), [load generation](results/k6-smoke-2026-10-04/README.md), [observation](results/observation-check-2026-10-16-verified/README.md), [the original pilot](results/pilot/discovery-2026-10-18-series1/README.md) and [the original preliminary three-copy check](results/fixed-replicas/check-2026-10-20-series1/README.md). They do not establish current cluster availability or maximum capacity. Use the [setup guide](md/GETTING_STARTED.md) for restart and run commands.

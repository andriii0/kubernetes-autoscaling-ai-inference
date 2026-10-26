# AI Inference Autoscaling

This is an independent research project about scaling AI inference when request load changes. The work starts with a short comparison of container orchestration platforms, then uses one selected platform for a local prototype and repeatable measurements. It is separate from the SUE group infrastructure.

## Research question

How effectively can the selected container orchestration platform autoscale AI inference under changing load while keeping latency acceptable?

The [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd), agreed on 2026-10-21, defines the main acceptance targets and comparison rules. The 5-second successful-response p95 target is an explicit study assumption for a short complete answer, not a validated user requirement. The completed main series compares a fixed number of inference instances with automatic scaling under steady and burst traffic. It records request latency, throughput, errors, resource use, replica count and observed scaling reaction. Final findings remain to be written.

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
- `results/`: run settings, raw measurements, and generated figures.

The final findings belong in a separate Notion document in roadmap step 23, with links to supporting raw measurements.

## Planned workflow

Define one inference workload and two load profiles. Compare suitable orchestration platforms against the stated criteria and document the choice. Build the local environment, run a pilot, and lock the model, request format, resource limits, and latency target. Repeat the fixed-capacity and autoscaling scenarios with the same settings. Keep raw data and configuration for each run so the findings can be checked and reproduced.

## Current state

The implemented path uses Ollama for inference, k6 for load generation and `bench/observe.py` for cluster/resource observations. Pilot rate selection and pilot CSV/JSON summaries and plots are implemented; a preliminary three-copy check is saved. A [preliminary HPA check](results/autoscaling/check-2026-10-20-series1/README.md) verifies growth and reduction. Protocol agreement is complete. The existing launcher/analyzer now support protocol v1.1 and the manual matrix (step 20), with local verification. The 18-run main matrix is complete; the [initial series record](results/main/series-2026-10-25-v1.1/README.md) preserves preparation, the first ten attempts and their pause checkpoint. [Comparative tables and plots](results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/README.md) are saved. All modes meet the agreed targets, including one fixed copy; an HPA advantage is not established. The final findings and reproduction review remain unfinished. Recheck runtime readiness before any additional approved load. See [STATUS.md](md/STATUS.md) for verification dates, limitations and the active plan, and [ARCHITECTURE.md](md/ARCHITECTURE.md) for implementation details.

Saved checks are available for [deployment](results/smoke-2026-10-04/smoke.json), [load generation](results/k6-smoke-2026-10-04/README.md), [observation](results/observation-check-2026-10-16-verified/README.md), [the completed pilot](results/pilot/discovery-2026-10-18-series1/README.md) and [the preliminary three-copy check](results/fixed-replicas/check-2026-10-20-series1/README.md). They do not establish current cluster availability or maximum capacity. Use the [setup guide](md/GETTING_STARTED.md) for restart and run commands.

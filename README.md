# AI Inference Autoscaling

This is an independent research project about scaling AI inference when request load changes. The work starts with a short comparison of container orchestration platforms, then uses one selected platform for a local prototype and repeatable measurements. It is separate from the SUE group infrastructure.

## Research question

How effectively can the selected container orchestration platform autoscale AI inference under changing load while keeping latency acceptable?

The acceptable p95 latency limit will be set after a small pilot run and before the main experiments. The project will compare a fixed number of inference instances with automatic scaling under steady and bursty traffic. It will record request latency, throughput, errors, resource use, replica count, and scaling reaction time.

## Documentation

Start with [current status](md/STATUS.md) for progress, the [setup guide](md/GETTING_STARTED.md) for commands, or [Fontys documents](docs/README.md) for research, PDP, diagrams and saved feedback.

- [Roadmap](md/ROADMAP.md): milestones and completion criteria.
- [Status](md/STATUS.md): verified progress and remaining work.
- [Architecture](md/ARCHITECTURE.md): implemented components and runtime flow.
- [Decisions](md/DECISIONS.md): choices, alternatives and limitations; [detailed technology decisions in Notion](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a) explains Qwen, Ollama, CPU, k6 and planned HPA.
- [Getting started](md/GETTING_STARTED.md).
- [Task plans](md/plans/) and [teacher feedback](md/meeting/teacher-feedback.md).

## Project layout

- `docs/`: collected Fontys documents, PDF exports and course references; see its index for ownership.
- `md/`: technical context, concise decisions, meeting notes and task plans. Detailed technology research is maintained in Notion.
- `app/`: code for the representative inference workload.
- `deploy/`: reproducible local environment and deployment configuration.
- `bench/`: load generation, observation, and result analysis.
- `results/`: run settings, raw measurements, and generated figures.
- `report/`: conclusions, limitations, and technical advice.

## Planned workflow

Define one inference workload and two load profiles. Compare suitable orchestration platforms against the stated criteria and document the choice. Build the local environment, run a pilot, and lock the model, request format, resource limits, and latency target. Repeat the fixed-capacity and autoscaling scenarios with the same settings. Keep raw data and configuration for each run so the findings can be checked and reproduced.

## Current state

The implemented path uses Ollama for inference, k6 for load generation and `bench/observe.py` for cluster/resource observations. Pilot rate selection and pilot CSV/JSON summaries and plots are implemented; HPA, the three-replica comparison and main-series analysis remain unfinished. The Python server/load-generator starter files are not the active runtime. See [STATUS.md](md/STATUS.md) for verification dates, limitations and the active plan, and [ARCHITECTURE.md](md/ARCHITECTURE.md) for implementation details.

Saved checks are available for [deployment](results/smoke-2026-10-04/smoke.json), [load generation](results/k6-smoke-2026-10-04/README.md), [observation](results/observation-check-2026-10-16-verified/README.md) and [the completed pilot](results/pilot/discovery-2026-10-18-series1/README.md). They do not establish current cluster availability or maximum capacity. Use the [setup guide](md/GETTING_STARTED.md) for restart and run commands.

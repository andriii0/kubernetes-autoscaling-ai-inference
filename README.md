# AI Inference Autoscaling

This is an independent research project about scaling AI inference when request load changes. The work starts with a short comparison of container orchestration platforms, then uses one selected platform for a local prototype and repeatable measurements. It is separate from the SUE group infrastructure.

## Research question

How effectively can the selected container orchestration platform autoscale AI inference under changing load while keeping latency acceptable?

The acceptable p95 latency limit will be set after a small pilot run and before the main experiments. The project will compare a fixed number of inference instances with automatic scaling under steady and bursty traffic. It will record request latency, throughput, errors, resource use, replica count, and scaling reaction time.

## Documentation

- [Roadmap](md/ROADMAP.md): milestones and completion criteria.
- [Status](md/STATUS.md): verified progress and remaining work.
- [Architecture](md/ARCHITECTURE.md): implemented components and runtime flow.
- [Decisions](md/DECISIONS.md): choices, alternatives and limitations.
- [Setup guide in Russian](md/GETTING_STARTED_RU.md).
- [Task plans](md/plans/) and [teacher feedback](md/meeting/teacher-feedback.md).

## Project layout

- `md/`: project documentation, research, meeting notes and task plans.
- `app/`: code for the representative inference workload.
- `deploy/`: reproducible local environment and deployment configuration.
- `bench/`: load generation, observation, and result analysis.
- `results/`: run settings, raw measurements, and generated figures.
- `report/`: conclusions, limitations, and technical advice.

## Planned workflow

Define one inference workload and two load profiles. Compare suitable orchestration platforms against the stated criteria and document the choice. Build the local environment, run a pilot, and lock the model, request format, resource limits, and latency target. Repeat the fixed-capacity and autoscaling scenarios with the same settings. Keep raw data and configuration for each run so the findings can be checked and reproduced.

## Current state

Verified on 2026-10-04: the saved `ai-lab` Minikube cluster runs one Ollama replica in namespace `inference`, using the locally loaded `ai-inference:0.1` image. A request from Windows through the Kubernetes Service returned a completed response from `qwen2.5:0.5b`; the model runtime reports CPU execution.

Deployment: [deploy/ollama.yaml](deploy/ollama.yaml). Platform decision: [research/platform-choice.md](md/research/platform-choice.md). Verification data: [results/smoke-2026-10-04/smoke.json](results/smoke-2026-10-04/smoke.json) and the adjacent `cluster.json` snapshot. This is a deployment smoke test, not performance evidence.

To resume, start Docker Desktop, run `minikube start -p ai-lab`, and wait for `kubectl --context ai-lab -n inference rollout status deployment/ollama`. Open the Service tunnel with `minikube -p ai-lab service ollama -n inference --url` and keep that terminal open; its address can change.

Load generation is implemented in [bench/inference.js](bench/inference.js). A one-minute check at 2 requests per 10 seconds completed 13 requests with no inference errors or dropped iterations. Mean response latency was 1.043 s and p95 was 1.154 s. These are measurements of this small warm-model check, not a capacity estimate. See [the recorded run](results/k6-smoke-2026-10-04/README.md).

To repeat the short check from the project directory, set `BASE_URL` to the current Service tunnel address and run:

```powershell
k6 run --no-usage-report -e RATE=2 -e DURATION=1m .\bench\inference.js
```

Cluster and resource observation is implemented in [bench/observe.py](bench/observe.py). It saves Kubernetes state, scaling-signal observations, and direct kubelet CPU/memory measurements as timestamped JSONL. Run `python .\bench\observe.py .\results\my-run\cluster.jsonl --duration 150` with a new output path. See [the format and limitations](md/OBSERVATION.md) and [the live verification](results/observation-check-2026-10-16-verified/README.md).

Autoscaling, pilot rate selection and automated result analysis remain unfinished. `bench/analyze.py`, `bench/load_test.py` and `app/inference.py` are still starter functions. The active model server is Ollama; the active load generator is k6. Before the main comparison, finish the technology decision records and freeze the workload and acceptable latency target after the pilot.
# Platform choice for the local prototype

Date: 2026-10-04

Status: Kubernetes selected for one local CPU prototype. This decision is based on documented capabilities and the project requirements, not a measured performance ranking of platforms.

## Requirements

The prototype must run a small text-generation model locally, provide one address for its replicas, change the replica count under load, and expose enough state to measure the changes. The experiment compares fixed capacity with automatic scaling on one physical computer. A second complete platform implementation is outside the initial prototype scope.

## Alternatives

| Candidate | Relevant capability | Reason for the decision |
|---|---|---|
| Kubernetes | HPA changes application replica count using resource or additional metrics. | Selected: it directly supports the experiment and provides explicit resource limits, service routing and observable replica state. Learning and configuration effort are its main disadvantages. |
| Nomad with Nomad Autoscaler | Application scaling is supported through a separately configured Autoscaler agent. | Viable alternative. Its more compact core architecture does not remove the need to configure scaling and metrics. No performance disadvantage has been measured. |
| Docker Swarm | Services can be scaled to a desired replica count. | A metrics-based autoscaling controller would need to be selected and evaluated as an additional component. |
| Docker Compose | Supports a configured number of service replicas. | Useful for simple fixed-capacity deployment; it does not provide the intended metrics-based scaling policy through the scale command alone. |

Sources: [Kubernetes HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/), [Nomad Autoscaler](https://developer.hashicorp.com/nomad/tools/autoscaling), [Swarm service scaling](https://docs.docker.com/engine/swarm/swarm-tutorial/scale-service/), [Compose up](https://docs.docker.com/reference/cli/docker/compose/up/).

## Local Kubernetes environment

Minikube is selected because it supports the existing Windows and Docker Desktop setup, image loading, and an easy metrics-server addon. The cluster and addon have already run successfully in this setup. This confirms basic compatibility; it does not establish lower resource usage or faster inference than the alternatives.

kind is a viable option for reproducible clusters and automated checks. k3d is a viable option for running K3s in Docker. Neither requires a complete second application prototype to be considered in this decision. Switching remains possible if Minikube prevents a required measurement or repeatable deployment.

Sources: [Minikube](https://minikube.sigs.k8s.io/docs/), [kind](https://kind.sigs.k8s.io/), [k3d](https://k3d.io/stable/).

## Scope and validation

The first deployment uses one CPU replica of Ollama with qwen2.5:0.5b. Its initial resources and settings follow the [setup guide](../GETTING_STARTED_RU.md). They are pilot settings, not established optimum values. Acceptance requires a ready deployment and a completed model response through the Kubernetes Service from Windows.

Later experiments will compare fixed one replica, fixed three replicas and automatic scaling between one and three replicas, using the same model and load configuration. The acceptable latency and load rates must be fixed after the pilot. metrics-server provides the HPA input; it is not a source for precise resource accounting.

Revisit this decision if the local deployment cannot meet the experiment requirements, if the research question changes to a comparative platform benchmark, or if the workload moves to hardware or a hosting environment with different constraints.

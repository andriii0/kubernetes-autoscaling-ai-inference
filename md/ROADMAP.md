# Project Roadmap

Updated: 2026-10-16. Latest saved runtime checks: 2026-10-16.

## Goal and current position

Evaluate how automatic scaling of AI inference handles changing request load while keeping response time acceptable. Compare one fixed replica, three fixed replicas, and automatic scaling between one and three replicas. A replica is one running copy of the model server.

The local prototype, short load check, and continuous cluster/resource observer are complete. Direct kubelet resource measurements were verified with saved data on 2026-10-16. The next work is to finish the remaining decision records and request-level run records, then run a pilot to select the main experiment settings. Autoscaling is not implemented yet.

Completed steps refer to saved evidence, not a claim that the cluster is running today. All replicas use the CPU of one physical computer. Detailed commands are available in [GETTING_STARTED_RU.md](GETTING_STARTED_RU.md).

## All steps

`[x]` = completed with saved evidence. `[ ]` = not completed. Step numbers match the descriptions below; guide step numbers are different.

- [x] 01. Define the prototype scope and comparison requirements.
- [x] 02. Compare orchestration platforms and select one.
- [x] 03. Compare local Kubernetes tools and select one.
- [x] 04. Prepare Docker and the required command-line tools.
- [x] 05. Create the local cluster and project namespace.
- [x] 06. Enable resource metrics for Kubernetes.
- [x] 07. Download the model and obtain a first response.
- [x] 08. Package the model server and weights in a local image.
- [x] 09. Deploy one model replica in Kubernetes.
- [x] 10. Verify a response through the application Service.
- [x] 11. Implement the k6 load scenario.
- [x] 12. Run and save a short load check.
- [ ] 13. Complete the remaining technology decision records.
- [x] 14. Implement continuous cluster observation.
- [x] 15. Select and verify resource measurements for the final report.
- [ ] 16. Run a pilot with increasing load on one replica.
- [ ] 17. Record and freeze the experiment settings.
- [ ] 18. Test three manually configured replicas.
- [ ] 19. Configure and verify automatic scaling from one to three replicas.
- [ ] 20. Prepare the main experiment matrix and run procedure.
- [ ] 21. Execute and save the main experiment series.
- [ ] 22. Process the measurements and build tables and charts.
- [ ] 23. Write the findings, limitations, and recommendations.
- [ ] 24. Check that another person can repeat the experiment.

## Step descriptions

### 01. Define the prototype scope and comparison requirements

**Purpose:** decide what the project will measure before expanding the implementation.

Use a small local text-generation workload. Require an application address, configurable replica count, automatic scaling, and observable state. Plan to compare fixed capacity with automatic scaling under steady and burst traffic.

**Completion evidence:** the requirements and scope in [research/platform-choice.md](research/platform-choice.md) and the research question in [README.md](../README.md). The acceptable response-time target still needs pilot results in step 17.

### 02. Compare orchestration platforms and select one

**Purpose:** choose a platform based on the project requirements and explain the alternatives.

Compare Kubernetes, Nomad with Nomad Autoscaler, Docker Swarm, and Docker Compose. Select Kubernetes for the first prototype and document its tradeoffs. A second full platform implementation is outside the initial scope.

**Completion evidence:** [research/platform-choice.md](research/platform-choice.md). This is a documented capability-based choice, not a measured performance ranking.

### 03. Compare local Kubernetes tools and select one

**Purpose:** select a practical way to run Kubernetes on the existing Windows computer.

Consider Minikube, kind, and k3d. Use Minikube for the prototype because it supports the existing Docker setup and required workflow.

**Completion evidence:** the local environment decision in [research/platform-choice.md](research/platform-choice.md) and the saved cluster checks. No comparative speed or memory advantage has been measured.

### 04. Prepare Docker and the required command-line tools

**Purpose:** provide the tools needed to run containers, manage Kubernetes, and generate requests.

Prepare Docker Desktop with Linux containers, Minikube, kubectl for Kubernetes commands, and k6 for load generation. Record versions with experiment results.

**Completion evidence:** the deployment and load-check records under `results/smoke-2026-10-04/` and `results/k6-smoke-2026-10-04/`. Setup and restart commands are in guide steps 1–2.

### 05. Create the local cluster and project namespace

**Purpose:** create the environment where the model replicas will run.

Create the Minikube cluster `ai-lab` and namespace `inference`. A namespace groups the Kubernetes resources belonging to the project. Wait for the cluster node to become ready.

**Completion evidence:** [results/smoke-2026-10-04/cluster.json](../results/smoke-2026-10-04/cluster.json). See guide step 2 for the commands.

### 06. Enable resource metrics for Kubernetes

**Purpose:** allow Kubernetes to receive CPU and memory observations needed for the planned scaling policy.

Enable metrics-server and verify that resource readings become available. Treat these readings as an operational scaling signal; choose the source for final resource-consumption claims separately in step 15.

**Completion evidence:** the metrics-server setup recorded in [GETTING_STARTED_RU.md](GETTING_STARTED_RU.md) and the saved cluster checks from 2026-10-04.

### 07. Download the model and obtain a first response

**Purpose:** verify that the selected model can run locally before adding Kubernetes deployment details.

Run Ollama, download `qwen2.5:0.5b`, and send a short prompt. Use CPU execution for the initial experiment.

**Completion evidence:** the model and completed response recorded in [results/smoke-2026-10-04/smoke.json](../results/smoke-2026-10-04/smoke.json). The standalone setup procedure is in guide step 3.

### 08. Package the model server and weights in a local image

**Purpose:** let replicas use an already downloaded model without downloading its weights from the internet on every start.

Prepare the `ai-inference:0.1` container image with Ollama and model weights, and make it available inside Minikube. The weights are the files containing the model's learned parameters.

**Completion evidence:** the image recorded in the saved deployment checks and referenced by [deploy/ollama.yaml](../deploy/ollama.yaml). See guide step 4 for the preparation procedure.

### 09. Deploy one model replica in Kubernetes

**Purpose:** establish the fixed-one-replica baseline.

Deploy Ollama in `inference` with one replica, explicit CPU and memory settings, and a readiness check. A readiness check tells Kubernetes whether the server is ready to receive traffic.

**Completion evidence:** [deploy/ollama.yaml](../deploy/ollama.yaml) and the saved cluster snapshots. One ready replica with no restarts was observed during the short check. See guide step 5.

### 10. Verify a response through the application Service

**Purpose:** confirm that requests reach the model through the address used by the load generator.

Use the Ollama Service, which provides an application address independent of an individual replica. Open the local access tunnel and send a request from Windows. The tunnel address may change when restarted.

**Completion evidence:** [results/smoke-2026-10-04/smoke.json](../results/smoke-2026-10-04/smoke.json). See guide step 6.

### 11. Implement the k6 load scenario

**Purpose:** generate a controlled request rate and collect response measurements.

Implement steady and burst scenarios using the selected prompt and model settings. Record successful-response latency, inference errors, and dropped iterations separately. A dropped iteration is a scheduled request that the load generator could not start.

**Completion evidence:** [bench/inference.js](../bench/inference.js). The short steady scenario was executed in step 12; the full burst scenario has not yet been validated in the main experiment. See guide step 7.

### 12. Run and save a short load check

**Purpose:** verify the request generator and saved results before increasing load.

Run one minute at two requests per ten seconds against one warm replica. Exclude the separate warmup request from the measurements.

**Completion evidence:** [results/k6-smoke-2026-10-04/README.md](../results/k6-smoke-2026-10-04/README.md): 13 completed responses, no inference errors or dropped iterations, mean response time 1.043 seconds, and p95 1.154 seconds. p95 is the response-time value within which 95% of measured successful responses fall. This small check does not establish maximum capacity.

### 13. Complete the remaining technology decision records

**Purpose:** make the remaining choices explicit before the main experiment.

Use guide section 14 to compare alternatives for the model, model server, CPU versus GPU execution, load generator, resource measurements, and scaling policy. Record selected options and reasons in `md/DECISIONS.md`; finalize numerical settings in `md/plans/experiment-protocol.md` after the pilot in step 17.

**Done when:** the remaining decisions have requirements, considered alternatives, a selected option, and an explanation. Missing comparative measurements must remain labelled as missing.

### 14. Implement continuous cluster observation

**Purpose:** preserve what happened during each run instead of relying on terminal screenshots.

Implement `bench/observe.py` using guide step 11. Save timestamped replica state, scaling state, and resource observations throughout a run. Use UTC timestamps so request and cluster records can be aligned.

**Completion evidence:** `bench/observe.py`, `bench/test_observe.py`, and [the live check](../results/observation-check-2026-10-16-verified/README.md). The check saved 30 observations across a 150-second session with no collection errors. Error handling and output protection were also verified. JSONL records retain raw state, source timestamps, gaps and errors.

### 15. Select and verify resource measurements for the final report

**Purpose:** support resource-consumption conclusions with an appropriate measurement source.

Compare the options in guide section 14.13. Select the source, document its units and sampling interval, and verify that it measures the intended containers or processes. Keep metrics-server observations for interpreting the scaling signal, but do not use them as precise resource accounting.

**Completion evidence:** direct kubelet `/metrics/resource` collection, described in [bench/OBSERVATION.md](OBSERVATION.md), and [saved verification](../results/observation-check-2026-10-16-verified/README.md). Raw CPU core-seconds, memory working set in bytes, container identity and source timestamps were checked independently. metrics-server remains a separate scaling signal. These sources do not measure Windows-wide power or monetary savings; cadence and observer overhead still limit the experiment.

### 16. Run a pilot with increasing load on one replica

**Purpose:** find useful low and peak request rates for this computer.

First verify Docker, the cluster, the application address, exactly one ready replica, and no active autoscaler. Run short probes one at a time, following guide step 8. Wait for outstanding requests to finish and CPU usage to fall between probes. Stop increasing the rate when substantial delays or errors appear and inspect the result.

**Done when:** saved probes identify a low rate handled comfortably by one replica and a peak rate that makes its response times noticeably worse. Save the actual rate, duration, request settings, and raw data for every probe.

### 17. Record and freeze the experiment settings

**Purpose:** keep the main comparison consistent across modes.

Complete `md/plans/experiment-protocol.md` with the model, prompt, generation settings, resource limits, low and peak rates, scenario durations, warmup procedure, acceptable error rate, and p95 response-time target. Explain why the target is appropriate for the task.

**Done when:** settings are documented before the main series. Do not silently change them between modes or after seeing an inconvenient result; document any revised protocol and the affected runs.

### 18. Test three manually configured replicas

**Purpose:** check whether additional replicas help at the chosen peak rate before introducing automatic scaling.

Follow guide step 9 to start three replicas, warm each model, verify traffic reaches all three, and repeat the peak probe. If performance does not improve, inspect traffic distribution and available resources.

**Done when:** all replicas are verified and both the one-replica and three-replica probe results are saved. A performance improvement is an outcome to measure, not a completion requirement.

### 19. Configure and verify automatic scaling from one to three replicas

**Purpose:** let Kubernetes change replica count in response to observed CPU load.

Create `deploy/hpa.yaml` following guide step 10. HPA, the Horizontal Pod Autoscaler, changes application replica count using observed metrics. Verify that it receives CPU readings, then run a burst probe and record replica changes and response times during load growth and decline. Account for the configured wait before scaling down.

**Done when:** the scaling reaction is recorded and explained, including any failure to add or remove replicas. Missing input metrics must be fixed before treating a run as autoscaling evidence.

### 20. Prepare the main experiment matrix and run procedure

**Purpose:** define a repeatable comparison before collecting the main results.

Use three modes: fixed one replica, fixed three replicas, and automatic scaling from one to three. Test steady and burst traffic with at least three repetitions of each combination: an initial plan of 18 runs. Follow guide step 12 for clean starts, warmup, and switching modes between runs.

Exclude initial warmup from measurements. In automatic mode, loading models in newly created replicas during a run is part of the measured scaling reaction.

**Done when:** the matrix, preparation procedure, saved metadata, and handling of invalid runs are recorded in `md/plans/experiment-protocol.md`.

### 21. Execute and save the main experiment series

**Purpose:** collect comparable evidence for all planned combinations.

Execute the matrix using the frozen settings. Save each run in its own folder with raw k6 data, cluster observations, resource measurements, console output, configuration, versions, UTC times, and exit codes. Count response errors separately from requests the generator could not start.

**Done when:** the planned series has complete evidence. Mark and explain invalid or repeated runs. If variation prevents a reliable conclusion, add justified repetitions or report insufficient evidence.

### 22. Process the measurements and build tables and charts

**Purpose:** connect request behaviour, scaling changes, and resource use over time.

Implement `bench/analyze.py` following guide step 13. Produce summaries and aligned time-series charts for response latency, errors, completed and dropped requests, ready replica count, and resources. Keep missing values as gaps.

**Done when:** saved tables and charts can be regenerated from raw files, and their units, time windows, and data sources are documented.

### 23. Write the findings, limitations, and recommendations

**Purpose:** answer the research question using measured results.

Write `report/results.md`. Compare response times, errors, scaling reaction, resource use, and variation between repetitions. Explain the limits of one physical computer, the small model, the repeated short prompt, possible caching, and measurement sources.

**Done when:** conclusions link to the supporting runs and state when autoscaling helps, does not help, or cannot be judged from the evidence. The project does not require a positive result for autoscaling.

### 24. Check that another person can repeat the experiment

**Purpose:** make the final project usable for review and reproduction.

Check the documented setup, image preparation, configuration, scenario commands, result locations, and analysis commands. Include required versions and explain which values are machine-specific. Resolve missing steps and broken evidence links.

**Done when:** the instructions provide a complete path from prerequisites to regenerated results, and the report clearly distinguishes saved evidence from unverified runtime state.

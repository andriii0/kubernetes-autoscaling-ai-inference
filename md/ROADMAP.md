# Project Roadmap

Updated: 2026-10-28. Latest saved preliminary HPA check: 2026-10-28 UTC, at the separately authorized peak rate 12; main protocol v1.1 remains unchanged.

## Goal and current position

Evaluate how automatic scaling of AI inference handles changing request load while keeping response time acceptable. Compare one fixed replica, three fixed replicas, and automatic scaling between one and three replicas. A replica is one running copy of the model server.

The local prototype, short load check, and continuous cluster/resource observer are complete. Direct kubelet resource measurements were verified with saved data on 2026-10-16. Technology decisions are documented. Request-level records and integrated collection now have offline tests and a saved live low-load check on 2026-10-18. Minimal pilot analysis and the increasing-load pilot are complete, including two five-minute repetitions per selected rate. I agreed [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) on 2026-10-21. Step-20 code and run instructions have local verification. The 18-run main matrix and reproducible comparative tables/plots are complete; [STATUS.md](STATUS.md) records verification and limits. A [preliminary HPA check](../results/autoscaling/check-2026-10-20-series1/README.md) now verifies growth and reduction. The main findings document and final reproduction review remain unfinished.

Completed steps refer to saved evidence, not a claim that the cluster is running today. All replicas use the CPU of one physical computer. Setup commands are in [GETTING_STARTED.md](GETTING_STARTED.md). Detailed pilot and scaling procedures live in the linked task plans; guide section numbers are topic references, not the order of project work.

The [new preliminary HPA burst](../results/autoscaling/check-20261028-181713-peak12/README.md) shows 1 -> 2 -> 3 -> 1 scaling at 2 -> 12 -> 2 requests/10 s, with valid collection but a latency target miss. It is separate from the completed main matrix and does not close the open findings or reproduction steps.

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
- [x] 13. Complete the remaining technology decision records.
- [x] 14. Implement continuous cluster observation.
- [x] 15. Select and verify resource measurements for the final report.
- [x] 16. Run a pilot with increasing load on one replica.
- [x] 17. Record and freeze the experiment settings.
- [x] 18. Test three manually configured replicas.
- [x] 19. Configure and verify automatic scaling from one to three replicas.
- [x] 20. Prepare the main experiment matrix and run procedure.
- [x] 21. Execute and save the main experiment series.
- [x] 22. Process the measurements and build tables and charts.
- [ ] 23. Write the findings, limitations, and recommendations.
- [ ] 24. Check that another person can repeat the experiment.

## Step descriptions

### 01. Define the prototype scope and comparison requirements

**Purpose:** decide what the project will measure before expanding the implementation.

Use a small local text-generation workload. Require an application address, configurable replica count, automatic scaling, and observable state. Plan to compare fixed capacity with automatic scaling under steady and burst traffic.

**Completion evidence:** the scope and research question in [README.md](../README.md) and the [platform decision](DECISIONS.md#1-use-one-kubernetes-prototype-after-comparing-alternatives). The response-time target and its study-assumption rationale are recorded in the agreed step-17 protocol.

### 02. Compare orchestration platforms and select one

**Purpose:** choose a platform based on the project requirements and explain the alternatives.

Compare Kubernetes, Nomad with Nomad Autoscaler, Docker Swarm, and Docker Compose. Select Kubernetes for the first prototype and document its tradeoffs. A second full platform implementation is outside the initial scope.

**Completion evidence:** section 6 (SQ3), pages 6-8 of the [research document](<../docs/PDP Research document.pdf>) and the [short decision record](DECISIONS.md#1-use-one-kubernetes-prototype-after-comparing-alternatives). This is a documented capability-based choice, not a measured performance ranking.

### 03. Compare local Kubernetes tools and select one

**Purpose:** select a practical way to run Kubernetes on the existing Windows computer.

Consider Minikube, kind, and k3d. Use Minikube for the prototype because it supports the existing Docker setup and required workflow.

**Completion evidence:** [Technology Decisions in Notion, section 6](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a), the [local summary](DECISIONS.md#2-use-minikube-with-docker-on-the-existing-windows-computer) and the saved cluster checks. No comparative speed or memory advantage has been measured.

### 04. Prepare Docker and the required command-line tools

**Purpose:** provide the tools needed to run containers, manage Kubernetes, and generate requests.

Prepare Docker Desktop with Linux containers, Minikube, kubectl for Kubernetes commands, and k6 for load generation. Record versions with experiment results.

**Completion evidence:** the deployment and load-check records under `results/smoke-2026-10-04/` and `results/k6-smoke-2026-10-04/`. Setup and restart commands are in guide steps 1-2.

### 05. Create the local cluster and project namespace

**Purpose:** create the environment where the model replicas will run.

Create the Minikube cluster `ai-lab` and namespace `inference`. A namespace groups the Kubernetes resources belonging to the project. Wait for the cluster node to become ready.

**Completion evidence:** [results/smoke-2026-10-04/cluster.json](../results/smoke-2026-10-04/cluster.json). See guide step 2 for the commands.

### 06. Enable resource metrics for Kubernetes

**Purpose:** allow Kubernetes to receive CPU and memory observations needed for the planned scaling policy.

Enable metrics-server and verify that resource readings become available. Treat these readings as an operational scaling signal; choose the source for final resource-consumption claims separately in step 15.

**Completion evidence:** the metrics-server setup recorded in [GETTING_STARTED.md](GETTING_STARTED.md) and the saved cluster checks from 2026-10-04.

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

**Completion evidence:** [bench/inference.js](../bench/inference.js). The short steady scenario was executed in step 12; all six mode/profile combinations, including the full burst, have saved main-series evidence in steps 21 and 22. See guide step 7.

### 12. Run and save a short load check

**Purpose:** verify the request generator and saved results before increasing load.

Run one minute at two requests per ten seconds against one warm replica. Exclude the separate warmup request from the measurements.

**Completion evidence:** [results/k6-smoke-2026-10-04/README.md](../results/k6-smoke-2026-10-04/README.md): 13 completed responses, no inference errors or dropped iterations, mean response time 1.043 seconds, and p95 1.154 seconds. p95 is the response-time value within which 95% of measured successful responses fall. This small check does not establish maximum capacity.

### 13. Complete the remaining technology decision records

**Purpose:** make the remaining choices explicit before the main experiment.

Compare alternatives for the model, model server, CPU versus GPU execution, load generator, resource measurements, and scaling policy. Keep concise accepted decisions in `md/DECISIONS.md` and detailed technology research in Notion; use the numerical agreement recorded in the separate Notion experiment protocol in step 17.

**Completion evidence:** [Technology Decisions in Notion](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a), completed on 2026-10-18, explains Qwen, Ollama, CPU, k6 and planned CPU-based HPA with requirements, alternatives, reasons, official sources and reconsideration criteria. The measurement decision and its verification remain in [DECISIONS.md](DECISIONS.md#6-separate-the-scaling-signal-from-resource-measurements). The pilot rates are now measured in step 16; the preliminary HPA check now records growth and reduction; the repeated comparison is now saved in steps 21 and 22, without an established HPA advantage.

### 14. Implement continuous cluster observation

**Purpose:** preserve what happened during each run instead of relying on terminal screenshots.

Maintain `bench/observe.py` using the schema and collection rules in [OBSERVATION.md](OBSERVATION.md). Save timestamped replica state, scaling state, and resource observations throughout a run. Use UTC timestamps so request and cluster records can be aligned.

**Completion evidence:** `bench/observe.py`, `tests/bench/test_observe.py`, and [the live check](../results/observation-check-2026-10-16-verified/README.md). The check saved 30 observations across a 150-second session with no collection errors. Error handling and output protection were also verified. JSONL records retain raw state, source timestamps, gaps and errors.

### 15. Select and verify resource measurements for the final report

**Purpose:** support resource-consumption conclusions with an appropriate measurement source.

Compare resource-measurement options, then document the selected source, units, sampling interval and intended containers or processes in `md/OBSERVATION.md`; use [DECISIONS.md](DECISIONS.md) for accepted operating choices and constraints. Keep metrics-server observations for interpreting the scaling signal, but do not use them as precise resource accounting.

**Completion evidence:** direct kubelet `/metrics/resource` collection, described in [OBSERVATION.md](OBSERVATION.md), and [saved verification](../results/observation-check-2026-10-16-verified/README.md). Raw CPU core-seconds, memory working set in bytes, container identity and source timestamps were checked independently. metrics-server remains a separate scaling signal. These sources do not measure Windows-wide power or monetary savings; cadence and observer overhead still limit the experiment.

### 16. Run a pilot with increasing load on one replica

**Purpose:** find useful low and peak request rates for this computer.

First verify Docker, the cluster, the application address, exactly one ready replica, and no active autoscaler. Run short probes one at a time, following the [pilot plan](plans/measurements-and-pilot.md#4-pilot-sequence). Wait for outstanding requests to finish and CPU usage to fall between probes. Stop increasing the rate when substantial delays or errors appear and inspect the result.

**Done when:** saved probes identify a low rate handled comfortably by one replica and a peak rate that makes its response times noticeably worse. Save the actual rate, duration, request settings, and raw data for every probe.

**Completion evidence:** [the saved pilot series](../results/pilot/discovery-2026-10-18-series1/README.md), with eight valid discovery/confirmation runs and an excluded pre-fix diagnostic. Low=2 and peak=8 requests/10 s each have two five-minute repetitions. Response degradation repeats at the peak; timeout counts vary. Step 17 is complete, step-20 preparation has local verification, and the main matrix and comparative analysis are complete in steps 21 and 22. The older pilot slowdown did not recur; see [the open discrepancy](PILOT_MAIN_DISCREPANCY.md).

### 17. Record and freeze the experiment settings

**Purpose:** keep the main comparison consistent across modes.

Write a separate experiment protocol in Notion with the model, prompt, generation settings, resource limits, low and peak rates, scenario durations, warmup procedure, acceptable error rate, and p95 response-time target. Explain why the target is appropriate for the task.

**Done when:** settings are documented before the main series. Do not silently change them between modes or after seeing an inconvenient result; document any revised protocol and the affected runs.

**Completion evidence:** I approved [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) on 2026-10-21. It records the settings, acceptance windows, 18-run order, preparation, selected resource quantities and outcome/data rules. Version 1.1 clarifies the original 1.0 agreement before any main run; step 17 remains complete. Executable alignment now has step-20 local verification; this agreement does not authorize or complete the main series.

### 18. Test three manually configured replicas

**Purpose:** check three manually configured copies at the pilot peak rate before the main experiment.

Follow the [manual replica comparison procedure](plans/scaling-experiment.md#1-manual-replica-comparison) to start three replicas, warm each model, verify traffic reaches all three, and repeat the peak probe. Inspect traffic distribution and resources if the result is unexpected.

**Done when:** all three replicas and their warmups/Service traffic are verified, and both one-copy and three-copy peak probe results are saved. A performance improvement is an outcome to measure, not a completion requirement. This preliminary check does not require the repeated main series.

**Completion evidence:** the [one-copy pilot](../results/pilot/discovery-2026-10-18-series1/README.md) and [three-copy check saved on 2026-10-20](../results/fixed-replicas/check-2026-10-20-series1/README.md). The three-copy records verify individual warmup, selected Service endpoints and traffic on every copy. The saved probes were reconciled again on 2026-10-21. Their different dates and repetition counts do not establish a controlled repeated comparison or an HPA advantage.

**Scope correction (2026-10-21):** restore the original preliminary-check criterion. Repetitions under frozen main conditions belong to step 21, using the matrix prepared in step 20. Do not run another series to close step 18; the existing evidence completes it. Historical result reports retain their original milestone wording and verdicts.

### 19. Configure and verify automatic scaling from one to three replicas

**Purpose:** let Kubernetes change replica count in response to observed CPU load.

Use `deploy/hpa.yaml` and the [HPA configuration and verification procedure](plans/scaling-experiment.md#2-hpa-setup-and-checks). HPA, the Horizontal Pod Autoscaler, changes application replica count using observed metrics. Verify that it receives CPU readings, then run a burst probe and record replica changes and response times during load growth and decline. Account for the configured wait before scaling down.

**Done when:** the scaling reaction is recorded and explained, including any failure to add or remove replicas. Missing input metrics must be fixed before treating a run as autoscaling evidence.

**Completion evidence:** the [preliminary HPA check](../results/autoscaling/check-2026-10-20-series1/README.md) saves the CPU input, 1 -> 2 -> 3 -> 1 transitions, per-pod activity and complete request reconciliation. This completes the mechanism check, not the repeated main experiment.

### 20. Prepare the main experiment matrix and run procedure

**Purpose:** define a repeatable comparison before collecting the main results.

Use three modes: fixed one replica, fixed three replicas, and automatic scaling from one to three. Test steady and burst traffic with at least three repetitions of each combination: an initial plan of 18 runs. Follow the [main run procedure](plans/scaling-experiment.md#3-main-run-procedure) for clean starts, warmup, and switching modes between runs.

Exclude initial warmup from measurements. In automatic mode, loading models in newly created replicas during a run is part of the measured scaling reaction.

**Done when:** the existing scripts and linked execution instructions support the matrix, preparation, metadata and outcome/data rules recorded in Notion protocol v1.1. Verify every mode/profile, initial/post-warmup gate, primary phase/window, resource quantity/coverage and run-assessment requirement before main load. Protocol v1.1 supplies the agreement; current runtime readiness remains a separate check before approved load. A manual checklist is sufficient; a separate matrix orchestrator is not required.

**Completion evidence:** the [main procedure and checklist](plans/scaling-experiment.md#3-main-run-procedure), shared configuration and existing launcher/analyzer support the agreed rules. All 122 bench tests passed, including all six mode/profile paths with local HTTP fixtures, explicit preparation gates and calculation checks. Historical hashes and saved summaries match. This is code/procedure verification, not a live main experiment.

### 21. Execute and save the main experiment series

**Purpose:** collect comparable evidence for all planned combinations.

Execute the matrix using the frozen settings. Save each run in its own folder with raw k6 data, cluster observations, resource measurements, console output, configuration, versions, UTC times, and exit codes. Count response errors separately from requests the generator could not start.

**Done when:** the planned series has complete evidence. Mark and explain invalid or repeated runs. If variation prevents a reliable conclusion, add justified repetitions or report insufficient evidence.

**Completion evidence (2026-10-26):** [18 reviewed main attempts and combined validation](../results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/validation.json). All 5,189 requests reconcile, all planned mode/profile/repetition cells are present, inputs match, and resource gaps remain explicit. The preserved pause/recovery records explain interruptions and pre-run restart context.

### 22. Process the measurements and build tables and charts

**Purpose:** connect request behaviour, scaling changes, and resource use over time.

Extend the implemented [pilot analysis](plans/measurements-and-pilot.md#5-pilot-output-and-decisions) in `bench/analyze.py` using the [main result analysis plan](plans/scaling-experiment.md#4-main-result-analysis). Produce summaries and aligned time-series charts for response latency, errors, completed and dropped requests, ready replica count, and resources. Keep missing values as gaps.

**Done when:** saved tables and charts can be regenerated from raw files, and their units, time windows, and data sources are documented.

**Completion evidence (2026-10-26):** [reproducible combined analysis](../results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/README.md), produced by bench/summarize_main.py using the existing analyzer. It includes per-run/group/phase/scaling/resource CSVs, validation JSON, 18 aligned plot pairs and an all-repetition primary-p95 plot. Exact model-ready/server-drain times and complete HPA application CPU totals remain unavailable; these are stated limits, not zero values.

### 23. Write the findings, limitations, and recommendations

**Purpose:** answer the research question using measured results.

Write a separate findings document in Notion and link to the supporting runs. Compare response times, errors, scaling reaction, resource use, and variation between repetitions. Explain the limits of one physical computer, the small model, the repeated short prompt, possible caching, and measurement sources.

**Done when:** conclusions link to the supporting runs and state when autoscaling helps, does not help, or cannot be judged from the evidence. The project does not require a positive result for autoscaling.

### 24. Check that another person can repeat the experiment

**Purpose:** make the final project usable for review and reproduction.

Check the documented setup, image preparation, configuration, scenario commands, result locations, and analysis commands. Include required versions and explain which values are machine-specific. Resolve missing steps and broken evidence links.

**Done when:** the instructions provide a complete path from prerequisites to regenerated results, and the report clearly distinguishes saved evidence from unverified runtime state.

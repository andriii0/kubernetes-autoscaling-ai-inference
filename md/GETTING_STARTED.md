# Getting started

This guide explains how to prepare and use the local CPU prototype on Windows. Run commands in PowerShell from `C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference`. Code and configuration files already exist in this project; open them through the links below.

The section numbers group topics. They are not the project schedule. Check [STATUS.md](STATUS.md) for the current state and active plan, and [ROADMAP.md](ROADMAP.md) for the order of work. Set up observation before collecting pilot results, even though its reference section appears later in this guide.

Saved checks do not prove that Docker or the cluster is running today. The preliminary HPA check is implemented; the repeated main comparison remains planned. Pilot analysis is implemented; current completion evidence is in STATUS.md.

## What the project will do

The experiment will compare fixed capacity with automatic scaling for a small text-generation service. Docker Desktop runs containers, Minikube runs the local Kubernetes cluster, Ollama runs the model, and k6 sends test requests. The first experiment uses CPU execution.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the system flow and [DECISIONS.md](DECISIONS.md) for accepted choices. Detailed technology research is maintained in [Notion](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a).

## 0. Basic terms

| Term | Meaning here |
|---|---|
| Image | A package containing a program and the files needed to run it. |
| Container | A running instance of an image. |
| Kubernetes | The system that starts containers and manages their copies. |
| Cluster | The Kubernetes environment. |
| Node | A machine in the cluster; here it runs inside Docker on the same computer. |
| Pod | The Kubernetes unit that contains the Ollama container. |
| Replica | Another copy of that pod. |
| Deployment | The application configuration and desired replica count. |
| Service | An application address that routes connections to its pods. |
| HPA | Horizontal Pod Autoscaler: a controller that changes the replica count using observed load. |
| Inference | Using an existing model to generate an answer; no model training is needed. |

Adding replicas on this node does not add physical CPU or memory to the computer.

## 1. Prepare Docker and PowerShell

Open Docker Desktop and wait for its engine to start. Use Linux containers with the WSL 2 backend. WSL 2 lets Linux run inside Windows. Minikube creates this project's cluster; Docker Desktop's built-in Kubernetes cluster is not needed.

```powershell
Set-Location 'C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference'
docker info --format '{{.OSType}}'
docker info --format 'CPUs={{.NCPU}} RAM_BYTES={{.MemTotal}}'
```

The first check must print `linux`. The second shows the resources available to Docker. The cluster command in section 2 needs at least 8 available CPU units and more than 12 GiB of memory.

If Docker reports that WSL is missing, run the following command in an administrator PowerShell window, then restart Windows if requested:

```powershell
wsl --install
```

Skip this installation if Docker already works. If resources are too limited, inspect the Docker and WSL settings. Preserve any existing settings in `.wslconfig`.

**Check:** `docker info` succeeds before continuing.

Source: [Docker Desktop with WSL 2](https://docs.docker.com/desktop/features/wsl/).

## 2. Prepare the tools and cluster

Check the installed tools first:

```powershell
minikube version
k6 version
kubectl version --client
python --version
```

`kubectl` sends commands to Kubernetes. Python runs the existing observer and pilot launcher. Install only missing tools; the following commands cover Minikube, k6 and kubectl:

```powershell
winget install --id Kubernetes.minikube --exact --source winget
winget install --id GrafanaLabs.k6 --exact --source winget
winget install --id Kubernetes.kubectl --exact --source winget
```

After installation, open a new PowerShell window, return to the project directory and check the versions again. Use the project's Python interpreter if `python` is not available on PATH.

For the first cluster setup:

```powershell
minikube start -p ai-lab --driver=docker --cpus=8 --memory=12288
kubectl --context ai-lab wait --for=condition=Ready node --all --timeout=180s
kubectl --context ai-lab get nodes
```

The first start downloads images. The CPU value is a computing budget, not the number of physical cores in the computer. The current resource choices are explained in [ARCHITECTURE.md](ARCHITECTURE.md#runtime-flow). To resume an existing setup, use [Stop and resume](#stop-and-resume).

Check whether the namespace already exists:

```powershell
kubectl --context ai-lab get namespace inference
```

Only if that command reports `NotFound`, create it:

```powershell
kubectl --context ai-lab create namespace inference
```

Enable the scaling metrics and check them:

```powershell
minikube -p ai-lab addons enable metrics-server
kubectl --context ai-lab top nodes
```

metrics-server supplies Kubernetes with resource readings. The Metrics API may need a minute to become available; retry `top nodes` if needed. Every `--context ai-lab` option explicitly selects this cluster.

**Check:** the node is `Ready` and `top nodes` returns readings.

Sources: [Minikube setup](https://minikube.sigs.k8s.io/docs/start/), [Docker driver](https://minikube.sigs.k8s.io/docs/drivers/docker/), [k6 installation](https://grafana.com/docs/k6/latest/set-up/install-k6/).

## 3. Download the model and get a first answer

The selected model is `qwen2.5:0.5b`. Its weights are the files that hold its learned parameters. Keep them out of Git. The model choice is recorded in [DECISIONS.md](DECISIONS.md#3-use-the-verified-ollamaqwen-cpu-baseline-for-the-first-experiment).

Use the Ollama version pinned in the existing [Dockerfile](../app/Dockerfile). Keep these commands in the same PowerShell window:

```powershell
$ollamaBaseImage = ((Get-Content .\app\Dockerfile | Where-Object { $_ -match '^FROM\s+' }) -replace '^FROM\s+', '').Trim()
docker ps -a --filter 'name=^/ai-lab-model$'
```

If `ai-lab-model` already exists, start it:

```powershell
docker start ai-lab-model
```

If it does not exist, create a temporary CPU-only helper container:

```powershell
docker pull $ollamaBaseImage
docker run -d --name ai-lab-model --cpus=2 --memory=2g $ollamaBaseImage
```

Check Ollama, download the model if needed, and ask for an answer:

```powershell
docker exec ai-lab-model ollama list
docker exec ai-lab-model ollama pull qwen2.5:0.5b
docker exec ai-lab-model ollama run qwen2.5:0.5b 'Explain what a container is in three short sentences.'
```

If Ollama is not ready immediately after startup, wait a few seconds and repeat the check. These commands do not pass a GPU to the container. An existing local model can be reused; preserve its identity throughout a measured series.

**Check:** the model returns text before moving to Kubernetes deployment.

Sources: [Ollama in Docker](https://docs.ollama.com/docker), [model entry](https://ollama.com/library/qwen2.5:0.5b).

## 4. Build the image with model files

The existing [Dockerfile](../app/Dockerfile) includes the model files in the image. New replicas can use these files without downloading the weights from the internet. Each replica still loads the model into its own memory.

```powershell
New-Item -ItemType Directory -Force .\app\models | Out-Null
docker cp ai-lab-model:/root/.ollama/models/. .\app\models
docker build -t ai-inference:0.1 .\app
minikube -p ai-lab image load ai-inference:0.1
```

The last command makes the image available inside Minikube. An image in Docker Desktop is not automatically present in the cluster's image store. Keep the pinned Dockerfile; do not replace its base image with `latest` during a series.

After a successful build and image load, the helper can be stopped:

```powershell
docker stop ai-lab-model
```

Optional cleanup: `docker rm ai-lab-model` removes only that helper container. First confirm that the files were copied and the image was built. Keep `/app/models/` excluded by the project's [.gitignore](../.gitignore). Do not rebuild a measured image under the same tag during a series.

**Check:** the image build and Minikube image load succeed.

## 5. Deploy one model replica

Use the existing [deploy/ollama.yaml](../deploy/ollama.yaml). It owns the Deployment, resource settings, readiness probe and Service configuration; do not create a second copy from this guide.

```powershell
kubectl --context ai-lab apply -f .\deploy\ollama.yaml
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
kubectl --context ai-lab -n inference get pods
```

`requests` tells Kubernetes how much capacity to account for when placing a pod. `limits` restricts use. CPU units are a time budget; they do not pin the pod to particular physical cores.

The `/api/tags` readiness probe checks the Ollama API. It does not prove that the model is warm. Initial warmup and the loading delay of new replicas follow [the accepted readiness decision](DECISIONS.md#10-distinguish-server-readiness-from-a-warm-model).

**Check:** one pod is `Running` with `READY 1/1`. Test an individual request before generating load.

## 6. Send a request through the Service

Open a second PowerShell window:

```powershell
minikube -p ai-lab service ollama -n inference --url
```

This opens a tunnel to the Service and prints an address such as `http://127.0.0.1:54321`. Keep that window open. The port can change after a restart.

In the first window, paste that address when asked:

```powershell
$env:BASE_URL = (Read-Host 'Service URL from the Minikube window').Trim().TrimEnd('/')
$body = @{
    model = 'qwen2.5:0.5b'
    prompt = 'Explain what a container is in three short sentences.'
    stream = $false
    options = @{ num_predict = 64 }
} | ConvertTo-Json -Depth 3
Invoke-RestMethod -Uri "$env:BASE_URL/api/generate" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 60
```

This is a connectivity check, not a measured run. `stream = false` returns the complete answer together. `num_predict` caps the number of generated tokens, which are small pieces of text. Measured request settings live in [bench/workload.json](../bench/workload.json); [bench/inference.js](../bench/inference.js) uses them.

**Check:** `response` contains text and `done` is `true`.

Use the Service URL for load tests. `kubectl port-forward deployment/ollama` selects one pod and does not test traffic distribution across replicas.

Sources: [Minikube Service access](https://minikube.sigs.k8s.io/docs/handbook/accessing/), [Ollama generate API](https://docs.ollama.com/api/generate).

## 7. Check the load scenario

The existing [bench/inference.js](../bench/inference.js) reads the shared [workload settings](../bench/workload.json) and owns the arrival schedule, metric names and k6 thresholds. It starts requests on a schedule so slow answers do not silently reduce the requested arrival rate. Open that file to inspect its current settings.

For a short path check, use the launcher with a new folder:

```powershell
$runDir = Join-Path 'results/load-check' ("{0}-{1}" -f [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'), [Guid]::NewGuid().ToString('N').Substring(0, 8))
python .\bench\run_pilot.py --base-url "$env:BASE_URL" --rate 2 --duration 1m --run-dir "$runDir"
```

`--rate 2` means two requests per ten seconds. The [launcher](../bench/run_pilot.py) refuses an existing path before starting any process. It requires one stable ready replica and no HPA, observes 60 seconds of idle state, performs a separate warmup generation, runs k6 with continuous observation and records another 10 seconds afterward. It saves request events, raw metrics, a summary, metadata, snapshots, preserved inputs and a collection check. Do not start another observer for this command. The [pilot plan](plans/measurements-and-pilot.md#2-saved-run-format) owns the detailed sequence, options and failure interpretation; this short check does not select pilot rates.

Check `console.txt`, `summary.json` and the recorded exit code. Successful responses, response errors and `dropped_iterations` are different counts. A dropped iteration is a scheduled request that k6 could not start. Missing optional token/load measurements remain missing; the script records their availability separately.

**Check:** requests reach the service, replies are valid, and no scheduled requests are dropped. A threshold failure is a result to inspect, not automatically a broken script. The final experiment targets must be agreed before the main comparison.

Sources: [k6 arrival models](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/), [JSON output](https://grafana.com/docs/k6/latest/results-output/real-time/json/).

## 8. Find the useful load range for one replica

Use the active [Measurements and pilot load tests plan](plans/measurements-and-pilot.md). It owns the probe sequence, stop rules, saved run format and choice of low/peak rates. The completed pilot selected low=2 and peak=8 requests per 10 seconds, with two five-minute confirmations each; see [the saved report](../results/pilot/discovery-2026-10-18-series1/README.md). Freeze the main protocol before comparing replica modes. This guide does not define another pilot protocol.

## 9. Test three replicas manually

A preliminary three-copy check is implemented and has [saved results](../results/fixed-replicas/check-2026-10-20-series1/README.md). Follow [Manual replica comparison](plans/scaling-experiment.md#1-manual-replica-comparison) for commands, individual warmups and Service distribution checks. The repeated main comparison still needs the agreed protocol. That section owns the scale commands, warmup checks and traffic-distribution checks. Completion criteria are in [roadmap step 18](ROADMAP.md#18-test-three-manually-configured-replicas).

## 10. Configure automatic scaling

The preliminary HPA mode uses [deploy/hpa.yaml](../deploy/hpa.yaml): 1-3 copies, CPU target 60%, and a 300-second downscale stabilization window. Use a current Service tunnel URL and a new run directory:

```powershell
python .\bench\run_pilot.py --base-url "$env:BASE_URL" --mode autoscaling --profile burst --low-rate 2 --rate 8 --run-dir results/autoscaling/NEW/burst-1
```

The launcher resets to one copy, observes idle for 60 seconds, warms that initial model, applies HPA and waits for two numeric CPU/ScalingActive samples at one ready copy. It then runs the shared 782-second burst and records another 300 seconds without new requests. New copies are not separately warmed. Per-pod logs stream to disk before a pod can disappear. At completion or failure, it stops collection, removes this HPA and restores one copy; `recovery.json` records that restoration separately.

Omit `--duration` and `--replicas` in this mode. A failed response threshold can still have valid measurements. Missing log coverage, an API failure, a restart or changed configuration stops the run and retains partial data. Follow the [active plan](plans/scaling-experiment.md#2-preliminary-hpa-implementation-and-check) for acceptance criteria. The [saved preliminary check](../results/autoscaling/check-2026-10-20-series1/README.md) verifies growth and reduction; the repeated main comparison remains separate.

## 11. Save cluster observations

The observer already exists in [bench/observe.py](../bench/observe.py). Follow [OBSERVATION.md](OBSERVATION.md) for its command, options, file format, units, error handling and limitations. Its output path must be new. Set this up before the pilot; an empty HPA list is valid until autoscaling is configured.

The [pilot plan](plans/measurements-and-pilot.md#1-measurement-design) defines how the launcher collects observation and request data together. The standalone observer command is for independent diagnostic sessions. Resource measurements use direct kubelet data; metrics-server is kept separately as the scaling signal.

## 12. Run the same tests in each mode

This step is planned. [Main run procedure](plans/scaling-experiment.md#3-main-run-procedure) owns preparation, mode switching, warmup and saved-run commands. Freeze the actual settings after the pilot before executing the matrix in [roadmap steps 20 and 21](ROADMAP.md#20-prepare-the-main-experiment-matrix-and-run-procedure). Startup and restart commands alone do not prepare a measured run.

## 13. Turn measurements into findings

[bench/analyze.py](../bench/analyze.py) generates per-run CSV/JSON summaries and aligned PNG/SVG plots for saved pilot, preliminary fixed-three and autoscaling data. It refuses an existing output directory. The [pilot report](../results/pilot/discovery-2026-10-18-series1/README.md#reproduce-and-inspect) includes a reproduction command; [Main result analysis](plans/scaling-experiment.md#4-main-result-analysis) describes the remaining repeated comparison and reporting against agreed targets. The observation schema remains in [OBSERVATION.md](OBSERVATION.md).

CSV/JSON-only analysis uses Python's standard library. Plots additionally require the optional Matplotlib version declared in [pyproject.toml](../pyproject.toml):

```powershell
python -m pip install 'matplotlib>=3.10,<4'
```

For any saved pilot folder, choose a new analysis destination:

```powershell
$runDir = Read-Host 'Saved pilot run directory'
$analysisDir = Read-Host 'New analysis output directory'
python .\bench\analyze.py "$runDir" --output-dir "$analysisDir"
```

Add `--no-plots` when only CSV/JSON is required. The analysis commands read saved data; they do not generate a new load test.

Run `python -m unittest discover -s bench` from the project root. Numeric and lifecycle analysis tests do not require Matplotlib. Dedicated plot tests report a skip when this optional dependency is absent; install the version above to include it. Tests that execute real k6 report a skip when k6 is missing from PATH; collection and error-handling unit tests still run. The verified project-environment command is `.\.venv\Scripts\python.exe -m unittest discover -s bench`. If that environment has no pip, install the plot dependency from a Python with pip using `python -m pip --python .venv install "matplotlib>=3.10,<4"`. These tests use temporary files and local HTTP fixtures, not the live cluster.

The launcher accepts an optional `--slo-ms VALUE` to check p95 successful-response latency in milliseconds and saves `slo_ms` in metadata. It deliberately ignores ambient `SLO_MS` and `K6_*` overrides. Omit the flag to leave the latency threshold unset. Existing k6 thresholds are at most 1% inference errors and zero dropped iterations; these are preliminary operating settings, not an agreed main protocol. Threshold failure is separate from collection validity.

## Troubleshooting

| Problem | What to check |
|---|---|
| Docker daemon unavailable | Docker Desktop is running and `docker info` succeeds. |
| Tool not found | Open a new PowerShell window after installation and check PATH. |
| Ollama server unavailable just after startup | Wait briefly and retry `ollama list`. |
| `ErrImageNeverPull` | Build the application image and load it into Minikube as in section 4. |
| Pod remains `Pending` | Inspect events and available CPU/memory for its requests. |
| `OOMKilled` | The container exceeded its memory limit. Review limits during the pilot and keep later comparisons consistent. |
| Service URL does not respond | Keep the tunnel open and use its current port. |
| HPA shows `<unknown>` | Once HPA exists, check metrics-server and `top pods`; follow the scaling plan. |
| More replicas give no improvement | Check request distribution and shared CPU/memory limits using the scaling plan. |
| kubectl version mismatch | Use Minikube's client: replace `kubectl --context ai-lab` with `minikube -p ai-lab kubectl --`. |

Inspect a problem pod:

```powershell
kubectl --context ai-lab -n inference get pods
$podName = Read-Host 'Pod name to inspect'
kubectl --context ai-lab -n inference describe pod $podName
kubectl --context ai-lab -n inference logs $podName
```

`describe` shows state and events. `logs` shows program output. Do not start a large test while a single request or short path check is failing.

## Stop and resume

Stop the load generator and observer, then close the tunnel with `Ctrl+C`.

```powershell
minikube stop -p ai-lab
```

This stops the cluster and keeps its saved environment. To resume, open Docker Desktop and run:

```powershell
minikube start -p ai-lab
kubectl --context ai-lab -n inference rollout status deployment/ollama --timeout=180s
kubectl --context ai-lab -n inference get pods
```

Open a fresh Service tunnel as in section 6 and update `BASE_URL`. For measurements, follow the preparation and warmup procedure in the relevant pilot or scaling plan. A successful restart does not make an old run's state current evidence.

<a id="research-alternatives"></a>

## 14. Decisions and experiment limits

Use these documents for the maintained explanations and rules:

| Topic | Document that owns it |
|---|---|
| Current progress and active work | [STATUS.md](STATUS.md) |
| Milestones and completion criteria | [ROADMAP.md](ROADMAP.md) |
| Components and runtime flow | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Accepted choices and readiness policy | [DECISIONS.md](DECISIONS.md) |
| Detailed technology alternatives | [Technology Decisions in Notion](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a) |
| Orchestration-platform research | [Research document, section 6](<../docs/PDP Research document.pdf>) and its [editing source](../docs/README.md) |
| Measurement fields, units and limits | [OBSERVATION.md](OBSERVATION.md) |
| Pilot procedure and selection rules | [Measurements and pilot load tests](plans/measurements-and-pilot.md) |
| Planned scaling runs and main analysis | [Scaling experiment plan](plans/scaling-experiment.md) |
| Actual run data and conclusions | The report next to each run under `results/` |

If a planned procedure conflicts with an accepted decision or the implementation, fix the conflict before running the experiment. Keep unavailable measurements missing and preserve earlier runs. The plans and decisions define the detailed rules; this guide provides setup commands and links to them.

# Fresh setup reproduction check

I ran this check on 6 November 2026 from a fresh clone of GitHub main at `c1e43b1552401c8dbc412c09cda8115baf59c792`. I created a new Python environment and a separate Minikube profile, `ai-lab-repro24`, with its own kubeconfig. This was a new setup on the same Windows computer.

## Setup

| Tool | Version used |
|---|---|
| Windows 11 | 25H2, build 26200 |
| Python | 3.12.0 |
| Docker Desktop and Engine | 4.95.0 and 29.8.2, Linux engine on WSL 2 |
| Minikube | 1.39.0 |
| Kubernetes and kubectl | 1.37.0 and 1.36.1 |
| Node containerd | 2.3.4 |
| k6 | 2.2.0 |
| Ollama and model | 0.34.4 and Qwen2.5 0.5B |

I used the Docker driver with 8 CPUs and 12 GiB requested for Minikube. I downloaded the model in a separate helper, built the pinned Dockerfile under the host tag `ai-inference:repro24` and loaded that image into the new profile. The short names in `minikube image tag` returned exit code 0, but the pod reported `ErrImageNeverPull`. The full names worked. I verified that the target tag was listed before the pod became Ready.

```powershell
minikube -p ai-lab-repro24 image tag docker.io/library/ai-inference:repro24 docker.io/library/ai-inference:0.1
minikube -p ai-lab-repro24 image ls
```

I checked `kubectl top nodes` and got a completed text response through the Service tunnel. The [Service check](service-check.json) records the Ollama version, model digest and running image ID. See the [setup guide](../../../md/GETTING_STARTED.md) for the full procedure and the machine-specific values.

## Short live run

I sent 2 requests per 10 seconds for one minute to one copy, with no HPA. All 13 requests succeeded. Collection passed with zero errors or warnings. No requests failed, were dropped or remained unfinished. Successful-response p95 was 1.228 seconds. See the [collection check](live-run/collection-check.json), [run metadata](live-run/metadata.json) and [analysis summary](live-analysis/summary.csv).

I used the same launcher and analyzer as in the guide. With the Service tunnel open, the run and analysis commands are:

```powershell
$runDir = 'results/load-check/reproduction-new'
.\.venv\Scripts\python.exe -B bench/run_pilot.py --context ai-lab-repro24 --base-url $env:BASE_URL --rate 2 --duration 1m --run-dir $runDir
.\.venv\Scripts\python.exe -B bench/analyze.py $runDir --output-dir "${runDir}-analysis" --no-plots
```

Use new run and analysis paths. To regenerate just the saved check, pass this report's `live-run` folder to the analysis command.

## Main series replay

I replayed the 18 archived runs with `bench/summarize_main.py --no-plots` in the fresh Python environment. The [13 regenerated CSV and JSON hashes](main-replay-sha256.csv) match the [saved comparison](../../main/series-2026-10-25-v1.1/analysis-main-2026-10-26/README.md) byte for byte. The replay reads saved runs and sends no requests.

The live check confirms the path from setup to a collected run and CSV/JSON analysis. The main comparison was replayed from saved data. The check does not cover a second physical machine or an independent handover to another person.

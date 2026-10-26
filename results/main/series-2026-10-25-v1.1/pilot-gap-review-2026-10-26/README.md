# Pilot-to-main latency gap review

Reviewed on 2026-10-26 without generating new requests. comparison.csv/json covers all eight valid pilot runs and three main fixed-one/steady runs. Existing measurements and previous analyses are unchanged.

## Supported observations

The request object is identical: prompt/model name, non-streaming response, 64-token maximum, context 1024, two threads, temperature 0 and seed 42. Successful responses in this comparison all report 56 output tokens. The initial image ID, container CPU/memory settings, environment and recorded tool versions match. The main series records model digests explicitly; the pilot metadata does not provide the same direct model-digest record.

At the selected rate, actual request starts are 1.25 seconds apart in both stages. Pilot peak client in-flight maxima are 24 and 14, versus 2, 3 and 2 in main steady. In-flight means started but not yet completed at the client; it includes transport, waiting and execution. It is not a directly measured Ollama queue length. The serial configuration and growing response delays support a queueing interpretation, but do not localize every wait.

Pilot low-load mean response times are 1.317 and 1.308 seconds, with no overlap between requests. Pilot peak first responses are about 1.38 seconds, then delays accumulate; first-30-second means are already 2.80/2.94 seconds. Main fixed-one/steady means are 0.954/1.094/1.154 seconds, with first-30-second means 0.958/0.893/0.997 seconds. The lower isolated-response margin around the 1.25-second arrival interval can produce a large backlog difference. For illustration, a constant 1.35-second service time versus arrivals every 1.25 seconds would accumulate about 24 seconds of waiting over 240 arrivals; this is an illustrative queue model, not a fitted server-time measurement.

In the first pilot peak, mean successful latency by request-start 30-second windows grows from 2.80 seconds to 29.39 seconds. The second peak grows and partly recovers. This temporal pattern is retained in latency-windows.csv and queue-comparison.png/svg. The plot's upper panel shows successes; the lower panel includes all starts and completions, including timeouts.

The client elapsed versus k6 HTTP-duration median difference is about one millisecond in both stages. Reported model-load durations in the two pilot peaks average about 1.2 milliseconds and never exceed 3.6 milliseconds for successful requests; repeatedly cold-loading the model does not explain their tens-of-seconds successful latencies. Request/raw-metric reconciliation passes.

## Procedure and scope differences

Main runs add explicit initial/post-warmup quiet-state checks. The three main fixed-one/steady loads begin 35-50 seconds after warmup completion; pilot loads begin about 0.15 seconds after warmup. This is a real procedure difference, but these observations do not isolate its causal contribution. The pilot also shows slower responses throughout its low-load runs, so a single post-warmup observation alone cannot establish the explanation.

The pilot README reports an 8-CPU/12-GiB Minikube container quota. A read-only current docker inspect also returns 8 CPU/12 GiB; see current-quota-inspection.json. The main metadata's 24 CPU comes from docker info and describes the engine, not the Minikube-container quota. The records do not establish an 8-to-24 CPU quota increase. Current inspection cannot prove historical quotas during every main run.

The image ID matches, and the recorded Python, Windows build, k6, Minikube, Kubernetes and Docker versions match. Changes in inference.js affect extra primary metrics, threshold configuration and burst definitions; request payload, steady executor/rate, HTTP call, elapsed-time measurement and connection-reuse setting remain the same. The earlier raw latencies are therefore not explained by using a different percentile or a weaker offered rate.

## Remaining unknowns

The observed queueing difference explains the shape and magnitude of the latency gap. The physical reason for faster effective processing in the main stage is not identified. Historical Windows background activity, CPU frequency/power/thermal state, cgroup throttling counters and server queue/evaluation timings were not collected. Host contention, frequency changes and runtime/cache state remain hypotheses. Do not assert that a game, extra CPUs, a model change or the new settling gate caused the improvement.

Both result sets remain valid within their recorded conditions. The pilot peak is not a stable capacity threshold for a shared computer. Preserve the main matrix and its frozen targets; no additional 18-run series is justified merely by this diagnostic.

## Reproduce

From the repository root, choose a new destination; plotting uses the existing optional Matplotlib dependency:

```powershell
.\.venv\Scripts\python.exe -B results/main/series-2026-10-25-v1.1/pilot-gap-review-2026-10-26/verify.py results/main/series-2026-10-25-v1.1/pilot-gap-review-rerun
```

The script reads saved data only, checks the compared payload/container/version identities and archive hashes, then writes tables and two plot formats. It refuses an existing output directory. current-quota-inspection.json is a separately retained live diagnostic observation, not generated by this offline script.

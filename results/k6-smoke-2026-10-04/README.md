# Short k6 load check

Verified on 2026-10-04 using k6 2.2.0 and one CPU replica of Ollama in the `ai-lab` cluster.

## Configuration

The steady scenario schedules 2 requests per 10 seconds for 1 minute, with a 30-second request timeout. One warmup request was sent outside k6 and is excluded from its measurements. The prompt and model settings match the guide. No latency target was applied; the main experiment target must be selected after pilot runs.

## Observed results

| Measurement | Result |
|---|---|
| Completed requests | 13 |
| Incorrect or failed inference responses | 0 |
| Scheduled iterations not started | 0 |
| Mean complete-response latency | 1.043 s |
| Median complete-response latency | 1.011 s |
| p95 complete-response latency | 1.154 s |
| Maximum complete-response latency | 1.282 s |
| Output length | 56 tokens per response |
| k6 exit code | 0 |

The configured rate implies about 12 requests over a minute; the observed count above is taken from the actual run. The deployment had one available replica before and after the run, with no container restarts. Raw inference-error and latency samples were checked against the exported summary.

This check confirms that the load generator reaches the model through the Kubernetes Service and saves usable results. It does not establish maximum capacity, an acceptable latency target, or an autoscaling advantage. It uses one physical host, one repeated short prompt, a warm model and possible prompt caching; p95 is based on only 13 responses.

## Saved evidence

[metadata.json](metadata.json) contains the rate, units, timestamps, model request, tool version and script hash. [requests.json](requests.json) contains the raw k6 metric samples; [summary.json](summary.json) contains aggregates. The console output, warmup response and Kubernetes snapshots are saved alongside them.

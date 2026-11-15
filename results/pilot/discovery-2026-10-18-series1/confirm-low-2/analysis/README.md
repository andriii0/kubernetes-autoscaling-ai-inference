# Pilot analysis

Source folders:
- C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference\results\pilot\discovery-2026-10-18-series1\confirm-low-2

I calculate successful-response percentiles with linear interpolation at (n-1)*p and count errors separately. Failures are included in completed requests; dropped iterations never started.

Resource summaries use source timestamps from scenario start through client drain; idle/warmup and post-load samples remain visible in plots. CPU mean is the arithmetic mean of available source-interval averages, not integrated CPU consumption. Missing rates remain gaps, and CSV missing values are empty.

I group counts in ten-second buckets; the last bucket can be partial. I report whole-run p95 with its sample count and keep collection failures visible. Runs with failed collection do not establish capacity.

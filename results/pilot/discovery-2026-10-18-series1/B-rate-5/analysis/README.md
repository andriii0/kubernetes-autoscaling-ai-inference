# Pilot analysis

Source folders:
- C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference\results\pilot\discovery-2026-10-18-series1\B-rate-5

Successful latency percentiles use linear interpolation at (n-1)*p; errors are excluded from latency but counted separately. Failure counts are part of completed requests. Dropped iterations never started. Resource summaries use source timestamps within the scenario-start to client-drain interval; idle/warmup and post-load samples remain visible in plots. CPU mean is the arithmetic mean of available source-interval averages, not integrated CPU consumption. Missing rates remain gaps, and CSV missing values are empty. Counts are ten-second buckets; the last bucket can be partial. Whole-run p95 is shown with its sample count. Collection failures remain explicit in the summary; those runs do not establish capacity.

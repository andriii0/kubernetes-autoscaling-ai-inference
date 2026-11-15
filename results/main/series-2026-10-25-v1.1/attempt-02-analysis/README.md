# Pilot analysis

Source folders:
- C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference\results\main\series-2026-10-25-v1.1\attempt-02-fixed-3-steady

I calculate successful-response percentiles with linear interpolation at (n-1)*p and count errors separately. Failures are included in completed requests; dropped iterations never started. started_per_second divides starts by scheduled_seconds (the scheduled load duration). completed_per_second divides completions by client_window_seconds (scheduled load plus any client drain). These rates use different windows and are not a direct completion ratio.

Resource summaries use source timestamps from scenario start through client drain; idle/warmup and post-load samples remain visible in plots. CPU mean is the arithmetic mean of available source-interval averages, not integrated CPU consumption. Missing rates remain gaps, and CSV missing values are empty.

I group counts in ten-second buckets; the last bucket can be partial. I report whole-run p95 with its sample count and keep collection failures visible. Runs with failed collection do not establish capacity.

For three copies, plots and per-replica-resources.json use each pod's own source timestamps. Total instantaneous resource values stay missing when source timestamps differ; asynchronous rates are not added.

For main runs, assessments.json applies protocol targets to the primary start-time phase; primary-resources.json integrates source counter intervals over scheduled load only, with coverage. Node consumption and observed per-instance memory peaks are reported separately.

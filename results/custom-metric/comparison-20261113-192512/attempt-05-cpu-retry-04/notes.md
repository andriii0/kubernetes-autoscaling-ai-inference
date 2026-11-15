Historical snapshot at the time this attempt stopped. The current outcome is recorded in the parent series report.

The series stopped again at 12:12:00 UTC (13:12 Berlin) on 14 November. Attempt 05 retry 04 recorded 393 started and 392 completed requests, with no summary. The clock guard failed again; the saved observation near 12:10:30 UTC shows Prometheus about 1.384 seconds ahead of the Windows receive time. Full cleanup passed. Four cells remain accepted; cell 6 never started.

The Hyper-V clocksource was still selected at the subsequent runtime check, so the mitigation did not prevent recurrence. No experiment process or continuation task remained; HPA was absent and one Ollama copy was Ready. No new load was started. The cause of the clock jump remains unresolved.

The host recovery changed instance identities, the timing environment and the continuation procedure. The first four runs retain their own validated evidence, but matching images/configuration alone does not establish that a later recovered pair forms an unchanged six-cell protocol. The original frozen-configuration rule requires an explicit decision about that boundary. I must resolve it, together with the clock failure, before treating further runs as the final comparison. A fresh complete series under stable settings is the conservative option; it has not been launched.

Historical startup snapshot:

This replaces the incomplete fifth CPU attempts in a separate folder. The first four accepted cells remain intact.

At 2026-11-14T12:05:07.884164+00:00, the independent continuation was running `attempt-05-cpu-retry-04` in measured CPU load with four of six cells accepted. 44 requests had started and 38 had completed, more than two minutes after the first measured request, with no recorded collection errors. The active-1 cell follows only after this CPU cell passes full load, post-load, collection and cleanup checks. This confirms startup, not an accepted fifth result.

Before this retry, the host had rebooted. I restored the same cluster settings and recorded fresh metric-pod identities with unchanged images. I temporarily selected the Hyper-V clocksource; the cause of the earlier clock jumps remains unresolved. The five-minute idle check and full cleanup passed. All measurement settings and guards are unchanged. The final comparison must disclose the session boundary.

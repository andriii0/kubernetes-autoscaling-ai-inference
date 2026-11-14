# Clock recovery and explicit continuation

At 2026-11-13T23:47:28.942016+00:00, the continuation was running with four of six cells accepted. `attempt-05-cpu-retry-03` had reached measured CPU load: 11 requests started and 10 completed. The final active-1 cell follows only if the CPU cell passes full collection and cleanup. This snapshot confirms load startup, not either remaining result.

The saved clock bounds changed abruptly between 23:04:01 and 23:04:06 UTC on 13 November. Prometheus was then about 1.015 seconds ahead of the Windows receive time. Live clocks were aligned again before I changed any clock setting. I could not establish the underlying host/guest trigger from the available logs. I did not change system clocks, restart the infrastructure, weaken the one-second guard or modify collectors.

Before launch, 36 idle observations over three minutes passed, followed by the existing backend CPU quiet and two fresh gateway-zero checks. All 53 focused tests passed. The accepted-prefix replay retained cells 1-4 and listed only cells 5-6. All 596 pre-existing non-Markdown series files matched their saved hashes before launch; the continuation intentionally updates the manifest and keeps its previous version in the resume directory.

I launched the existing Python worker through a new hidden, one-time Windows task at 23:41:39 UTC on 13 November (00:41:39 Berlin on 14 November). It has Limited privileges, no recurring triggers and no automatic restart. The recorded process ancestry reaches the Windows Schedule service. The worker deletes its task when it exits.

Evidence: [failed query bounds](failed-clock-bounds.json), [environment check](environment-check.json), [idle validation](verification.json), [cleanup](idle-check/recovery.json), [prefix replay](prefix-replay.json), [launch](launch.json), [processes](startup-processes.json), and [measured-load startup](measured-load-startup.json).

Historical snapshot at the time this attempt stopped. The current outcome is recorded in the parent series report.

This retry stopped around 22:19 UTC on 13 November when the driver and child processes disappeared. Of 420 started requests, 419 completed: 232 succeeded and 187 failed. The load and post-load periods were incomplete.

Windows recorded a Codex hang in the same minute, but the cause of the process interruption is unproven. I ran cleanup separately; it passed. The event export, stale manifest and lock are saved in [the recovery directory](../resume-check-app-interruption/).

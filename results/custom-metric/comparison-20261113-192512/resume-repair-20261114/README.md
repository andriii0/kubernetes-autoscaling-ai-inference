# Repairs and host recovery on 14 November

Retry 03 stopped during measured CPU load on 13 November: the clock guard failed at about 23:48:11 UTC and the attempt finalized at 23:48:56 UTC. It recorded 19 started, completed and successful requests, but no complete summary. Full cleanup passed. It is not an accepted fifth result. The earlier three-minute idle check did not establish a lasting clock fix.

## Code corrections

I fixed continuation after a cell has been accepted but the next cell's preflight fails. The accepted cell is replayed and retained; only the next cell is pending. Results now keeps superseded failed attempts visible while excluding them from the completion verdict when an accepted replacement exists. The reviewer already reports recorded launcher failures before missing request files. I widened only a test fixture's sampling interval from 50 to 200 ms to avoid a machine-speed-dependent test failure; the real interval remains five seconds.

After the host reboot, I added an explicit instance-renewal record to continuation. It is allowed only between complete pairs, validates the original identities and unchanged image digests, and is archived with the continuation. Live preflight still requires the prepared stack configuration, backend configuration, model and node resource limits. An unrecorded instance change is rejected. The unchanged collector continues to reject restarts and identity changes within each run.

All 269 Python tests passed after the recovery change. Six browser tests passed for the earlier Results change; the later driver change does not alter the UI. No workload, collector, target, model or resource setting changed. No commit or push was made.

## Clock investigation

The saved trace shows chronyd calls to clock_adjtime and Docker initd calls to settimeofday. This establishes that both processes access the guest clock; it does not establish a conflict or identify which caused the observed jump. A clock_adjtime call can also read clock state. The underlying trigger remains unresolved.

The original 180-second probe and the subsequent 600-sample Hyper-V probe both had zero one-second violations. I temporarily changed the WSL kernel clocksource from tsc to hyperv_clocksource_tsc_page. A passing probe after that change does not prove causality because the baseline also passed. No persistent clock configuration was changed. The isolated temporary tracing instance was absent after the host reboot; it did not survive into this run.

## Host recovery

Windows rebooted while the series was already stopped. On resuming work, Docker was off and the ai-lab API was unavailable. I started Docker and the existing ai-lab profile. All three metric containers had restarted once; Ollama's prior restart count rose from three to four before new load.

I saved the restarted pod state and bounded logs in host-recovery, verified the original stack and images, and renewed only the three metric pods under their unchanged Deployments. The new pods are Ready with zero restarts. The original node limits remain 8 CPU and 12 GiB, with the same power scheme. The identity mapping is in host-recovery/infrastructure-recovery.json. The temporary Hyper-V clocksource was reapplied for this session.

The first four accepted results remain valid under their own archived checks. Both cells of pair 3 will use the recovered environment. The final interpretation must disclose this session boundary and the provisional clock mitigation. Four accepted results are not a completed six-cell comparison; failed attempts remain visible and excluded.

## Verification and independent startup

The fresh validation after reboot passed 60 idle observations over 300 seconds, full backend quiet/fresh-zero cleanup, and accepted-prefix replay. All 737 protected files were unchanged before launch. See validation-after-reboot/verification.json. The continuation intentionally updates the manifest and archives its preceding version.

The hidden Windows task started at 11:57:38 UTC on 14 November. It runs with Limited privileges, no recurring trigger and no automatic retry. Its Python worker deletes the task when the continuation exits. The task definition, worker, launch record and process snapshot are saved here.

At 2026-11-14T12:05:07.884164+00:00, the independent continuation was running `attempt-05-cpu-retry-04` in measured CPU load with four of six cells accepted. 44 requests had started and 38 had completed, more than two minutes after the first measured request, with no recorded collection errors. The active-1 cell follows only after this CPU cell passes full load, post-load, collection and cleanup checks. This confirms startup, not an accepted fifth result.

The Notion experiment-log update was attempted twice but automatic permission review timed out both times. The remote page was not confirmed updated; local Notes and this report contain the current record.

## Subsequent failure and interpretation

The series stopped again at 12:12:00 UTC (13:12 Berlin) on 14 November. Attempt 05 retry 04 recorded 393 started and 392 completed requests, with no summary. The clock guard failed again; the saved observation near 12:10:30 UTC shows Prometheus about 1.384 seconds ahead of the Windows receive time. Full cleanup passed. Four cells remain accepted; cell 6 never started.

The Hyper-V clocksource was still selected at the subsequent runtime check, so the mitigation did not prevent recurrence. No experiment process or continuation task remained; HPA was absent and one Ollama copy was Ready. No new load was started. The cause of the clock jump remains unresolved.

The host recovery changed instance identities, the timing environment and the continuation procedure. The first four runs retain their own validated evidence, but matching images/configuration alone does not establish that a later recovered pair forms an unchanged six-cell protocol. The original frozen-configuration rule requires an explicit decision about that boundary. I must resolve it, together with the clock failure, before treating further runs as the final comparison. A fresh complete series under stable settings is the conservative option; it has not been launched.

The [Notion experiment log](https://app.notion.com/p/417c7c697bfd8049a916f48c59ff1e75) was successfully updated on 14 November with retry 03, the host recovery, retry 04 failure and the unresolved protocol boundary.

# Active-request HPA threshold preparation

I checked targets 1 and 2 active requests per replica in that order. Both completed with valid collection and cleanup. Each used the same 782-second 2 -> 12 -> 2 burst and 300-second post-load window. These are preparation runs, separate from both historical comparisons and from the proposed six-run CPU/custom comparison.

## Outcome

| Target | Peak successful / started | Peak timeouts | Successful peak p95 | Mechanism qualifies | Service targets |
|---|---:|---:|---:|---|---|
| 1 active request per replica | 358 / 360 | 2 | 26.347 s | Yes | Missed latency |
| 2 active requests per replica | 360 / 360 | 0 | 3.600 s | Yes | Passed |

I selected **target 1** because the predeclared rule chooses the smaller qualifying threshold. It does not choose the lowest observed latency. Target 2 performed much better in this single preparation, but these two ordered runs are not repeated comparisons of thresholds. I retain both results and will not silently change the rule or call target 1 the better-performing threshold.

Both runs kept one desired/Ready copy during the initial low phase, grew to three and later reduced to one. No requests were dropped or left unfinished. The infrastructure identities, configurations and workload source hashes matched across runs, with the review-driver version exception recorded below. The six-run CPU/custom comparison has not started.

## Target 1

The load and cleanup completed. Collection is valid: 457 requests started and completed, 455 succeeded and two timed out. There were no dropped or unfinished requests. All 457 client IDs matched gateway records; native backend reconciliation also passed.

At peak, 358/360 requests succeeded. Successful-response p95 was 26.347 seconds, above the five-second target. Timeouts remain separate from that percentile.

The threshold qualifies under the declared mechanism rule: desired and Ready counts stayed at one during the initial low phase, then reached at least two about 7.1 seconds into the peak in the sampled observations. Growth to three and later reduction to one were observed. This does not establish model warmth or a benefit over CPU-based HPA.

Raw metric replay passed. The load window has 158 bounding/in-window observations, with maximum source age about 5.00 seconds. Cleanup removed HPA, restored one Ready copy, passed backend CPU quiet and observed two new zero scrapes.

## Review interruption and continuation

The driver stopped after target 1 because the shared assessor expected `protocol_version`, which is intentionally absent from preliminary run metadata. I reproduced the error offline. I corrected only the derived assessment view to label this extension; the saved raw metadata and load are unchanged.

I preserved the stopped state in [manifest-before-review-fix.json](manifest-before-review-fix.json). The [current manifest](manifest.json) records both driver hashes and the continuation reason. The first run's archived source remains intact. After 31 focused tests and a successful replay of its evidence, I continued with target 2 without repeating target 1.

## Target 2

All 457 requests succeeded, including all 360 peak requests. There were no errors, timeouts, dropped or unfinished requests. Peak successful-response p95 was 3.600 seconds. Desired count reached at least two about 20.1 seconds into peak; a second Ready copy was observed about 25.1 seconds into peak.

The native collection check, all 457 gateway ID matches and raw metric replay passed. The load window again has 158 bounding/in-window metric observations, with maximum source age about 5.01 seconds. Cleanup removed HPA, restored one Ready copy, passed backend CPU quiet and obtained two fresh gateway zeros.

I confirmed afterward that no HPA or load generator remained, Ollama was 1/1 Ready, and all three metric-stack components remained Ready without restarts. The stack is left installed. The preparation completed at 17:44:18 UTC on 13 November 2026.

## Evidence

- [Target 1 metadata](target-1/metadata.json), [collection check](target-1/collection-check.json) and [cleanup](target-1/recovery.json).
- [Target 1 assessment and signal replay](target-1-analysis/preparation.json).
- [Target 2 metadata](target-2/metadata.json), [assessment and signal replay](target-2-analysis/preparation.json) and [cleanup](target-2/recovery.json).
- [Frozen configuration and source hashes](frozen-inputs.json); the selected target is in the [manifest](manifest.json).
- [Final pre-launch test output](prelaunch-tests.txt): 240 tests passed before the review-only correction.
- Configurations, component/image identities, source hashes, continuous gateway/native logs and raw metric observations are stored inside each run.

The preserved Ollama pod's `lastState` includes a termination before this preparation began. It is historical container state, not a restart during these measurements.

## Final code verification

All 241 Python tests passed in the final repeat (63.856 seconds). The preceding post-run suite had two failed subcases in the existing accelerated HPA lifecycle fixture: observation gaps of 0.47-0.63 seconds exceeded its 0.10-second limit. That test passed separately without changes, followed by the passing full suite. I retain [the failed test output](postrun-tests-first.txt) and [the final passing output](postrun-tests-repeat.txt). I did not change the fixture or production limits. This remains an intermittent test timing issue; it is separate from the verified preparation records.

Final integrity verification preserved 120 historical evidence files, reproduced the previous aggregates and resolved 285 local links. No commit or push was made.

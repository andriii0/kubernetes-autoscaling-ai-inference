# Resume the peak-12 comparison

I will repair the comparison adapter for `comparison-20261110-205108-peak12` without changing its measured inputs or original driver.

1. Derive fixed-three activity from all three expected pod identities and positive saved completion counts, after replaying collection validation. Keep absent or incomplete evidence invalid.
2. Replay the consecutive saved prefix with the original source/environment checks. Reject partial attempts and holes. Retain the failed manifest and record the pause and repair.
3. Save the recovered third assessment in a new analysis directory and continue cells 4–9 using the original arguments, preparation and stop rules.
4. Check the host before live continuation. Run focused adapter tests and a read-only replay before launch.

Acceptance: the first three attempts replay without measurement changes; the third is a target miss, not invalid data. Missing fixed-three activity still stops. Live progress is reported separately from completion. The original driver and raw measurements remain preserved.

## Verification and execution

### Recover attempt 07 and prevent log loss

Recovery and continuation are complete. I reused the continuous collector for fixed modes and recorded the allowed old/new launcher hashes explicitly, keeping all other source checks strict. Focused tests passed; detailed evidence and the collection-method limitation are in the [recovery report](../../results/follow-up/comparison-20261110-205108-peak12/LOG_RECOVERY.md). I checked the final manifest: all nine cells are complete and combined analysis was saved. The original failed seventh attempt remains preserved.

I confirmed rotation on the node: the second pod's `2.log.20261110-232000` contains exactly the 25 missing generation completions. I will preserve the failed attempt, recover into a separate evidence directory with source hashes and provenance, and replay collection before accepting it. I will reuse the existing continuous `autoscaling.Logs` collector for fixed-mode runs, with explicit shutdown and failure reporting. Remaining runs must retain archived-source checks; any collector change needs an explicit source-version boundary rather than silently accepting a mismatch. Verification covers rotation recovery, stream failure and cleanup, followed by a read-only series replay before live continuation.

I added `bench/resume_peak12.py`, reusing the existing corrected `comparison_input` and `require_assessable` functions in `bench/run_peak12_comparison.py`. The original saved driver still owns arguments, source checks, environment comparison and execution helpers. Two focused tests passed: saved attempts 1–3 replay successfully and missing expected replica evidence stops before assessment. The read-only dry run lists cells 4–9 as pending.

The first continuation preflight queried the default namespace and stopped before load or manifest changes. I corrected the query to the observer's `inference` namespace and launched continuation again. Each launch keeps its host snapshot and source in a separate `resume-*` folder. The successful continuation archives the previous failed manifest and records the pause. Completion remains unverified until the driver finishes.

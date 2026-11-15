# Resume the peak-12 comparison

Status: complete. I repaired the comparison adapter for `comparison-20261110-205108-peak12` without changing its measured inputs or original driver.

1. Derive fixed-three activity from all three expected pod identities and positive saved completion counts, after replaying collection validation. Keep absent or incomplete evidence invalid.
2. Replay the consecutive saved prefix with the original source/environment checks. Reject partial attempts and holes. Retain the failed manifest and record the pause and repair.
3. Save the recovered third assessment in a new analysis directory and continue cells 4–9 using the original arguments, preparation and stop rules.
4. Check the host before live continuation. Run focused adapter tests and a read-only replay before launch.

Acceptance: the first three attempts replay without measurement changes; the third is a target miss, not invalid data. Missing fixed-three activity still stops. Live progress is reported separately from completion. The original driver and raw measurements remain preserved.

## Verification and execution

### Recover attempt 07 and prevent log loss

Recovery and continuation are complete. I reused the continuous collector for fixed modes and recorded the allowed old/new launcher hashes explicitly, keeping all other source checks strict. Focused tests passed; detailed evidence and the collection-method limitation are in the [recovery report](../../results/follow-up/comparison-20261110-205108-peak12/LOG_RECOVERY.md). I checked the final manifest: all nine cells are complete and combined analysis was saved. The original failed seventh attempt remains preserved.

I confirmed rotation on the node: the second pod's `2.log.20261110-232000` contains exactly the 25 missing generation completions. I preserved the failed attempt, recovered the records into a separate evidence directory with source hashes and provenance, and replayed collection before accepting it. I reused the existing continuous `autoscaling.Logs` collector for later fixed-mode runs, with explicit shutdown and failure reporting. The source-version boundary is recorded instead of silently accepting a mismatch.

I added `bench/resume_peak12.py`, reusing the existing corrected `comparison_input` and `require_assessable` functions in `bench/run_peak12_comparison.py`. The original saved driver still contains the argument, source-check, environment-comparison and execution helpers. Two focused tests passed before continuation: saved attempts 1–3 replayed successfully and missing expected replica evidence stopped before assessment. The read-only dry run listed cells 4–9 as pending at that checkpoint.

The first continuation preflight queried the default namespace and stopped before load or manifest changes. I corrected the query to the observer's `inference` namespace and launched continuation again. Each launch keeps its host snapshot and source in a separate `resume-*` folder. The successful continuation archives the previous failed manifest and records the pause.

## Final result

The comparison is complete. All nine planned cells have valid full-load evidence. Fixed one missed the latency and error targets in all three repetitions. HPA reduced peak failures from 698 across the three fixed-one runs to 89, but missed the five-second p95 target in every repetition. Fixed three completed all 1,080 peak requests without an error, passed the p95 target twice and missed once at 5.116 seconds.

Attempt 07 was recovered from a rotated node log. The recovered directory contains the 25 records that were absent from the end-only snapshot, while the original failed attempt remains unchanged. The collector version changed before the last fixed-mode runs, so the final report must disclose that source boundary. It does not change the client measurements or workload settings.

I published the interpretation in the findings, Research v0.10 and the project summaries. This completes the comparison.

Verification (2026-11-11): all 167 local tests passed. The historical verifier preserved 120 protected evidence files, reproduced the saved aggregates and resolved 301 local links. Research v0.9 rendered to 13 pages and every page was checked at that checkpoint. No live load or cluster change was used for that documentation update.

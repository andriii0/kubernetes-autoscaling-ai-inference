# Attempt 07 log recovery

Continuation finished at 2026-11-11T00:38:04 UTC. The manifest contains nine accepted cells, and `combined-analysis/` contains nine run summaries. The final fixed-one peak p95 was 28.835 s with 192 peak timeouts; the final HPA peak p95 was 19.266 s with no peak failures. Both missed the 5-second target. These are valid measured target misses, not collection failures. Peak p95 uses successful requests only.

I recovered the missing server records from the node without repeating load. The original `attempt-07-fixed-3-burst` remains unchanged and failed. The derived `attempt-07-fixed-3-burst-recovered` contains a copy of its evidence plus the rotated CRI log and corrected validation metadata.

The node file `2.log.20261110-232000` for pod UID `ee38f8af-8777-45b4-aa55-7b6155c7defd` contains the 25 missing generation completions. The original server total was 432; restored logs reconcile all 457 completed successful client requests. The regular collection validator passes, and the comparison assessment is `pass`. Raw recovered bytes and their SHA-256 are retained in the derived folder. No requests or resource measurements were synthesized.

`log-recovery.json` maps the seventh cell to the derived folder and records the two accepted hashes of `run_pilot.py`. Other executable hash checks remain strict. For subsequent fixed-mode runs I changed end-only log snapshots to the existing continuous log collector. This is a collection-method boundary within the comparison, so the series should not be described as having identical collection code throughout. The workload and preparation rules remain the same.

Verification: 45 fixed-replica, autoscaling and comparison tests passed in the focused batch. The two resume tests passed after updating the saved-prefix expectation. Read-only replay accepted cells 1–7 and listed 8–9 as pending. Initial test execution required `PYTHONPATH=bench;tests/bench`; the fixture was updated to supply simulated continuous logs rather than invoke kubectl against simulated pod names.

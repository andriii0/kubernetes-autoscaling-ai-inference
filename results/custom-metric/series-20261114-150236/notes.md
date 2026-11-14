# Notes

I started a new cycle with code commit `5d50420`. I kept the old four results and all failed fifth-cell attempts in the retired series. I will not join those results to this cycle.

At 16:31 Berlin on 14 November, target 1 passed collection, scaling qualification and cleanup. All 457 started requests completed: 450 succeeded and 7 timed out. Successful peak p95 was 26.390 seconds, so the response targets failed. There were no dropped or unfinished requests. Target 2 had started preparation; the six comparison cells had not started.

The timer and experiment lock fixes are committed. They do not fix the physical host clock jump. I kept the strict clock guard, so another jump can stop this cycle.

## Verified later stop

Stopped at 16:38 Berlin on 14 November. Target 1 completed; target 2 failed on a clock difference around 1.53 seconds. It had 100 starts and 80 completions. No comparative cell started. Ubuntu time synchronization was later correlated with the clock step. I retain this cycle separately.

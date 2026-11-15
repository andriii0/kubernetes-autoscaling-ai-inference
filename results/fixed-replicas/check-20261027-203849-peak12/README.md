# Preliminary prepared three-copy check at rate 12

I ran one five-minute steady check on 2026-10-27 with three fixed Ollama copies and 12 requests per 10 seconds (1.2/s). HPA was absent. The launcher used the existing prepared fixed-mode path, individual pod warmups and fresh quiet-state gates. This is outside main protocol v1.1 and does not establish a repeated controlled comparison.

## Outcome

- 361 starts and client completions; all 361 succeeded. Zero response failures, timeouts, unfinished requests and dropped starts.
- Successful-response mean 4.066 seconds, p50 2.956 seconds, p95 9.507 seconds and maximum 14.773 seconds.
- The whole-run successful p95 target of 5000 ms was missed. k6/launcher exit code 99 records this target miss; collection remains valid, with collector exit code 0.
- Native server completion counts are 123, 118 and 120 across the three selected pods, all HTTP 200. They sum to the client total. Every pod completed its separate warmup before load and handled measured Service traffic. These aggregate logs do not attribute individual client requests to pods.

The scheduled load window is 20:48:31.249 through 20:53:31.249 UTC. The client window ends at 20:53:32.358 UTC. The observer retained 97 samples, zero collection errors and a maximum poll gap of about 5.027 seconds. The existing one-millisecond start-boundary warning is retained; duplicate appearances in derived output do not represent additional invalid requests.

## Verification and limits

The collector/analyzer replay accepts the run. Saved analysis matches recalculation, archived executable hashes match, and all three successful warmups are present. An independent interpolation of request-event p95 gives 9507 ms; the raw k6 successful-latency distribution matches those events. [review.json](review.json) records the checks. CSV/JSON analysis and per-pod resource records are in [the adjacent analysis](../check-20261027-203849-peak12-analysis/README.md); asynchronous pod resource samples are not summed into an instantaneous application total.

For context, the four earlier one-copy five-minute peaks at the same rate had successful p95 18.941, 27.730, 29.081 and 26.612 seconds, with 0/361, 153/360, 188/360 and 198/361 timeouts. This three-copy check has lower observed successful p95 and no timeouts, but still misses the agreed 5-second target. These are preliminary runs at different times and repetition counts on one shared computer; do not call the difference an isolated causal effect or claim that HPA will meet the target. Adding copies also increases the combined application CPU limit from 2 to 6.

A final read-only snapshot found three Ready copies and no HPA. I left those three copies running after the job finished, without starting HPA or repeating load. Normal server drain remains separately unverified in metadata; no equality rule is relaxed after timeouts. I kept all earlier pilot/main records and their original verdicts. The open issue remains in [PILOT_MAIN_DISCREPANCY.md](../../../md/PILOT_MAIN_DISCREPANCY.md).

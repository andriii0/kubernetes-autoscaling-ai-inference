# Interrupted fresh rate selection

Reviewed on 2026-10-27. I started this separate one-copy pilot to select low and peak rates under current host conditions. The background process disappeared before the fourth probe reached measured load. The series is incomplete; no peak or confirmed low/peak pair was established.

## Completed two-minute probes

Rates are requests per 10 seconds. p95 covers successful responses.

| Run | Rate | Successful / completed | Failed / unfinished / dropped | Successful p95, seconds |
|---|---:|---:|---:|---:|
| 01, discovery low | 2 | 24 / 24 | 0 / 0 / 0 | 1.0665 |
| 02, discovery peak | 8 | 97 / 97 | 0 / 0 / 0 | 1.1410 |
| 03, discovery peak | 10 | 121 / 121 | 0 / 0 / 0 | 1.7050 |

All 242 requests succeeded. Replayed collection checks are valid; archived executable hashes and saved analysis match. Probe 03 retains the previously accepted one-millisecond request-start boundary warning. All three meet the search's 5000-ms p95 and 1% response-error criteria. Rate 2 is only a calm candidate: the four five-minute confirmations never started.

## Last observed state

The next folder is `04-discovery-peak-rate-12`. Its metadata stops at `initial_quiet`, last written at about 11:07:30 UTC. It has no load-start timestamp, request events or finished timestamp. The driver PID 24876 was absent at the first scheduled check and the final review. No project pilot/observer process or k6 process was found at those checks. The logs contain no final driver result or captured explanation for the process exit.

The raw manifest still says `running`. I preserved it as the last driver-written record; [review.json](review.json) records the independently observed interruption. A stale manifest does not establish that the job is active. The process exit code, reason for termination and normal cleanup completion are unknown. I did not treat this as a target failure at rate 12 or evidence of its capacity.

The follow-up review was recorded after the process had stopped. It did not establish why the process disappeared.

## Meaning and limits

These short probes agree with the later fast one-copy results at rate 8. They do not explain the historical pilot slowdown, establish a sustained overload boundary, or show an HPA benefit. Rates 12, 16 and 20 were not measured, and no selected rate received the planned five-minute confirmations.

I preserved every existing raw file, the archived driver and earlier results. I did not start replacement load or change the main matrix. Any later search needs fresh runtime checks and new result paths so this partial attempt stays intact.

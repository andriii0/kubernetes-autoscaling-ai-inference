# Controlled peak-12 burst comparison

I ran the same `2 -> 12 -> 2` requests-per-10-seconds burst with one fixed copy, three fixed copies and HPA. Each mode has three repetitions. This follow-up is separate from main protocol v1.1, which used a peak of 8 requests per 10 seconds.

## Result

The table covers the 300-second peak. Successful-response p95 excludes failed requests, so failures are shown separately.

| Mode | Target passes | Successful p95 range | Successful / completed | Failed |
|---|---:|---:|---:|---:|
| Fixed one | 0 / 3 | 28.574-29.497 s | 382 / 1,080 | 698 |
| HPA | 0 / 3 | 19.266-29.801 s | 991 / 1,080 | 89 |
| Fixed three | 2 / 3 | 4.001-5.116 s | 1,080 / 1,080 | 0 |

One fixed copy was overloaded in every repetition. HPA reduced the number of failures and completed every request in its third repetition, but it missed the five-second p95 target in all three runs. Three warmed copies completed every peak request and gave the lowest latency. Its one target miss was 5.116 seconds.

All three HPA runs grew from one to three copies and later reduced capacity. The first extra running copy appeared about 50-111 seconds after the peak began. Three running copies appeared about 171-231 seconds into the peak. Extra capacity was therefore unavailable for much of the peak, while requests were already waiting.

These results apply to this local CPU setup, model, prompt and burst. They do not prove that fixed capacity is always better. A longer burst, pre-warmed spare capacity or another scaling signal could give a different result. Application CPU totals are not complete enough to claim CPU savings from HPA.

## Collection and recovery

All nine accepted runs have valid request and observation records, with no dropped or unfinished requests. Attempt 07 originally failed collection because an end-only log snapshot missed 25 completions after the container runtime rotated its log. I recovered those exact records from the node into `attempt-07-fixed-3-burst-recovered`. The original failed attempt remains unchanged.

I switched later fixed-mode runs to continuous log collection. The collector source therefore changes inside this follow-up series. The workload, request measurements and assessment rules did not change. [LOG_RECOVERY.md](LOG_RECOVERY.md) records the recovered file, hashes and validation.

## Evidence

- [Manifest and per-run verdicts](manifest.json)
- [Combined CSV and JSON analysis](combined-analysis/README.md)
- [Saved-data plots](plots/README.md)
- [Log recovery report](LOG_RECOVERY.md)
- [Comparison procedure](../../../md/plans/scaling-experiment.md#controlled-peak-12-burst-comparison)


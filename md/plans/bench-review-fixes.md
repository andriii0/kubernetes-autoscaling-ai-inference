# Benchmark review fixes

I want to reject unsupported fixed-one verdicts, retain missing measurements, prevent ambiguous analysis keys, and stop series continuation after failed HPA recovery.

1. Reuse the fixed-replica log check for main fixed-one runs. Keep the frozen protocol and saved evidence.
2. Count missing token samples explicitly, preserve missing model-load maxima, and reject duplicate output keys before writing.
3. Require successful HPA recovery before advancing the series. Keep recovery separate from the run assessment.
4. Check each regression offline, run the benchmark tests, replay the 18 saved main runs, and verify historical integrity.

## Verified results

- A fixed-one log with no requests or only warmup activity makes the run not assessable. The check uses generation completions in the k6 process window, which provides pod activity evidence without per-request attribution.
- Failed or absent HPA recovery stops the series review. Measured outcomes remain available. The frozen executable-input hash check still applies when continuing a series.
- The duplicate-folder test supplies two valid runs with the same folder name and checks that no output directory is created. Missing token counts appear under the JSON key "null". CSV model-load maxima stay empty when all values are missing, and measured zero remains zero.
- All 161 tests passed, including real k6 against local HTTP fixtures. The fixed-mode main fixture uses 200 ms observation intervals to give Windows scheduling more room.
- The 18 saved attempts replayed successfully. All 13 CSV/JSON artifacts matched the saved combined analysis byte for byte. The historical integrity check passed for 120 protected files, saved aggregates, and local links.

No live cluster or experiment was needed for these checks.

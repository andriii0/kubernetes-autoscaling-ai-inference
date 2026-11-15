# Bounded clock correction

I preserve the stopped first comparison and both threshold preparations. The collector now records query send/receive times and uses the same one-second clock allowance as initial checking. Source age in Prometheus's clock must still be between zero and ten seconds. Missing data and excessive offsets remain failures. Cleanup waits for two source zeros beyond the boundary plus the clock allowance.

The first focused suite passed all 58 checks. Browser checks initially failed because of process-access and dependency problems, then exposed an error in my test setup: it tried to use Results navigation while Runs was open. I corrected the setup; these checks sent no Kubernetes load.

All 254 Python tests and six browser tests passed. Their outputs are saved here. Both archived preparations replayed successfully with the corrected validator, without changing their settings or raw data.

The installed check saved five zero samples: two with the normal observer clock and three with a simulated observer offset of -0.8 seconds. I did not change system clocks or generate inference traffic. The existing cleanup path passed backend CPU quiet and two fresh gateway zeros, with HPA absent and one Ready Ollama copy. Effective backend configuration was unchanged.

The [collector record](collector-fix.json) fixes the old/new hashes of the two changed collector files. [Installed evidence](installed-collector/result.json) retains signals, original timestamps, component identities and cleanup. The before/after hashes matched for all 245 protected files in the threshold preparation and stopped comparison. The new driver requires this exact verified record before accepting the collector change; other unreviewed workload changes still fail.

Comparison v2 records this clock-validation boundary. HPA policies, selected target 1, routing, model, workload, source-age limit and six-cell order remain unchanged. The old interrupted run cannot be counted as complete. I reviewed and checked the change locally; external review was unavailable.

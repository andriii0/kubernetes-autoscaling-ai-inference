# CPU versus active-request HPA comparison v2

I launched this fresh comparison at 19:25:13 UTC (20:25 Berlin) on 13 November. The startup snapshot confirmed launcher PID 24292 and interpreter/driver PID 42856 with this exact directory. Attempt 01 CPU was in recovery quiet, no errors were recorded, and 0/6 runs were complete. This records startup only.

The six cells are CPU / active-1, active-1 / CPU, CPU / active-1. Both use the same Envoy, Prometheus and Adapter, the 782-second 2 -> 12 -> 2 requests/10 s burst, 300 seconds post-load and one to three replicas. CPU target 60%, request target 1, model, workload and backend resources are unchanged.

The [clock correction](../clock-fix-20261113/README.md) reconciles the collector's clock allowance with preflight and saves query send/receive bounds. Source age remains limited to ten seconds in Prometheus's clock; missing/stale signals and offsets beyond one second still fail. Cleanup requires two new zero scrapes beyond its boundary plus the clock allowance. The [collector boundary](collector-fix.json), source archive and preparation-code-boundary record the exact old/new hashes.

All 254 Python tests, six browser checks, both archived preparation replays and the installed collector/cleanup check passed before launch. I retain the [earlier stopped comparison](../comparison-20261113-180650/README.md) separately. Its missing load cannot be recovered or counted as a complete cell. No raw historical file was rewritten.

The [manifest](manifest.json) records progress and accepted outcomes. A service target miss is retained; invalid collection, changed inputs or failed cleanup stops progression. I will assess the policies only after reviewing complete saved evidence. The series is left unattended after startup, without automatic repeats. No commit or push was made at launch.

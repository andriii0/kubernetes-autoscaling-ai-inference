# Clock investigation, 14 November

I kept the old run files unchanged and checked the clock boundary without model load. Two 180-second probes collected 261 and 263 samples. Both had zero query errors and zero violations of the one-second bound. Maximum observer wall/monotonic difference was about 16 ms. See [the first probe](../clock-check-20261114-build/summary.json) and [the paired probe](../clock-check-20261114-paired-trace/summary.json).

The successful [kernel trace](clock-setters-retry1.txt) recorded `chronyd` frequency/error updates about every eight seconds and `initd` wall-clock sets about every 30 seconds. A later `chronyc tracking` query reported the PHC0 reference, a normal leap state and a microsecond-scale current offset. Only fields selected by each `adjtimex` mode are meaningful; other printed fields may be unused data.

No one-second jump occurred during these checks. The trace does not establish which process caused the earlier 1.384-second difference. I did not disable a synchronizer or change an OS clock setting. The Hyper-V clocksource was already selected; the earlier failure happened with that source. Temporary trace probes were removed after collection. The first trace attempt failed on line endings and remains saved separately.

I changed request duration to a pinned local Go monotonic timer, added paired observer clocks and a shared experiment lock, and corrected recovery-baseline reuse. The one-second guard remains strict. These code fixes do not establish a permanent fix for Windows/WSL time. A new series will use new preparation; its measured load is the next live check. [Legacy replay](legacy-replay.json) records the separate recheck of the old four cells.

The [final monitor check](../clock-check-20261114-final/verification.json) passed 33 idle observations over three minutes with the new code. The final Python suite passed 288 tests; six browser checks passed. This is a pre-launch check, not a completed load series.

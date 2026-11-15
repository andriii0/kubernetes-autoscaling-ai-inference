Historical snapshot of the retired 13 November series. The current outcome is recorded in the parent project status and the separate evening series report.

Four of six runs are complete. Run 5 (CPU) failed five times. First, kubectl crashed. Then the run process stopped. The last three attempts stopped because the Windows and Prometheus clocks differed by more than one second.

The latest attempt stopped on 14 November at 13:12 Berlin: 393 requests started and 392 finished. Cleanup passed. Run 6 has not started.

I fixed errors in resume and result reporting. I also tried the Hyper-V clock source, but the clock error happened again. The cause is still unknown.

After Windows restarted, I restored the cluster with the same images and settings. This changed the test environment. I kept the four complete runs and all failed attempts. The full comparison is still unfinished.

Details: [run report](README.md) and [clock investigation](resume-repair-20261114/README.md).

On 14 November I decided to keep this series as stopped. I will run new preparation and all six cells with the new timer. I will not add the new results to these four.

Later investigation (14 November) correlated the four clock failures with Ubuntu systemd-timesyncd synchronization steps in the shared WSL clock. The earlier unknown-cause wording records what I knew at that time. The separate [evening series](../series-20261114-191048/README.md) completed six new cells under a temporary synchronization guard, then restored the service. This old series remains retired with four accepted cells; I did not combine them.

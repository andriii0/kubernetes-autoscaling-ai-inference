Four of six runs are complete. Run 5 (CPU) failed five times. First, kubectl crashed. Then the run process stopped. The last three attempts stopped because the Windows and Prometheus clocks differed by more than one second.

The latest attempt stopped on 14 November at 13:12 Berlin: 393 requests started and 392 finished. Cleanup passed. Run 6 has not started.

I fixed errors in resume and result reporting. I also tried the Hyper-V clock source, but the clock error happened again. The cause is still unknown.

After Windows restarted, I restored the cluster with the same images and settings. This changed the test environment. I kept the four complete runs and all failed attempts. The full comparison is still unfinished.

Details: [run report](README.md) and [clock investigation](resume-repair-20261114/README.md).

On 14 November I decided to keep this series as stopped. I will run new preparation and all six cells with the new timer. I will not add the new results to these four.

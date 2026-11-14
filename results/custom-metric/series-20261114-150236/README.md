# Fresh CPU/request HPA cycle

I started this cycle on 14 November 2026 at 16:05:28 Berlin (15:05:28 UTC). It uses fresh target-1 and target-2 preparation, followed by six CPU/request cells in order: CPU, active-1, active-1, CPU, CPU, active-1. Comparison starts only if valid preparation selects target 1. There are no automatic retries.

The measurement code is local commit `5d50420`; [verification](../clock-check-20261114-final/verification.json) passed before launch. The independent one-time Windows task is `AI-Inference-Fresh-20261114-150236`. Its [startup snapshot](../launch-20261114-150236/startup.json) records the command and confirmed progress. Live state is in [workflow.json](workflow.json) and [preparation manifest](preparation-new/manifest.json).

At 16:31 Berlin on 14 November, target 1 passed collection, scaling qualification and cleanup. All 457 started requests completed: 450 succeeded and 7 timed out. Successful peak p95 was 26.390 seconds, so the response targets failed. There were no dropped or unfinished requests. Target 2 had started preparation; the six comparison cells had not started.

I keep the [old four accepted cells and failures](../comparison-20261113-192512/README.md) separate. Request duration now uses a monotonic timer. The one-second clock bound and ten-second source-age limit remain strict. The physical clock jump remains unresolved; a new stop is still possible. No final comparison is available yet.

# Fixed replica preparation

Date: 2026-10-20. Scope: prepare and verify three fixed copies after the completed one-copy pilot. This is a preliminary check, not the main comparison or an agreed response-time target.

## Work

1. Reuse the pilot launcher, observer, reconciliation and analysis for fixed one or three replicas. Keep the default one-replica path and old evidence compatible.
2. Warm each selected pod through the Kubernetes pod API proxy. Save its identity, Ready transition and successful generation times. Check the Service endpoints before load.
3. Save each pod's Ollama access log after load. Count completed generation requests in the measured window and check them against client counts. This proves distribution at pod level, not an individual client-to-pod mapping.
4. Verify negative cases offline before any measured cluster load. Start the existing cluster, confirm resources and image, then scale to three without HPA.
5. Run a short distribution check first. If valid, save one five-minute peak check at 8 requests/10 seconds with the existing request settings and no newly invented latency target. Keep failures and explain limitations. No other test workload runs during measurement.

## Acceptance and verification

- [x] Old one-replica checks and historical evidence integrity pass.
- [x] Tests reject missing/restarted pods, incomplete warmup, wrong Service endpoints and absent/inconsistent access logs.
- [x] Analysis sums all selected containers without turning missing values into zero.
- [x] Live evidence records three ready, individually warmed pods and requests handled by all three, or records the exact blocker without claiming success.
- [x] Update status and execution instructions with verified outcomes. Keep protocol step 17 and main experiment unfinished; do not commit or push.

Verified outcome: [saved technical check](../../results/fixed-replicas/check-2026-10-20-series1/README.md). The final checks include the new negative cases, historical evidence verification and live Service/log reconciliation. Three copies remain deployed; the temporary tunnel is closed after measurement.

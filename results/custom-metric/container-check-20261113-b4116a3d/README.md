# Custom-metric container check

I completed this functional check on 13 November 2026. `result.json` records a passed result with no errors; Docker logs, final metrics and backend request IDs are retained here. `inputs/` and `source-sha256.json` preserve the source used for the accepted check.

I verified Envoy 1.35.0 configuration, Prometheus 3.5.0 configuration and ten positive/negative query cases. Three held requests produced a 0 -> 3 -> 2 -> 0 gauge sequence. HTTP 503, client timeout and cancellation cleared the gateway count. Admin health requests were excluded, each request reached the backend once over a separate connection, all six request IDs matched access records, and the gauge returned to zero after restart.

The timeout check confirmed the metric's scope: a disconnected client disappears from the gateway count while backend work may continue. This is client-facing concurrency, not Ollama's internal queue or a drain guarantee.

Earlier failed attempts remain in adjacent directories: `container-check-20261113-bc8b3044` failed to connect to the IPv4 host fixture through Docker's dual-stack host name; `container-check-20261113-f0c5d707` read access logs before their asynchronous flush; `container-check-20261113-187339ae` reused an ephemeral admin port after Docker reassigned it on restart. I fixed those three fixture issues without changing the deployment renderer: IPv4-only lookup for this host fixture, bounded access-record reconciliation, and a refreshed admin address after restart.

This check used disposable Docker containers and a controlled HTTP backend. It did not deploy Prometheus Adapter, test the installed custom-metrics API, run model inference load, or start the HPA comparison. Created test containers were removed; the existing ai-lab cluster was retained.

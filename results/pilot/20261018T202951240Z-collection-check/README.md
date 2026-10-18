# Integrated collection check: 2026-10-18

This is a one-minute low-load verification of the collection path, not a capacity pilot or an autoscaling comparison. The existing `ai-lab` cluster was started with Docker and its Ollama Service was exposed through a temporary Minikube tunnel. No deployment/resource settings were changed. The tunnel address is specific to this session.

## Procedure and result

- Fixed one replica, no targeting HPA; 60 seconds of idle observation, a separate successful generation for warmup, 60 seconds at 2 requests per 10 seconds, then 10 seconds of post-load observation.
- Observer interval: 5 seconds. Measured scenario: 20:31:01.884Z to 20:32:01.884Z. Full orchestration and source identities are in [metadata.json](metadata.json).
- 12 started and 12 completed requests, all successful; no failed, unfinished or dropped requests. All measured responses reported 56 output tokens. Warmup is excluded.
- 29 cluster observations, no collection errors; maximum collection-start gap 5.026 seconds. One container identity throughout. CPU rates were available in 15 container observations; repeated underlying source timestamps legitimately leave other rate values missing.
- Successful response mean 2263 ms, p95 2643.95 ms. Peak observed container working-set memory: 602329088 bytes. These are observations of this small check, not capacity or savings claims.
- Launcher, k6 and collector returned 0; `collection_valid` is true, with no errors or warnings. See [collection-check.json](collection-check.json).

An independent read of the raw event file confirmed 12 distinct start/completion pairs, successful HTTP results, agreement with `summary.json`, zero sample errors and stable container identity. No parallel test suite ran during load; other Windows host activity was not audited.

## Scope and limitations

The stored input copies describe the executed implementation. Archive hashes and tool-version diagnostics are advisory; request reconciliation and observation coverage remain required. Initial/final snapshot copies are inspection aids; validation uses the full observation stream.

All work ran on the existing single computer. The check does not select low/peak pilot rates, freeze a latency target, verify three replicas/HPA, measure collection overhead near saturation, or establish server drain after timeouts. The result can be rechecked without modifying its raw files:

```powershell
python bench/pilot_records.py results/pilot/20261018T202951240Z-collection-check
```

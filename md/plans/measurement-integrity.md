# Measurement integrity and documentation consistency

Date: 2026-10-18. Status: complete. The results and unfinished work below describe that date; current state is in [STATUS.md](../STATUS.md).

## Objective

Address the seven reported risks without changing raw historical measurements or claiming new model/cluster validation. Preserve unrelated work and the existing research document structure.

## Steps and acceptance

1. Add a small pilot launcher that exclusively creates a new run directory before invoking k6. Replace the fixed output paths in guide step 8. Verify a valid new run and rejection of an existing directory without modifying its contents.
2. Validate optional Ollama token and load-duration fields independently. Preserve explicit valid zeros, omit unavailable/invalid observations and record metadata availability. Verify actual k6 output against a local stub server.
3. Reject unordered/duplicate observation collection times and gaps greater than twice the declared observer interval. Preserve repeated underlying kubelet source times as valid collection behavior. Add positive jitter and negative corruption tests. Recheck a copy of the real series and preserve historical source identity with matching frozen source snapshots.
4. Align the existing Research sections and local decisions on two states: server/API readiness and a model that has loaded and completed generation. Initial replicas are warmed before measurement; model loading in new replicas is part of the scaling reaction. Keep the existing readiness probe unchanged. Render and inspect the revised Word document and its PDF export.
5. Narrow the Notion PDP practical scope to text-generation inference. Keep agents in literature/future work only and preserve the learning goals and research-first sequence. Check the saved page.
6. Mark the C4 views as target architecture, with HPA and automated result analysis planned. Update the editable FigJam and the saved diagram PDF consistently; inspect the result.
7. Separate committing from pushing in the repository work rules.

## Verification

Run focused launcher, k6-response and overhead-analysis tests, plus the existing observer tests. Check documentation links, inspect Word/PDF and FigJam visuals, and check the saved Notion page. Recalculate saved overhead results only in a temporary copy using the historical source bytes. Compare hashes of raw results before/after; do not overwrite the original summaries, metadata, raw JSONL or analysis exports. Record any unavailable live cluster check separately from these offline/local checks.

## Progress

- [x] Safe pilot output directories and launch instructions.
- [x] Honest optional k6 measurements with coverage metrics.
- [x] Observation timestamp validation and historical-series recheck.
- [x] Research/implementation readiness alignment and visual QA.
- [x] Notion PDP inference-only practical scope.
- [x] Editable and exported C4 target-architecture labels.
- [x] Separate commit and push rules.
- [x] Final regression checks, raw-evidence hashes and status update.

## Verified outcome

31 focused tests passed. A real k6 process exercised missing/invalid/zero/positive telemetry against a local stub. A temporary-copy reanalysis matched saved results; 120 original evidence hashes stayed unchanged. Research v0.7 was exported with native Microsoft Word after the packaged renderer reported missing LibreOffice, then all 14 page PNGs were inspected. Both FigJam views and the saved annotated C4 PDF were visually inspected. I kept the PDP learning goals and research-first sequence.

Limits: no live Docker, Kubernetes or model performance test; HPA, first-generation correlation and general result analysis remain planned. `docs/PDP.pdf` remains a historical snapshot, clearly identified in the index; the current scope is in Notion. Portflow submission was not part of this work.

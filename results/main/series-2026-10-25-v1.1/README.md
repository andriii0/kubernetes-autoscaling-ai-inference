# Main series: protocol v1.1

Started preparation on 2026-10-25. Source commit: 70811d87e849581378bc89544c2bbf10d4ebcf16. Each attempt archives executable inputs and their hashes; metadata records source revision and dirty state. Local documentation changes and newly collected results may make that state dirty.

The agreed matrix, order and rules are owned by the [Notion protocol](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd). Follow the [execution checklist](../../../md/plans/scaling-experiment.md#manual-matrix-checklist). Pilot and preliminary runs do not replace main repetitions. A target miss is retained as an outcome; a collection problem stops progression for inspection.

The user confirmed that the game was closed before the first attempt. Docker/Minikube were resumed during preparation; no cluster was recreated. The initial Ollama container had restarted once before measurements. The application image ID matches the saved preliminary check. Normal desktop applications remain open on this shared computer.

## Execution interruption

After attempt 05 completed normally, Codex usage limits paused further agent work. The student later requested continuation. The cluster, tunnel, model identity and absence of the game/project generators were rechecked before attempt 06. No completed run is repeated and no settings changed. Exact observed endpoints are recorded in interruptions.jsonl.

## Student-requested pause after attempt 10

The student requested completion and review of the active run, then no next run. Ten of eighteen planned cells have reviewed full-duration/full-load records. Attempt 11 (repetition 2, autoscaling/steady) has not started. Resume only after a new student instruction and fresh runtime checks. The [checkpoint](pause-after-attempt-10.json) records the saved counts, last assessment, source preservation and current state.

At the checkpoint, three copies remain Ready without HPA. No scale change or restart was applied after the measured fixed-three run. Main load and observer processes have finished; the Service tunnel remains open. Main results and these documentation updates are local and uncommitted; implementation repair 70811d8 was already pushed.

Attempt 10 retained the existing +1-ms boundary warning; original events/counts are unchanged. One copy has 299.798 of 300 seconds CPU coverage, so complete application CPU is unavailable. Per-instance estimates and coverage remain in attempt-10-analysis/primary-resources.json. This resource limitation does not erase the valid client result.

## Attempt log

| Actual / planned order | Mode / profile / repeat | Data / verdict | Successful p95 (ms) | Completed / failed / unfinished / dropped | Application CPU estimate (core-s) | Evidence |
|---|---|---|---:|---|---:|---|
| 1 / 1 | fixed-1 / steady / 1 | valid / pass | 1094.3 | 240 / 0 / 0 / 0 | 502.039 | [attempt-01-fixed-1-steady](attempt-01-fixed-1-steady/assessment.json) |
| 2 / 2 | fixed-3 / steady / 1 | valid / pass | 1197.0 | 240 / 0 / 0 / 0 | 498.302 | [attempt-02-fixed-3-steady](attempt-02-fixed-3-steady/assessment.json) |
| 3 / 3 | autoscaling / steady / 1 | valid / pass | 1445.0 | 241 / 0 / 0 / 0 | unavailable | [attempt-03-autoscaling-steady](attempt-03-autoscaling-steady/assessment.json) |
| 4 / 4 | fixed-1 / burst / 1 | valid / pass | 1299.1499999999999 | 336 / 0 / 0 / 0 | 769.398 | [attempt-04-fixed-1-burst](attempt-04-fixed-1-burst/assessment.json) |
| 5 / 5 | fixed-3 / burst / 1 | valid / pass | 1522.1 | 336 / 0 / 0 / 0 | 824.855 | [attempt-05-fixed-3-burst](attempt-05-fixed-3-burst/assessment.json) |
| 6 / 6 | autoscaling / burst / 1 | valid / pass | 3216.899999999999 | 336 / 0 / 0 / 0 | unavailable | [attempt-06-autoscaling-burst](attempt-06-autoscaling-burst/assessment.json) |
| 7 / 7 | fixed-3 / burst / 2 | valid / pass | 2197.0 | 336 / 0 / 0 / 0 | 989.779 | [attempt-07-fixed-3-burst](attempt-07-fixed-3-burst/assessment.json) |
| 8 / 8 | autoscaling / burst / 2 | valid / pass | 2706.7999999999975 | 336 / 0 / 0 / 0 | unavailable | [attempt-08-autoscaling-burst](attempt-08-autoscaling-burst/assessment.json) |
| 9 / 9 | fixed-1 / burst / 2 | valid / pass | 1870.6 | 337 / 0 / 0 / 0 | 855.292 | [attempt-09-fixed-1-burst](attempt-09-fixed-1-burst/assessment.json) |
| 10 / 10 | fixed-3 / steady / 2 | valid / pass | 2202.0 | 241 / 0 / 0 / 0 | unavailable | [attempt-10-fixed-3-steady](attempt-10-fixed-3-steady/assessment.json) |

10/18 planned cells have reviewed full-load, full-duration data. A request-target verdict does not establish complete resource coverage or an autoscaling advantage.

CPU is an estimate for the common scheduled window. Memory is the observed per-instance peak with sample coverage; peaks are not summed. Full resource details are in each attempt analysis folder. Client outcomes and server drain remain separate; normal server drain is not independently verified.

The initial fixed-1 assessment retains the container termination from cluster resume before the series. Its restart count stayed stable during the run; this is pre-run context rather than a new measured restart.

The first fixed-1/steady p95 is lower than the historical pilot peak p95. Different dates and host conditions prevent attributing that difference; do not revise the frozen rates or targets after this result. Comparative conclusions require the agreed main repetitions.

attempt-03-autoscaling-steady: the warning was inspected. Request starts range from 2.0 to 300001.0 ms against a 300000.0-ms scheduled profile. The existing 1-ms protocol tolerance applies; original events/counts and the warning are retained.

attempt-03-autoscaling-steady: complete application CPU is unavailable because at least one instance lacks full active-window coverage. Retain per-instance estimates/coverage; do not add them as a complete application total.

attempt-03-autoscaling-steady: observed growth=True, automatic reduction=False in the retained load/post-load observations. Read scaling.json separately from the later explicit restoration action.

attempt-06-autoscaling-burst: complete application CPU is unavailable because at least one instance lacks full active-window coverage. Retain per-instance estimates/coverage; do not add them as a complete application total.

attempt-06-autoscaling-burst: observed growth=True, automatic reduction=True in the retained load/post-load observations. Read scaling.json separately from the later explicit restoration action.

attempt-08-autoscaling-burst: complete application CPU is unavailable because at least one instance lacks full active-window coverage. Retain per-instance estimates/coverage; do not add them as a complete application total.

attempt-08-autoscaling-burst: observed growth=True, automatic reduction=True in the retained load/post-load observations. Read scaling.json separately from the later explicit restoration action.

attempt-10-fixed-3-steady: the warning was inspected. Request starts range from 1.0 to 300001.0 ms against a 300000.0-ms scheduled profile. The existing 1-ms protocol tolerance applies; original events/counts and the warning are retained.

attempt-10-fixed-3-steady: complete application CPU is unavailable because at least one instance lacks full active-window coverage. Retain per-instance estimates/coverage; do not add them as a complete application total.

# Main series: protocol v1.1

I completed all 18 runs on 2026-10-26. The [final analysis](analysis-main-2026-10-26/README.md) contains the full results, tables and plots. The pause record and attempt table below describe the earlier 10/18 checkpoint.

I started preparation on 2026-10-25 with source commit 70811d87e849581378bc89544c2bbf10d4ebcf16. Each attempt archives its executable inputs and hashes; metadata records the revision and dirty state.

The [Notion protocol](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) defines the matrix, order and rules. The [execution checklist](../../../md/plans/scaling-experiment.md#manual-matrix-checklist) describes the procedure. Pilot and preliminary runs do not replace main repetitions. A target miss is retained as an outcome; a collection problem stops progression for inspection.

The game was closed before the first attempt. Docker/Minikube were resumed during preparation; no cluster was recreated. The initial Ollama container had restarted once before measurements. The application image ID matched the saved preliminary check. Normal desktop applications remained open on this shared computer.

## Execution interruption

I paused after attempt 05 completed. Before continuing with attempt 06, I rechecked the cluster, tunnel and model identity, and confirmed that the game and project generators were absent. I did not repeat completed runs or change settings. Exact observed endpoints are recorded in interruptions.jsonl.

<a id="student-requested-pause-after-attempt-10"></a>

## Historical checkpoint: pause after attempt 10

I finished and reviewed attempt 10, then paused before attempt 11 (repetition 2, autoscaling/steady). At this checkpoint, ten of eighteen planned cells had reviewed full-duration/full-load records. I needed fresh runtime checks before continuing. The [checkpoint](pause-after-attempt-10.json) records the saved counts, last assessment, source preservation and runtime state.

At that checkpoint, three copies remained Ready without HPA. No scale change or restart was applied after the measured fixed-three run. The load and observer processes had finished, and the Service tunnel remained open. The first ten results had not yet been committed at the time of the pause. They were subsequently published with the completed series.

Attempt 10 retained the existing +1-ms boundary warning; original events/counts are unchanged. One copy has 299.798 of 300 seconds CPU coverage, so complete application CPU is unavailable. Per-instance estimates and coverage remain in attempt-10-analysis/primary-resources.json. This resource limitation does not erase the valid client result.

## Attempt log at the 10/18 checkpoint

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

At this checkpoint, 10/18 planned cells had reviewed full-load, full-duration data. The remaining eight were completed later; see the [final analysis](analysis-main-2026-10-26/README.md). A request-target verdict does not establish complete resource coverage or an autoscaling advantage.

CPU is an estimate for the common scheduled window. Memory is the observed per-instance peak with sample coverage; peaks are not summed. Full resource details are in each attempt analysis folder. Client outcomes and server drain remain separate; normal server drain is not independently verified.

The initial fixed-1 assessment retains the container termination from cluster resume before the series. Its restart count stayed stable during the run; this is pre-run context rather than a new measured restart.

The first fixed-1/steady p95 was lower than the historical pilot peak p95. Different dates and host conditions prevent attributing that difference. I kept the frozen rates and targets; the completed repetitions are compared in the final analysis.

attempt-03-autoscaling-steady: the warning was inspected. Request starts range from 2.0 to 300001.0 ms against a 300000.0-ms scheduled profile. The existing 1-ms protocol tolerance applies; original events/counts and the warning are retained.

attempt-03-autoscaling-steady: complete application CPU is unavailable because at least one instance lacks full active-window coverage. Retain per-instance estimates/coverage; do not add them as a complete application total.

attempt-03-autoscaling-steady: observed growth=True, automatic reduction=False in the retained load/post-load observations. Read scaling.json separately from the later explicit restoration action.

attempt-06-autoscaling-burst: complete application CPU is unavailable because at least one instance lacks full active-window coverage. Retain per-instance estimates/coverage; do not add them as a complete application total.

attempt-06-autoscaling-burst: observed growth=True, automatic reduction=True in the retained load/post-load observations. Read scaling.json separately from the later explicit restoration action.

attempt-08-autoscaling-burst: complete application CPU is unavailable because at least one instance lacks full active-window coverage. Retain per-instance estimates/coverage; do not add them as a complete application total.

attempt-08-autoscaling-burst: observed growth=True, automatic reduction=True in the retained load/post-load observations. Read scaling.json separately from the later explicit restoration action.

attempt-10-fixed-3-steady: the warning was inspected. Request starts range from 1.0 to 300001.0 ms against a 300000.0-ms scheduled profile. The existing 1-ms protocol tolerance applies; original events/counts and the warning are retained.

attempt-10-fixed-3-steady: complete application CPU is unavailable because at least one instance lacks full active-window coverage. Retain per-instance estimates/coverage; do not add them as a complete application total.

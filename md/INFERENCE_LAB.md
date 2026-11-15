# Inference Lab

## Purpose

I built Inference Lab as a local web interface for my inference experiments. It brings experiment controls and saved results into one browser window. I use it on the same Windows computer as the project.

The interface has two tabs: **Runs** and **Results**. It uses the existing experiment scripts and saved evidence format.

## Runs

The Runs tab contains two cards:

- **Pilot run** opens a settings dialog. I can choose fixed one replica, fixed three replicas or HPA, select a traffic profile, and set request rates and the p95 target. Steady runs have an editable duration. Burst duration comes from the workload stages. Prepared HPA pilots use burst traffic.
- **Main series · v1.1** resumes pending runs in an existing peak-8 main series. When the series is complete, **View results** opens its overview. This action does not create a new comparison or resume the separate peak-12 follow-up.

Dry run validates a command without sending load. During a launch, the interface shows the phase, run number and command output. I allow one UI job at a time and check for other experiment processes before a live start.

## Results

The Results tab uses three columns: result groups, saved series or runs, and a preview. The groups include **Series**, **Custom metrics**, **Pilots**, and **Checks & diagnostics**.

Selecting a series opens its overview on the right. I can see completion, target attainment and individual attempts. Completion and meeting the performance target are separate outcomes. CPU and active-request HPA have distinct policy labels. Custom comparison overviews show each policy’s accepted runs, peak on-time successes, errors, target passes and run-level p95 range from that manifest; earlier cycles are not pooled. Preserved failed attempts and recovered evidence remain visible as distinct entries.

A run preview shows its mode, traffic profile, request rate, successful-response p95, request counts and collection status. Missing measurements remain an em dash. The p95 label identifies its measurement window, so peak latency is not confused with whole-run latency. Errors and timeouts are reported separately from successful-response latency. Preparation previews use the saved peak assessment. An unfinished record remains unverified unless it contains a recorded failure; its initial collection flag alone is not a final data-failure verdict.

Saved plots open at full size, and **Open folder** opens the evidence directory. Browsing reads existing files; it does not rerun the experiment or regenerate analysis.

## Notes

I can add notes to a run or series to explain problems, recovery work or observations. Notes are saved in that result's `notes.md`, separately from measurements. Drafts survive navigation inside the page. If the file changes in another editor, the interface reports a conflict instead of silently replacing it.

The Notes panel also shows the nearest saved parent note as read-only context, with its source folder. This keeps the stopped cycle's explanation visible inside preparation previews even when the parent has no manifest. Editing the child note does not copy or overwrite that parent note. Retired attempt notes explicitly identify their historical scope.

## Platform choice

I initially planned Inference Lab as a small, single-page UI stand for the experiment. For that scope, a Python HTTP server with plain HTML, CSS and JavaScript was a straightforward way to connect a browser screen to my existing scripts and result files.

I later expanded the screen slightly: separate Runs and Results tabs, a pilot settings dialog and editable notes. It still follows the original local UI design. I kept this structure because it was simple to build and extend for that purpose. This is a choice based on the initial scope, not a claim that a custom HTTP server is generally simpler or better than FastAPI.

## Runtime and source

I start the application from the project root:

```powershell
.\.venv\Scripts\python.exe -B -m lab
```

The browser opens at `http://127.0.0.1:8765`. Saved-result browsing does not require a running cluster. Live experiments use the existing cluster setup and launcher preparation checks.

- `lab/server.py`: local HTTP routes and application startup.
- `lab/static/`: browser interface, styling and interactions.
- `lab/results.py`: saved-result catalog and previews.
- `lab/jobs.py`: launch coordination, process checks and output.
- `lab/launch.py`: configurable pilot adapter.
- `lab/notes.py`: note storage and edit-conflict checks.

See the [setup guide](GETTING_STARTED.md#inference-lab) for usage, [architecture](ARCHITECTURE.md#local-ui-flow) for runtime interactions, and [UI plan](plans/inference-lab.md) for verification history.

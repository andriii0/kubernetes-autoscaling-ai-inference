# Completed custom comparison review fixes

## Objective

I corrected the remaining result-browser and experiment-registry defects, then aligned the project documents with the completed 14 November CPU/request comparison. I kept the earlier evidence and the two previous fixes intact.

## Steps

1. Show CPU and active-request policies and their saved comparison outcomes in Inference Lab. Treat unfinished metadata as incomplete rather than prematurely failed.
2. Make registry persistence withstand interrupted writes while preserving exclusion of live experiments and registered children. Do not discard uncertain ownership.
3. Record the six accepted results, preparation, clock environment and restoration in the series report and current Markdown/Notes.
4. Update the existing Notion findings, logs, decisions and outline, and Research Word/PDF in place. Keep main 18, peak-12 nine, and custom six separate.
5. Run focused Python/browser checks, saved-result replay, evidence hashes, local links, and Word/PDF content and visual verification.

## Acceptance

- Each policy is identifiable; the comparison shows saved peak service outcomes and missing values explicitly.
- An unfinished run does not receive a final data-failure verdict only because collection_valid starts false; actual recorded failures remain visible.
- Interrupted registry persistence cannot truncate the last committed ownership record. Corrupt ownership is never silently treated as an empty registry.
- Current documents describe six accepted cells and 0/3 CPU versus 1/3 request-policy target passes, with the predeclared paired improvement and resource limits.
- Raw measurements and historical assessments remain byte-identical. This work uses saved results.

## Progress

Completed on 15 November 2026.

- Inference Lab separates CPU/request policy names and shows accepted per-policy peak counts, run-level p95 ranges and target attainment. Pending collection remains unverified. Preparation reads its saved peak assessment; continuation compares the saved JSON representation.
- Registry ownership uses a stable OS mutex and atomic JSON replacement. Twelve lock tests cover process exclusion, surviving children, interrupted saves, idle migration and malformed/missing state. A read-only code review found no blocking issue. Arbitrary corrupt ownership still requires verified-idle repair; I did not reset the live registry.
- I updated current Markdown, visible series Notes, the separate custom log, general Notion log, Findings, Technology Decisions and research outline. Research v0.12 preserves the original 18+9 results and adds the separate six-run extension and limits.
- All 91 focused Python tests and eight Edge browser tests passed, along with JavaScript syntax checks.
- Both preparations and all six comparison rows replayed against archived sources, and the paired summary matched. All 629 non-Markdown files in the new series retained their hashes. All 120 saved result previews loaded. The displayed real-series policy table matched 173/1,080 versus 903/1,080 timely successes, 194 versus zero errors and 0/3 versus 1/3 target passes.
- The historical verifier preserved 120 evidence hashes and reproduced the saved aggregates. I checked local links and anchors, excluding code blocks from link parsing.
- I checked that the Research Word/PDF text matched across 297 paragraphs/cells and inspected all 15 PDF pages. The policy table displayed in Edge without overlap or clipping.

I did not run a new experiment or submit documents to Portflow. The clock mitigation remains scoped to the completed cycle. External bibliography and FigJam boards were not revalidated in this fix pass.

## Notes and documentation follow-up

Completed on 15 November: I exposed the nearest nonempty parent Notes as read-only context in run and preparation previews, without copying it into child notes. Empty local notes now explicitly say that parent context is shown above. I marked retired attempts and reliability-plan snapshots as historical, put the final afternoon stop first, and corrected setup-guide group names and the resume button.

Both preparations and all six comparison runs already had PNG/SVG plots. I added separate preparation and comparison overviews, with `bench/plot_custom_overview.py` for regeneration. Series previews discover these plots and display their full height; existing per-run previews remain available. The comparison chart keeps timely successes and errors beside successful peak p95.

All 40 lab Python tests and nine Edge browser tests passed. JavaScript syntax passed. I verified saved detail data and plot paths for all eight completed runs and the two overviews, and checked the real UI's parent context and overview images. No raw JSON/JSONL, manifest, assessment or existing per-run plot was rewritten; only the new overview images were regenerated.

I reread all ten project-related Notion pages and the separate SUE questions page. The historical preparation numbers were correct for 13 November, but their heading lacked a date; I clarified that scope and the final evening status. I updated the PDP with the separate extension, clarified the main methodology's scope and custom-preparation exception, and recorded the Notes/plot corrections in the custom log. Other final-result pages already agreed with the six-run report. This is a full text review of the fetched pages, not a fresh external-bibliography or embedded-file audit.

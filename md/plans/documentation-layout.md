# Documentation layout and first GitHub snapshot

Date: 2026-10-16. I organized the project Markdown and saved the first GitHub snapshot.

## Steps

1. Keep root `AGENTS.md` and `README.md` as instructions and entry point.
2. Move the roadmap, guide, observer documentation and research under `md/`; retain status and task plans there. Add architecture and decisions based on inspected implementation/evidence.
3. Include the recorded teacher feedback under `md/meeting/`. Replace the document-authoring workspace's duplicate plan/notes with a pointer to the canonical project documentation after verifying copies.
4. Update relative links and planned documentation paths, preserving original result evidence and unfinished milestones.
5. Initialize the code directory as a Git repository. Exclude downloaded model weights, caches and local environment/credential files.
6. Run existing focused tests, check Markdown links, inspect staged files and secret/size candidates, create a private GitHub repository and push an initial commit.

## Acceptance

- Core files exist under `md/`; root instructions explain the new reading/planning workflow.
- Local Markdown links resolve, and setup commands still run from the repository root.
- Existing observer and result-analyzer tests pass; runtime code and original measurement files are unchanged.
- Git excludes model weights, caches and credentials. The remote commit equals the local commit and repository visibility is private.
- Word artifacts remain in the authoring workspace; Git publication does not replace required Fontys Portflow submission.

## Execution notes

The canonical tree is in place, including architecture, decisions, guides, research, plans and teacher feedback. The authoring workspace now points to this tree instead of keeping duplicate plans/meeting notes. All 55 local links/anchors and 21 focused tests passed. One timing-dependent JSONL test expectation was fixed; runtime source and measured data were preserved.

The private repository `andriii0/kubernetes-autoscaling-ai-inference` was created for the initial `main` snapshot. Ignored paths exclude downloaded weights and local credentials. Source LF settings and unmodified result-file storage are declared in `.gitattributes`. Final delivery verification compares local HEAD with remote `main` after push.

## Fontys document collection: 2026-10-18

Objective: collect seven files from Downloads in the project `docs/` folder and clarify document ownership without changing the research contents or reorganizing unrelated files.

Steps: check existing destinations; copy the files without removing originals; verify SHA-256 hashes; add a document index; update entry points and the documentation responsibility notes.

Acceptance: all seven copies match their sources; existing files are preserved; the index separates personal evidence, group context and course reference; local index links resolve; research structure and content are unchanged. Portflow submission remains a separate task.

I checked that all seven copies matched their source SHA-256 hashes and that the document-index links resolved. The research file was unchanged. The index now identifies the editing sources; other proposed layout changes were not implemented.

## Technology research deduplication: 2026-10-18

Objective: maintain detailed technology choices in Notion and concise implementation decisions locally, without changing the Word/PDF research or original runtime evidence.

Steps: compare the local technology research with Notion; update source ownership on the Notion page; verify it by fetching again; replace incoming local references; shorten duplicated guide comparisons; remove only the redundant research file.

Acceptance: all six Notion choice sections and the local research source URLs are retained; no active links reference removed research; local files/anchors resolve; runnable guide code blocks, runtime sources, Word/PDF files and result evidence remain byte-identical.

I retained all six detailed choice sections and source URLs in Notion, removed the local duplicate and checked the updated links. Runnable guide blocks, runtime sources, saved results and Word/PDF files were unchanged.

## Documentation cleanup: 2026-10-18

Objective: keep current state concise, link to measured results instead of duplicating their numbers, clarify document responsibilities and exclude temporary materials from ordinary context searches.

Steps: shorten status and repeated result summaries; define how the active plan relates to the general guide; exclude root `tmp/` from ripgrep in both project and authoring workspaces. Preserve temporary files, raw evidence, implementation and milestone completion.

Acceptance: retained evidence links resolve; status names the active plan, unfinished work and verification limits; measured overhead numbers have one maintained report; normal `rg` file discovery omits temporary material while explicit inspection remains possible. Runtime code remains unchanged.

Both workspaces now exclude root `/tmp/` from ordinary ripgrep searches. Explicit `rg --no-ignore --files tmp` inspection still works. All 159 protected source, evidence and collected document files retained their hashes. Milestone completion, runtime behavior and raw measurements were unchanged.

## English getting started guide: 2026-10-18

Objective: use simple English and keep every guide topic, with links to the document that describes each procedure or decision.

Steps: rename the guide to `md/GETTING_STARTED.md`; keep setup, short checks, troubleshooting and restart instructions; use the existing pilot plan for pilot rules; move future scaling/run/analysis details into `md/plans/scaling-experiment.md` with explicit prerequisites and planned status. Link existing source files instead of copying their JavaScript, Dockerfile or Deployment contents. Update incoming references and status without changing milestones or runtime files.

Acceptance: all original numbered topics remain available; the guide has no Russian prose; each advanced topic links to its owner; HPA and general analysis remain planned; no procedure links back to a guide section that is only a pointer. Local links and PowerShell syntax pass; source/evidence/document hashes remain unchanged. These checks do not execute setup or validate the live environment.

I kept guide topics 0-14, troubleshooting and restart instructions, and checked the English prose, local links and PowerShell syntax without executing setup. Pinned-image extraction worked against the existing Dockerfile. The HPA proposal remained in its planned source; I could not check it with a separate YAML parser because no YAML library was available. All 159 protected source, evidence and collected document files retained their hashes. HPA and the frozen-protocol file were still absent at this checkpoint; milestone completion was unchanged.

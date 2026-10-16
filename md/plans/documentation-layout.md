# Documentation layout and first GitHub snapshot

Date: 2026-10-16. Requested scope: organize project Markdown and push the current project to GitHub.

## Steps

1. Keep root `AGENTS.md` and `README.md` as instructions and entry point.
2. Move the roadmap, guide, observer documentation and research under `md/`; retain status and task plans there. Add architecture and decisions based on inspected implementation/evidence.
3. Include the recorded teacher feedback under `md/meeting/`. Replace the document-authoring workspace's duplicate plan/notes with a pointer to the canonical project documentation after verifying copies.
4. Update relative links and planned documentation paths, preserving original result evidence and unfinished milestones.
5. Initialize the code directory as a Git repository. Exclude downloaded model weights, caches and local environment/credential files.
6. Run existing focused tests, check Markdown links, inspect staged files and secret/size candidates, create a private GitHub repository and push an initial commit.

## Acceptance

- Requested core files exist under `md/`; root instructions explain the new reading/planning workflow.
- Local Markdown links resolve, and setup commands still run from the repository root.
- Existing observer and result-analyzer tests pass; runtime code and original measurement files are unchanged.
- Git excludes model weights, caches and credentials. The remote commit equals the local commit and repository visibility is private.
- Word artifacts remain in the authoring workspace; Git publication does not replace required Fontys Portflow submission.

## Execution notes

The canonical tree is in place, including architecture, decisions, guides, research, plans and teacher feedback. The authoring workspace now points to this tree instead of keeping duplicate plans/meeting notes. All 55 local links/anchors and 21 focused tests passed. One timing-dependent JSONL test expectation was fixed; runtime source and measured data were preserved.

The private repository `andriii0/kubernetes-autoscaling-ai-inference` was created for the initial `main` snapshot. Ignored paths exclude downloaded weights and local credentials. Source LF settings and unmodified result-file storage are declared in `.gitattributes`. Final delivery verification compares local HEAD with remote `main` after push.

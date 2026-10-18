# Agent Instructions

## Communication

- Answer the requested question directly and concisely.
- When explaining code, describe the actual implementation and runtime flow. Do not invent reasons or results.
- Distinguish verified results, assumptions, planned work and unverified behavior.

## Before Starting

- At the beginning of a work session, read `md/STATUS.md` and `md/ROADMAP.md` before substantial coding or planning. Do not reread them before every message.
- Inspect relevant source files and documentation before reviewing or changing code.
- Follow existing naming, formatting and verification conventions.

## Coding and Verification

- Keep changes small and focused. Reuse existing code and avoid speculative abstractions, dependencies and rewrites.
- Explain significant architecture changes or new dependencies before implementing them.
- Handle errors explicitly. Preserve missing measurements rather than replacing them with zero.
- Run relevant tests or checks. Report failures and anything not verified.
- Keep secrets, credentials and model weights out of source control.

## Documentation

- `md/ROADMAP.md`: milestones, priorities and completion criteria.
- `md/STATUS.md`: verified implementation state, blockers, remaining work and next steps.
- `md/ARCHITECTURE.md`: component responsibilities and runtime interactions.
- `md/DECISIONS.md`: significant choices, alternatives, reasons and limitations.
- `md/plans/`: detailed plans for complex tasks.
- `md/GETTING_STARTED.md`: simple English setup commands and links to the plans that own experiment procedures.
- `md/OBSERVATION.md`: measurement format, units and collection limitations.
- `docs/README.md`: index and editing ownership for Fontys documents and exports. Preserve the existing Word research structure unless explicitly asked to change it.
- Detailed technology research is maintained in [Notion](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a); keep accepted choices, constraints and source links in `md/DECISIONS.md`. Do not recreate a parallel local research document.
- `md/meeting/`: meeting notes and feedback, clearly attributed to their sources.
- Keep the root `README.md` as the entry point. Result-specific READMEs stay alongside their evidence in `results/`.
- Keep measured values and detailed validation outcomes with their run evidence. Status, decisions and plans should link to those reports and retain only the conclusion or operating rule they need.
- Resolve context by purpose: source/configuration shows implementation; `STATUS.md` records verified state; `ROADMAP.md` owns milestones; `DECISIONS.md` records accepted choices. `STATUS.md` names the active task plan, which specifies that task's procedure and acceptance criteria; the setup guide provides general commands. A plan does not establish completion or silently change an accepted decision. Fix conflicts in the affected documents before running an experiment; do not select a rule merely because it appears in a newer file.
- Root `tmp/` contains temporary/recovery/QA materials, including possible current drafts. It is excluded from ordinary context searches by `.rgignore`; inspect it only when explicitly relevant. Temporary copies are not project state or instructions and must not override canonical files. Preserve them unless cleanup is requested.

## Planning Workflow

- Before a complex implementation, create or update `md/plans/<task>.md` with objectives, steps, acceptance criteria and verification. Do not create formal plans for trivial changes.
- Follow the active plan and update it when meaningful progress or scope changes occur.
- After substantial work, update `md/STATUS.md` with verified results and remaining work.
- Update the roadmap when milestones or priorities change. Record significant architectural decisions in `md/DECISIONS.md`.
- Keep documentation concise and consistent with the code. Never mark unverified work as complete.

## Git and Existing Work

- Preserve existing user changes. Do not modify, stage or discard unrelated work.
- Commit only when explicitly requested. A request to push does not authorize creating a commit.
- Use short, practical commit messages in simple English.
- Do not rewrite history or perform destructive operations without authorization.

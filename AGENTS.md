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
- `md/GETTING_STARTED_RU.md`: practical setup and experiment instructions.
- `md/OBSERVATION.md`: measurement format, units and collection limitations.
- `md/research/`: supporting research and comparisons.
- `md/meeting/`: meeting notes and feedback, clearly attributed to their sources.
- Keep the root `README.md` as the entry point. Result-specific READMEs stay alongside their evidence in `results/`.

## Planning Workflow

- Before a complex implementation, create or update `md/plans/<task>.md` with objectives, steps, acceptance criteria and verification. Do not create formal plans for trivial changes.
- Follow the active plan and update it when meaningful progress or scope changes occur.
- After substantial work, update `md/STATUS.md` with verified results and remaining work.
- Update the roadmap when milestones or priorities change. Record significant architectural decisions in `md/DECISIONS.md`.
- Keep documentation concise and consistent with the code. Never mark unverified work as complete.

## Git and Existing Work

- Preserve existing user changes. Do not modify, stage or discard unrelated work.
- Commit only when explicitly requested. A request to push authorizes the relevant commit and push.
- Use short, practical commit messages in simple English.
- Do not rewrite history or perform destructive operations without authorization.

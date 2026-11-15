# C4 architecture model in Architect

## Objective

I will create a new persistent Architect project for this inference experiment, with C1 context, C2 containers, C3 components, and a C4 UML code view of the whole owned application. Architect is the authoring tool, not the system being modeled. Existing FigJam and Architect diagrams remain preserved.

## Steps

1. Start the existing Architect backend/frontend with the regular file-backed database; verify its local MCP tools.
2. Inspect current `lab`, `bench`, JavaScript/Go workload and Kubernetes configuration. Separate actual classes, functional modules and external runtimes.
3. Create four linked diagrams with named system/process/package boundaries, technologies, responsibilities and directed relationships. Cover CPU and active-request HPA paths.
4. Validate saved models, reread persisted identities/revisions, inspect rendered diagrams and open the project in the UI. Export portable snapshots and keep source-scope notes with the model.

## Acceptance

- C1-C3 use consistent drill-down scope; C4 is UML code structure, not a second infrastructure flow.
- UML includes every production module in `lab` and `bench`, the browser JavaScript, k6 script and Go timer, with real classes/functions and dependency semantics. Empty package markers, tests and historical archived executable copies are excluded explicitly.
- New diagrams persist in the regular Architect database, have checkpoints, validate without errors and can be exported. No experiment runs, application code changes, commits or publication are included.

## Progress

Completed on 15 November 2026. I started the existing Architect backend and frontend with its regular file-backed database and authored four new diagrams through the live HTTP MCP. C2 distinguishes the Lab HTTP server, benchmark CLI and offline analysis processes. C4 contains 54 elements and 66 relations after the later readability refinement, covering all 34 Python modules and 14 Python classes plus JavaScript, Go and runtime declarations.

All four saved models passed validation and were reread after writes. Source AST checks confirmed Python module/function/class/method coverage. I created checkpoints and exported native PNG/SVG and portable JSON snapshots to the [diagram index](../diagrams/architect/README.md). The browser loaded persisted views; C4 cards did not overlap. Native image export uses the installed Edge executable through a launch-time Architect setting. No application source, dependency, database schema or experiment state was changed.

## FigJam presentation follow-up

The user requested a new FigJam board matching the existing SUE AI Infra C4 board. I will preserve the verified model content, inspect that board's real styles, and create editable C1-C4 sections in a separate file. Acceptance: reference-derived colors and Inter typography, native editable nodes/connectors, all C4 modules/classes retained, readable text and no overlapping cards. I will reread counts/relationships and inspect rendered sections before linking the new board here.

Status on 15 November 2026: incomplete. I inspected the reference board's actual colors, Inter typography and connectors and created [a separate target board](https://www.figma.com/board/eWGVj6OOX3Jz70l5QHZQPV). The Figma MCP Starter tool-call limit was then reached before diagram content could be written. The target board is empty; no FigJam content or rendering validation is complete. The existing Architect diagrams and reference board remain unchanged. Per the user's instruction to stop if Figma MCP does not work, the transfer is stopped.

Follow-up completed on 15 November 2026: applied the requested C1/C3/C4 refinements in the persisted Architect project. C1 has three nodes and two relations; C3 reverses the saved-assessment relation; C4 is `Detailed code map` with 54 elements, 66 relations and seven groups, without external library cards and with selected architectural methods. Live validation, rereads, PNG/SVG rendering and portable snapshot refresh passed.

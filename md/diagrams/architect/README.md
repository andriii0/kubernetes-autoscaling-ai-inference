# C4 architecture in Architect

I made these four views from the implementation on 15 November 2026. They describe the AI inference experiment; I used Architect to draw them. They show the structure, not whether an experiment is currently running.

[Open the Architect project](http://localhost:5173/?project=bef694bf-c6ef-44e5-b591-7a67990d4079). The local Architect backend and frontend must be running. The diagrams are persisted in its regular file-backed database; the files below are portable copies of the verified revisions.

| View | Scope | Editable diagram | Portable model | Image |
|---|---|---|---|---|
| C1 | Researcher, experiment system and Kubernetes platform | [Open C1](http://localhost:5173/?project=bef694bf-c6ef-44e5-b591-7a67990d4079&diagram=a155ecbb-b1f2-425f-8649-541d2086f17b) | [JSON](c1.architect.json) | [SVG](c1.svg) / [PNG](c1.png) |
| C2 | Browser, Lab server, benchmark CLI, offline analysis, evidence, serving and metrics processes | [Open C2](http://localhost:5173/?project=bef694bf-c6ef-44e5-b591-7a67990d4079&diagram=3be9d52c-97d6-437a-a310-f2202dd169af) | [JSON](c2.architect.json) | [SVG](c2.svg) / [PNG](c2.png) |
| C3 | Components of the Python tools shown in C2, grouped by HTTP, CLI and offline-analysis responsibilities | [Open C3](http://localhost:5173/?project=bef694bf-c6ef-44e5-b591-7a67990d4079&diagram=d56e1114-e3c1-4391-a505-f91f5eb4e3ca) | [JSON](c3.architect.json) | [SVG](c3.svg) / [PNG](c3.png) |
| C4 | Detailed code map of the application as UML modules, classes and selected dependencies | [Open C4](http://localhost:5173/?project=bef694bf-c6ef-44e5-b591-7a67990d4079&diagram=b2f9ccf0-a924-43c1-89db-a15b02c58d9f) | [JSON](c4.architect.json) | [SVG](c4.svg) / [PNG](c4.png) |

C1 expands to C2; the Python processes in C2 expand to the grouped component view in C3. C4 maps those responsibilities to source code and also includes the browser and workload code. In C2, a container means a running application or data store, not necessarily a Docker container. The benchmark CLI represents successive processes using the same executable toolchain. Kubernetes infrastructure is distinguished from the experiment code in this repository. Both policies in the custom-metric comparison use the Envoy route; the main and peak-12 experiments use the direct Ollama Service route.

## UML scope and notation

C4 contains 54 elements and 66 relations in seven groups. It includes all 34 production Python modules and all 14 Python classes under `lab/` and `bench`, both JavaScript entry files, the Go timer module and its two structs. A configuration element identifies the Dockerfile, Kubernetes manifests, workload JSON and static HTML/CSS. Method rows are limited to architectural entry points and lifecycle operations; external library types are omitted.

Python functional modules have an explicit **Python module** stereotype; they are not claimed to be classes. Their rows list selected architectural functions. Python class cards list selected lifecycle methods and reference fields; unannotated types are not guessed. Browser rows include named functions, arrow-function helpers and central state. Anonymous callbacks and nested local functions remain implementation detail. The Go `now` closure is described on the timer/instance cards. Tests, the empty `lab/__init__.py`, archived copies of runners, third-party library internals and model weights are outside this code view.

Dashed arrows show dependencies; solid associations show module membership or object references. Hollow triangles distinguish inheritance and interface implementation. The Results-to-analysis relation is explicitly a **file contract**, not a Python import. Relations are selected architectural dependencies, not every import or call. Source paths on cards and the [source inventory](source-inventory.json) allow checking module and class coverage and source hashes.

C4 is a large zoomable diagram. Use the interactive canvas or SVG for detail; the whole-board PNG is an overview. The current Architect canvas has a minimum zoom, so a full UML board may require panning even after Fit View. The JSON preserves operations and their arguments even where the compact canvas card displays only method names.

## Verification and recovery

I validated the four diagrams, checked their source coverage and exported PNG and SVG copies at the saved revisions. I also checked that the views loaded in the browser and that the C4 cards did not overlap. [Verification metadata](verification.json) records IDs, revisions, counts and saved checkpoints.

Import an `*.architect.json` file through Architect's normal JSON import to make a new editable copy. Existing FigJam boards and the historical C4 PDF were preserved. These exports are not a Portflow submission.

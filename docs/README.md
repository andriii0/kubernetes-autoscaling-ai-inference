# Fontys documents

Collected on 2026-10-18 from my Downloads folder. These are saved documents, not confirmation of current Portflow submission. Original files were retained.

## Personal experiment

| Document | Role and editing source |
|---|---|
| [Research Word document](<PDP Research document.docx>) | Working research copy, version 0.8. It compares orchestration platforms and answers SQ4 using the completed local inference tests. Edit the existing sections. |
| [Research PDF](<PDP Research document.pdf>) | Version 0.8, exported from the Word copy. Re-export after later changes. |
| [PDP PDF](PDP.pdf) | Historical export with the earlier broader agent-workload scope; it is not the current scope statement. The [Notion PDP](https://app.notion.com/p/3e2c7c697bfd814d8509f00f3f7ae471) was reconciled on 18 October: practical tests cover inference only; agents remain literature/future work. Re-export from Notion before submitting an updated PDP PDF. |
| [C4 diagram PDF](<Kubernetes PE C4.pdf>) | Historical target-architecture export. Its annotation predates completed pilot analysis and the preliminary HPA check, and it has not been regenerated from the updated FigJam views. Preserve the PDF as a dated export; it is not the current editable diagram or live cluster evidence. |
| Editable C4 views | [C1](https://www.figma.com/board/KaoXEMPbKjCy1gOwdFdrUE?node-id=5-93) and [C2](https://www.figma.com/board/KaoXEMPbKjCy1gOwdFdrUE?node-id=5-127) describe the implemented local prototype after the 2026-10-28 update. [C3](https://www.figma.com/board/KaoXEMPbKjCy1gOwdFdrUE?node-id=30-56) expands the experiment runner. These views describe structure, not current runtime availability or proven HPA benefit. |
| [Personal FeedPulse PDF](FeedPulse.pdf) | Saved feedback export; later feedback may exist in FeedPulse. |

## Supporting context

| Document | Role |
|---|---|
| [Group FeedPulse PDF](<Group Feedpulse.pdf>) | SUE group-project context, kept separate from personal experiment results. |
| [AV-CSS course guide](AV-CSS-lesson-explainer.docx) | Course reference, not personal experiment evidence. Distinguish official course material from external advice; verify changed requirements against official sources. |

## Where other information lives

- [Project README](../README.md): entry point and project layout.
- [Status](../md/STATUS.md): verified progress and the next action.
- [Roadmap](../md/ROADMAP.md) and [task plans](../md/plans/): future work and completion criteria.
- [Technical decisions](../md/DECISIONS.md): concise local choices and constraints. [Technology Decisions in Notion](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a) is the maintained source for the detailed Qwen, Ollama, CPU, k6, HPA and Minikube rationale. Use the research document above for the full orchestration-platform comparison; do not maintain another copy of these decisions in local research files.
- [Main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd): agreed on 2026-10-21; owns numeric settings, targets, repeat order and outcome/data rules. The 18 main runs, comparative analysis and [Findings](https://app.notion.com/p/40fc7c697bfd81bbb00fcf67a8c3d00c) are saved. The [reproduction check](../results/reproduction/check-2026-11-06/README.md) passed on the same Windows host. See [current status](../md/STATUS.md) and the [complete analysis](../results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/README.md). The initial series README and pause checkpoint retain their earlier 10/18 snapshot.
- [Results](../results/): original run data and adjacent reports. Keep run READMEs beside their measurements; use their findings in the existing research evaluation sections when appropriate.

The initial file collection did not change research contents or exports. Technology-decision ownership was consolidated in Notion on 2026-10-18; Research v0.8 and its PDF include the completed SQ4 evaluation. Editable C1/C2/C3 now describe the implemented prototype; the older C4 PDF retains its historical target-architecture annotation. Local collection and GitHub storage do not replace required Fontys Portflow submission.

# Fontys documents

I keep the research document, PDF exports of my Notion pages and feedback here. The Notion exports below were created on 15 November 2026. I edit the research in Word and the other project documents in Notion, then export new PDFs after changes. Submission of the current evidence to Portflow still needs confirmation.

## Research document

| Document | Role and editing source |
|---|---|
| [Research Word document](<PDP Research document.docx>) | Working research copy, version 0.12, dated 15 November 2026. It compares orchestration platforms and answers SQ4 using the main series, controlled peak-12 follow-up and separate six-run CPU/request comparison. Edit the existing sections. |
| [Research PDF](<PDP Research document.pdf>) | Version 0.12, exported from the Word copy. Re-export after later changes. |

## Notion page exports

These PDFs are saved snapshots. The linked Notion pages remain their editing sources.

| PDF | Role and editing source |
|---|---|
| [Container Orchestration for AI Inference PDP](<Container Orchestration for AI Inference PDP.pdf>) | Research scope, learning goals, method and reflection, including the higher-load and custom-metric extensions. [Edit in Notion](https://app.notion.com/p/3e2c7c697bfd814d8509f00f3f7ae471). |
| [Technology Decisions](<AI Inference Autoscaling Technology Decisions.pdf>) | Reasons for choosing the model, server, CPU setup, load generator, HPA, Minikube and custom-metric infrastructure. [Edit in Notion](https://app.notion.com/p/3fdc7c697bfd81baaaa7f197548b7c5a). |
| [Pilot and Follow-up Results](<AI Inference Autoscaling Pilot and Follow-up Results.pdf>) | Pilot rate selection, preliminary scaling checks and the controlled peak-12 comparison. [Edit in Notion](https://app.notion.com/p/3fec7c697bfd81738d08d5527424af20). |
| [Experiment Methodology](<AI Inference Autoscaling Experiment Methodology.pdf>) | Frozen main v1.1 settings, preparation, targets and data-validity rules, with separate sections for the later experiments. [Edit in Notion](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd). |
| [Findings](<AI Inference Autoscaling Findings.pdf>) | Answers to the research questions, comparisons across the three experiment series, limitations and recommendations. [Edit in Notion](https://app.notion.com/p/40fc7c697bfd81bbb00fcf67a8c3d00c). |
| [Experiment Log](<AI Inference Autoscaling Experiment Log.pdf>) | Project history from setup and pilot through the main comparison, reproduction check and later extensions. [Edit in Notion](https://app.notion.com/p/40fc7c697bfd812c86b9fb9cad9ee986). |
| [Custom-Metric HPA Experiment Log](<AI Inference Custom-Metric HPA Experiment Log.pdf>) | Metric validation, preparation, interrupted attempts, clock investigation and the completed six-run CPU/request comparison. [Edit in Notion](https://app.notion.com/p/417c7c697bfd8049a916f48c59ff1e75). |
| [Custom-Metric HPA Research Outline](<AI Inference Custom-Metric HPA Research Outline.pdf>) | Extension question, metric and tool choices, target selection, scaling times and result limits. [Edit in Notion](https://app.notion.com/p/417c7c697bfd8048a688c8f2f23e978b). |
| [Feedbacks](Feedbacks.pdf) | Expert and peer comments on the architecture, experiments and conclusions. [Edit in Notion](https://app.notion.com/p/419c7c697bfd8032b30ef9495d9190b7). |

## Architecture

| Document | Role and editing source |
|---|---|
| Current editable C1-C4 views | [Architect project and exports](../md/diagrams/architect/README.md), created from current source on 15 November 2026. C1-C3 cover context, containers and components; C4 is the detailed UML code map. Portable JSON, SVG and PNG copies are included. |
| Earlier FigJam views | [C1](https://www.figma.com/board/KaoXEMPbKjCy1gOwdFdrUE?node-id=5-93), [C2](https://www.figma.com/board/KaoXEMPbKjCy1gOwdFdrUE?node-id=5-127) and [C3](https://www.figma.com/board/KaoXEMPbKjCy1gOwdFdrUE?node-id=30-56) are preserved. The Architect set is the current four-level model. |
| [C4 diagram PDF](<Kubernetes PE C4 (OLD).pdf>) | Historical target-architecture export dated 18 October 2026. It still describes HPA and automated analysis as planned. Preserve it as an earlier design; use the Architect set for the implemented structure. |

Architecture diagrams describe structure, not current cluster availability or proven scaling performance.

## Feedback and supporting context

| Document | Role |
|---|---|
| [Personal FeedPulse PDF](FeedPulse.pdf) | Updated personal teacher-feedback export from 15 November 2026. Expert and peer comments are recorded separately in Feedbacks above. |
| [Earlier PDP PDF](PDP.pdf) | Historical export from September with the broader inference-and-agent prototype scope. Use Container Orchestration for AI Inference PDP above for the current scope and reflection. |
| [Group FeedPulse PDF](<Group Feedpulse.pdf>) | SUE group-project context, kept separate from personal experiment results. |
| [AV-CSS course guide](AV-CSS-lesson-explainer.docx) | Course reference. Verify changed requirements against official sources. |

## Where other information lives

- [Project README](../README.md): entry point and project layout.
- [Status](../md/STATUS.md): verified progress and remaining work.
- [Roadmap](../md/ROADMAP.md) and [task plans](../md/plans/): milestones, procedures and completion criteria.
- [Technical decisions](../md/DECISIONS.md): concise local choices and constraints. Technology Decisions in Notion contains the detailed implementation rationale; the research document contains the orchestration-platform comparison.
- [Results](../results/): original run data and adjacent reports. The [18-run main series](../results/main/series-2026-10-25-v1.1/analysis-main-2026-10-26/README.md), [nine-run controlled peak-12 comparison](../results/follow-up/comparison-20261110-205108-peak12/README.md) and [six-run CPU/request comparison](../results/custom-metric/series-20261114-191048/README.md) remain separate.
- [Reproduction check](../results/reproduction/check-2026-11-06/README.md): fresh clone, short live check and saved main-analysis replay on the same Windows host.

Research v0.12 includes both later comparisons and their collection limitations. Later expert and peer comments are saved in Feedbacks, and teacher discussions are recorded in FeedPulse. Local files and GitHub storage do not replace Fontys Portflow submission.

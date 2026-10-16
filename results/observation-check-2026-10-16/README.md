# Initial observation check: superseded

The first check on 2026-10-16 saved CPU/memory and k6 data but incorrectly returned an empty Deployment list: the pod label selector was applied to Deployment metadata. Independent verification caught this before completion was reported.

The collector was corrected to read Deployments in the selected namespace, a regression test was added, and the check was repeated. These original files remain for traceability; use [the corrected run](../observation-check-2026-10-16-verified/README.md) as verification evidence.

# Documentation review and publication

Date: 2026-10-19. User requested review of pending Markdown, necessary corrections, small commits and push to the existing repository.

OWNS: AGENTS.md, README.md, .rgignore, pyproject.toml, bench/analyze.py, bench/test_analyze.py, bench/pilot_records.py, bench/test_pilot_records.py, docs/**, md/**, results/pilot/**, results/observer-overhead-2026-10-16-series1/**

## Objective and steps

Review the pending documentation reorganization, measurement-integrity maintenance and completed pilot together. Keep the English setup guide, linked future scaling procedure and local document index; correct stale implementation claims without marking future scaling work complete. Preserve existing raw evidence and Word/PDF bytes. Review and publish coherent groups of code, supporting evidence and documentation; do not rewrite history. Verify the private destination and exact pushed HEAD.

## Acceptance

- [x] G1: Documentation agrees with actual pilot results and code, distinguishes historical records from current state, and leaves protocol/scaling milestones unfinished.
  EVIDENCE: Reviewed all pending Markdown groups against implementation and saved pilot evidence. Corrected stale analyzer/rate-selection claims and damaged ranges; retained the English guide, source ownership, historical records and unfinished protocol/scaling milestones. Parsed 36 PowerShell blocks without execution.

- [x] G2: Historical raw evidence and saved overhead aggregates remain unchanged, and project Markdown links/anchors resolve.
  CHECK: python md/plans/measurement-integrity/verify.py
  EXPECT: measurement integrity verification passed
  EVIDENCE: automatic-evidence=v1; definition-sha256=b867f420badc98690e376c7d03e5e8a3357c1b437d383c8b50e0054d9dc57927; exit=0; EXPECT=matched; output-sha256=aa040cc5117d5f1efdd4246c8093abbe8598c0d0814a7fff847604c6433b1502; output-bytes=140; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G3: The collector, analysis and launcher regression suite passes.
  CHECK: python -m unittest discover -s bench -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=867be6e0aada05497a1f2f30bd8a473718c9f418a23695fe7eb04f030fdd746f; exit=0; EXPECT=matched; output-sha256=bbc1de2a89617a9b5ebff66b23dfbc17d64532c0c72bfe52c3aae0be46aa3054; output-bytes=7640; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G4: Historical-overhead validation tests reject corrupt evidence and accept valid source snapshots and collection jitter.
  CHECK: python -m unittest discover -s results/observer-overhead-2026-10-16-series1 -p test_overhead.py -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=efd64a2ef41eb23e8327b06a566e472c9b0a8522db8f34b6973b1ac19fa341ba; exit=0; EXPECT=matched; output-sha256=9db07ae800ff851e8f5a63529f1bd991f369b65b2967d19f8f80ac5f3fe13e0c; output-bytes=1342; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G5: All pre-review raw pilot/result data and Word/PDF bytes are preserved, and committed changes are split into reviewed logical groups.
  EVIDENCE: Pre-review SHA-256 comparison preserves all 358 result/source/Word/PDF files covered by the snapshot. The reviewed path set is partitioned exactly into eight named commits. 50 bench tests, 10 overhead tests and three disabled-check assertions pass; no weights or credential paths enter the commit scope.

- [ ] G6: Reviewed commits are published to the existing private origin/main and the published commit equals local HEAD.
  EVIDENCE: pending

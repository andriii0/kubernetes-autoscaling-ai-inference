# Gates: measurement integrity and documentation consistency

Historical verification record from 2026-10-18, before the later pilot. Current state is in [STATUS.md](../../STATUS.md); commands and evidence below retain their original execution context.

Scope: Address all seven reported issues and preserve raw historical evidence.

- [x] G1: A new pilot run works and an existing output directory is rejected without changing its files.
  CHECK: C:\Users\matvi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s bench -p test_run_pilot.py -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=dc5d634e668ed58cafcd2112a7bf8fc939f798aa98e6ad0c5bbac043e072ace4; exit=0; EXPECT=matched; output-sha256=6df8fd674509b813c1a95ad4816434445e05c0216fd01266d9d66c46f7761f83; output-bytes=974; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G2: Actual k6 output preserves valid zeros and omits invalid or absent optional measurements with explicit availability metrics.
  CHECK: C:\Users\matvi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s bench -p test_inference.py -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=b4863a6526cbe8a6f4696a19f389938974ae52a789455f623a9768fe102bb974; exit=0; EXPECT=matched; output-sha256=90a9f399331f2e007bcf2761a8bbcb3e54134272eaa14651b351cd962681bdb2; output-bytes=282; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G3: Overhead analysis accepts valid observation times and rejects duplicates, reordering and excessive internal gaps.
  CHECK: C:\Users\matvi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s results/observer-overhead-2026-10-16-series1 -p test_overhead.py -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=8630c13cacca0d450243248b1833ac2c81f4f849f6408d317645571733e69878; exit=0; EXPECT=matched; output-sha256=e458193ccc8fd5f473f71762e0a28eb4794b5bcc6ff6e29dc704792eefae2362; output-bytes=1342; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G4: Research Word/PDF, local decisions and the unchanged probe consistently distinguish server readiness, warm initial replicas and cold new replicas; all rendered pages are readable.
  EVIDENCE: 2026-10-18: Research v0.7 DOCX and matching native Word PDF; all 14 rendered pages inspected. Existing probe unchanged; DECISIONS section 10 and guide separate API Ready, initial warmup and new-replica loading. Packaged renderer lacked LibreOffice; native Word export plus Poppler used instead.

- [x] G5: The Notion PDP practical prototype is inference-only while agents remain literature/future scope; readback preserves the research-first method and learning goals.
  EVIDENCE: 2026-10-18: Notion page 3e2c7c69-7bfd-814d-8509-f00f3f7ae471 updated and fetched again. Prototype/activities/products are inference-only; agents remain literature/future work; research-first sequence and five learning outcomes preserved.

- [x] G6: Both editable C4 views and the saved PDF clearly identify target architecture and planned HPA/analysis, with readable nonoverlapping labels.
  EVIDENCE: 2026-10-18: FigJam nodes 5:94 and 5:128 label target architecture; 5:156 labels HPA planned. C1/C2 screenshots inspected without overlaps. Saved C4 PDF has a global target/planned-status annotation and its rendered page was inspected.

- [x] G7: Repository agent instructions require an explicit commit request and no longer treat push as commit permission.
  EVIDENCE: 2026-10-18: Read back AGENTS.md line 48: Commit only when explicitly requested. A request to push does not authorize creating a commit. No commit/push performed.

- [x] G8: Raw historical measurement hashes remain unchanged, a temporary-copy reanalysis matches saved aggregates, and documentation links resolve.
  CHECK: C:\Users\matvi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe md/plans/measurement-integrity/verify.py
  EXPECT: measurement integrity verification passed
  EVIDENCE: automatic-evidence=v1; definition-sha256=1a91dea7870c4a14dc80318bd441d8383938c16960b38a8311b0922f08f357f7; exit=0; EXPECT=matched; output-sha256=48bb60a0b021612dac3785b4c84ced9f38f017a8b5c27dd9c33d0c0abfc28faf; output-bytes=139; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

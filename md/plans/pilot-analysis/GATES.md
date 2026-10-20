# Gates: pilot analysis and discovery

OWNS: bench/analyze.py, bench/test_analyze.py, bench/pilot_records.py, bench/test_pilot_records.py, pyproject.toml, md/STATUS.md, md/ROADMAP.md, md/plans/measurements-and-pilot.md, md/plans/pilot-analysis/**, results/pilot/**, md/plans/experiment-protocol.md

Scope: finish minimal reproducible analysis, inspect successive one-replica discovery probes and repeated selected candidates, record supported settings and limitations.

Historical pilot-completion record from 2026-10-18. Its pending step-17 and unset-target statements describe that execution. The later [main experiment protocol v1.1](https://app.notion.com/p/3ffc7c697bfd813f8572c5b413836dcd) was agreed on 2026-10-21; original pilot evidence below is unchanged.

- [x] G1: Analysis calculates known latency/count/resource values, preserves missingness and rejects an existing output path.
  CHECK: python -m unittest discover -s bench -p test_analyze.py -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=a1cbfea8da93819244c6a82cf194329b1c696075e024fb63f16c6dc46f94578b; exit=0; EXPECT=matched; output-sha256=1d26d9fc3eca5377bfd5e1a6b20b4ecfed8974d144fba5ee70da25812385a85b; output-bytes=1254; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G2: A saved check produces readable aligned plots and statistics consistent with raw events and k6.
  EVIDENCE: Saved-check analysis and first/second peak PNGs visually inspected; all eight valid analysis p95/mean values match their raw k6 summaries. See results/pilot/discovery-2026-10-18-series1/analysis/ and README.md.

- [x] G3: Sequential pilot probes and repeated low/peak candidates have saved valid collection evidence; rate decisions follow the stop rules and record idle recovery.
  EVIDENCE: Eight valid runs, including two five-minute repetitions each at low=2 and peak=8, with separate recovery evidence. C stopped further increases; intermediate and confirmation order recorded before execution. Initial failed A retained/excluded. See results/pilot/discovery-2026-10-18-series1/README.md.

- [x] G4: Current status and selected protocol settings distinguish observed outcomes, provisional targets and remaining scaling work.
  EVIDENCE: STATUS.md and ROADMAP.md mark step 16 complete and step 17 pending; series README records selected rates, variable peak failures, unset pilot SLO and remaining main-protocol choices. No scaling advantage is claimed.

- [x] G5: Request timestamps one millisecond outside either boundary are reported explicitly, while two milliseconds are rejected.
  CHECK: python -m unittest discover -s bench -p test_pilot_records.py -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=dc1f8983b90a00a1299d7f67f0b719b4b4c4de093e0a27e9a59774978c02a1c1; exit=0; EXPECT=matched; output-sha256=6bd5eba1fa8bf912dca60440c6c03cb49743fbba0a62b4f4d9ba73a6c8a16028; output-bytes=1919; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

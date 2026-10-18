# Gates: pilot data collection

OWNS: bench/inference.js, bench/workload.json, bench/run_pilot.py, bench/pilot_records.py, bench/test_inference.py, bench/test_run_pilot.py, bench/test_pilot_records.py, md/STATUS.md, md/ARCHITECTURE.md, md/GETTING_STARTED.md, md/ROADMAP.md, md/plans/measurements-and-pilot.md, md/plans/data-collection/**

Historical completion record for the 2026-10-18 collection revision. Its test counts and remaining-analysis statements describe that revision, before the later [pilot](../../../results/pilot/discovery-2026-10-18-series1/README.md).

Scope: simplify blocking checks, strengthen negative tests and verify low-load collection; capacity discovery and pilot charts remain outside scope.

The initial 44-test result was superseded by review: two negative cases could fail for unrelated reasons, and one lifecycle rerun failed intermittently. This revision must reverify the outcomes below; live evidence is recorded separately from stub tests.

- [x] G1: Real k6 produces correlated starts and completions, classifies failures and preserves optional missing values.
  CHECK: python -m unittest discover -s bench -p test_inference.py -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=f02917c64728adb1d5b9fb1920607e4a272129efb29a6467372d4de7403eff87; exit=0; EXPECT=matched; output-sha256=b71152d6a1ba174862c2a365b013d1dc083e0f21790f9c02b5c96ed2a1daad5c; output-bytes=601; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G2: Version diagnostics only warn; real load completes, failed lifecycle tests retain diagnostics, and scheduler pauses respect the unchanged production coverage rule.
  CHECK: python -m unittest discover -s bench -p test_run_pilot.py -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=7e90d1d1edd0e9ffed913c39d837cb62ec2a4438bd9ef096c8ca7b9ec0a6d00b; exit=0; EXPECT=matched; output-sha256=916a654451441f22ce7d75e930a3ea90678e01be44866f109f4095cc9988dd59; output-bytes=2192; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G3: Single-defect fixtures fail for the specific intended reason; archive warnings preserve otherwise valid measurement data.
  CHECK: python -m unittest discover -s bench -p test_pilot_records.py -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=dc1f8983b90a00a1299d7f67f0b719b4b4c4de093e0a27e9a59774978c02a1c1; exit=0; EXPECT=matched; output-sha256=be76dadd462bb2bc891ca31fb301be6b14b51f3247c799ef01e69c5edb898ac5; output-bytes=1760; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G4: Existing resource observation checks still pass.
  CHECK: python -m unittest discover -s bench -p test_observe.py -v
  EXPECT: /Ran [1-9][0-9]* tests?[\s\S]*^OK$/m
  EVIDENCE: automatic-evidence=v1; definition-sha256=ba3e06eddc0442618bc9b85d2b1f489fa1ad30659ff68578bf9db97537dc35d1; exit=0; EXPECT=matched; output-sha256=5155b44ebad3f460f798cdd28ff4e6014260f6288800bcd448a9ab7d0454bd9f; output-bytes=2088; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G5: Documentation states the implemented run sequence, files, verification limits and remaining pilot work.
  EVIDENCE: Read updated status, architecture, roadmap and pilot plan against the implementation: warnings versus measurement errors, no repeated snapshot validation, unchanged production cadence and remaining analysis are consistent.
- [x] G6: Historical evidence hashes and reanalysis are preserved, and local documentation links resolve.
  CHECK: python md/plans/measurement-integrity/verify.py
  EXPECT: measurement integrity verification passed
  EVIDENCE: automatic-evidence=v1; definition-sha256=b867f420badc98690e376c7d03e5e8a3357c1b437d383c8b50e0054d9dc57927; exit=0; EXPECT=matched; output-sha256=aff9421956295a265dc304e912c02c84c6e4cd9a889e54d8e901d9ba734af098; output-bytes=140; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G7: Deliberately disabled unfinished-request, order and gap checks are caught by their targeted assertions.
  CHECK: python md/plans/data-collection/verify-tests.py
  EXPECT: negative-test verification passed
  EVIDENCE: automatic-evidence=v1; definition-sha256=6c08862f5c525906fb02353dcbd42020137b593fbafb4c6a366aa6565b2bf54f; exit=0; EXPECT=matched; output-sha256=12f2773ebd8ab09ed17078ffd0da382935318daf328a42a1a2bef8894f96adaa; output-bytes=125; shell=C:\WINDOWS\system32\cmd.exe; cwd=C:\Users\matvi\PycharmProjects\kubernetes-autoscaling-ai-inference; path=1f511c6f4970/67 entries

- [x] G8: One short run against the real model saves reconciled requests and cluster observations.
  EVIDENCE: results/pilot/20261018T202951240Z-collection-check: 12 paired successful requests, no failures/drops/unfinished work; 29 cluster samples, zero collection errors, stable container identity and matching raw/summary counters. Launcher/k6/collector returned 0. README records the independent raw-data read.

Revision verification notes: 43 tests (3 real-k6 event tests, 12 launcher tests, 12 record tests, 16 observer tests). The old lifecycle case passed 35 consecutive diagnostic attempts, so the original isolated failure was not reproduced. A controlled 450-ms observer-thread delay does reproduce a gap failure with the former 200-ms test interval. The integration test now uses the actual 5-second pilot setting; the production 10-second gap limit is unchanged. Ten consecutive revised lifecycle runs passed. Unexpected launcher exits retain files under the printed pilot-test-failure temporary directory. These checks do not prove that every possible timing failure is eliminated.

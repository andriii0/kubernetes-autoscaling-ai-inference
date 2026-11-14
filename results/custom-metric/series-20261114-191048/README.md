# Fresh comparison with a temporary clock guard

I started preparation at 20:14:37 Berlin on 14 November after 36 strict clock observations over three minutes passed. The new cycle uses target-1 and target-2 preparation, followed by six CPU/request cells in the original order. The driver stops on invalid data or cleanup and does not retry automatically. No completed comparison result is established by this startup record.

The independent Windows task is AI-Inference-Fresh-20261114-191048. Its worker temporarily masks Ubuntu systemd-timesyncd while keeping Ubuntu alive, and restores the prior enabled/active state on exit. Docker/WSL host-relative synchronization remains active. This is an environment mitigation, not proof of permanent clock repair or absolute UTC accuracy.

The measurement code is based on 7da7c66 with local changes to hide Windows child-process windows. I also fixed a missing-runtime test that still mocked the old executable lookup. The 154 focused tests passed. See [verification](../launch-20261114-191048/verification.json), [startup](../launch-20261114-191048/startup.json) and [worker](../launch-20261114-191048/worker.json). Source hashes are archived with each run.

The retired four-cell series, the stopped 16:05 preparation cycle and both later pre-load checks remain separate. I will not pool their measurements with these new six cells. Current progress is in workflow.json and preparation-new/manifest.json. No commit or push was made.

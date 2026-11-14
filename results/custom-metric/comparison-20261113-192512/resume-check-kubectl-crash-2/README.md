# Check after the kubectl crash

I found one failed node read in attempt 05 at 21:18:06 UTC. The Windows Application Error at 22:18:07 Berlin identifies Docker's kubectl.exe, exception 0xc0000409 and ntdll.dll. The other API and resource reads in that observation succeeded. This confirms a local client crash; the event does not explain its internal Windows cause.

The attempt recorded 454 started and completed requests: 274 successes, 180 failures and no unfinished client requests. It has no summary export and missed the end of the planned workload. Its collection is invalid, although cleanup passed. I retain it as an incomplete attempt.

All 30 repeated node reads passed. The saved live preflight confirmed the prepared host limits, stack identities and configuration, model digest and backend configuration. HPA was absent and the initial backend copy was Ready. I did not update kubectl, restart the cluster or weaken observation checks.

I added explicit comparison continuation. It replays each accepted cell from its verified source archive and compares the assessment, outcomes and resource results with the saved records. It refuses workload or collector changes. The continuation records changes only to the driver and the archive-review helper, preserves the previous manifest and uses separate retry, tunnel and preflight files.

The first diagnostic helper could not read the Windows event through its child shell and stopped before the live checks; its files remain in the adjacent directory. The second diagnostic completed, and [the event read directly](windows-events-direct.json) contains the matching crash.

The [before hashes](protected-before.json), [live check](live-preflight.json), [node reads](node-read-checks.json), [client version and hash](kubectl-client.json) and [request counts](result.json) retain the checked evidence.

All 51 focused tests and 263 Python tests passed. The [dry run](dry-run.json) accepted cells 1-4 and listed only 5-6 as pending. All 331 protected evidence files matched their [after hashes](protected-after.json). The [verification record](verification.json) and test outputs retain these checks. The observer, signal collector, workload and HPA settings did not change.

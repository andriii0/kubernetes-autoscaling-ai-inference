# Local browser checks

I keep these checks separate from Python unittest discovery. They use the actual HTML, JavaScript and local HTTP server with temporary results. Process detection and job subprocesses are replaced with local fixtures. No Kubernetes command, k6 load or saved project result is used.

## Run

From the repository root, with Node.js 20 or later and Python available:

```powershell
npm.cmd install --prefix tests/ui
$env:UI_TEST_PYTHON = (Resolve-Path .venv/Scripts/python.exe).Path
$env:UI_TEST_CHANNEL = 'msedge'
npm.cmd test --prefix tests/ui
```

This uses an installed Microsoft Edge without downloading a browser. For Playwright's bundled Chromium instead:

```powershell
Remove-Item Env:UI_TEST_CHANNEL -ErrorAction SilentlyContinue
node tests/ui/node_modules/playwright/cli.js install chromium
npm.cmd test --prefix tests/ui
```

The package pins Playwright. A missing dependency or browser fails the command explicitly. I use one browser and sequential tests; each test gets its own browser context. The temporary server and results are removed when the suite exits normally. There are no screenshots, videos or traces in the default run.

## Scenarios

- A completed series opens results without launching work. Target misses and collection failures have different labels.
- Notes preserve Unicode and literal HTML, survive save/reload, and keep drafts across navigation and refresh. A conflict preserves the on-disk note and the unsaved draft.
- The pilot form rejects an invalid rate, reports a failed launch and permits a dry retry with the chosen settings.
- A late result response cannot replace the newly selected result.
- A failed status request displays an error and disables launch.

These are functional browser checks, not a visual regression suite or proof of a live Kubernetes launch. Python tests separately verify backend validation, job exclusion, result parsing and note writes.

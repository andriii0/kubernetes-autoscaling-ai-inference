# Custom-metric overview plots

These overview plots are derived from the saved comparison summary and preparation manifest. They do not alter raw measurements or assessments. Per-run plots remain in each analysis directory. The comparison chart shows the three paired repetitions; the preparation chart shows both target checks.

I regenerate the overview PNG/SVG pairs from the saved manifests with:

```powershell
.\.venv\Scripts\python.exe -B bench/plot_custom_overview.py results/custom-metric/series-20261114-191048/comparison-new --overwrite
.\.venv\Scripts\python.exe -B bench/plot_custom_overview.py results/custom-metric/series-20261114-191048/preparation-new --overwrite
```

The comparison plot shows all three repetitions per policy: successful peak completions within five seconds, peak errors, and successful peak p95. Failures are excluded from p95, but remain in the first two panels' denominators. The preparation plot is separate and uses saved peak assessments, not whole-run p95. The selection rule uses scaling qualification, not whichever target has lower latency. No new requests are sent by this script. `--overwrite` replaces only the two named derived overview images in the selected folder.

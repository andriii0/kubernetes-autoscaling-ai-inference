"""Create plots from accepted peak-12 evidence without changing assessments."""

import argparse
import json
from pathlib import Path

from analyze import calculate_metrics, create_plots, load_results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('series', type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.series / 'manifest.json').read_text(encoding='utf-8'))
    destination = args.series / 'plots'
    destination.mkdir(exist_ok=False)
    rows = manifest['completed_runs']
    assessments = []
    for index, row in enumerate(rows, 1):
        data = load_results(args.series / row['run'])
        create_plots(data, calculate_metrics(data), destination / f"{index:02d}-{row['run']}")
        assessments.append(json.loads((args.series / row['analysis'] / 'comparison-assessment.json').read_text(encoding='utf-8')))
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5), layout='constrained')
    values = [a['primary']['p95_ms'] for a in assessments]
    ax.bar(range(len(rows)), [v / 1000 if v is not None else float('nan') for v in values])
    ax.axhline(5, color='#b91c1c', linestyle='--', label='Original target: ≤ 5 s')
    ax.set_xticks(range(len(rows)), [r['run'].replace('attempt-', '').replace('-burst', '') for r in rows], rotation=30, ha='right')
    ax.set_ylabel('Successful-response peak p95 (seconds)')
    ax.set_title('Accepted peak-12 runs · failed requests excluded from latency')
    ax.legend()
    fig.savefig(destination / 'primary-p95.png', dpi=150)
    plt.close(fig)
    (destination / 'README.md').write_text('# Saved-data plots\n\nI generated these plots with `bench/plot_peak12.py`. The manifest selects accepted runs, including recovered attempt 07. No load was repeated. Individual plots label whole-run latency; the overview uses saved peak assessments and the original 5-second target. Failed requests are excluded from latency, not from the saved error counts.\n', encoding='utf-8')


if __name__ == '__main__':
    main()

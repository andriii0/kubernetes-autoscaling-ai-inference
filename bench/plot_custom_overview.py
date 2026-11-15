"""Plot saved custom-metric preparation and paired outcomes; never run load."""

import argparse
import json
from pathlib import Path

from analyze_custom_comparison import summarize


def create(series, overwrite=False):
    manifest = json.loads((series / 'manifest.json').read_text(encoding='utf-8'))
    rows = manifest['completed']
    preparation = manifest.get('protocol', '').startswith('active-requests-preparation-')
    comparison = manifest.get('protocol', '').startswith('active-requests-comparison-')
    if not (preparation or comparison) or manifest.get('status') != 'finished' or not rows:
        raise ValueError('Choose a finished custom preparation or comparison manifest')
    summary = summarize(sorted(rows, key=lambda row: row['pair'])) if comparison else None
    destinations = [series / f'primary-p95.{ext}' for ext in ('png', 'svg')]
    if not overwrite and any(path.exists() for path in destinations):
        raise FileExistsError('Overview exists; use --overwrite to regenerate only these plots')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2 if preparation else 3,
                             figsize=(9 if preparation else 13, 4.6), layout='constrained')
    if preparation:
        labels = [str(row['target']) for row in rows]
        primary = [row['assessment']['primary'] for row in rows]
        axes[0].bar(labels, [row['p95_ms'] / 1000 for row in primary], color='#2563eb')
        axes[1].bar(labels, [row['failed'] for row in primary], color='#2563eb')
        axes[0].set(title='Preparation successful peak p95', ylabel='Seconds')
        axes[1].set(title='Preparation peak errors', ylabel='Requests')
        for ax in axes:
            ax.set_xlabel('Active requests per replica target')
        latency_axis = axes[0]
    else:
        for policy, label, color in (('cpu', 'CPU HPA', '#2563eb'),
                                     ('active-1', 'Request HPA - target 1', '#15803d')):
            arm = summary['arms'][policy]
            for ax, key, scale in zip(axes, ('peak_on_time_fraction', 'peak_error_fraction',
                                             'successful_peak_p95_ms'), (100, 100, .001)):
                values = [value * scale if value is not None else float('nan')
                          for value in arm[key]['values']]
                ax.plot([1, 2, 3], values, 'o', label=label, color=color)
                ax.set_xticks([1, 2, 3])
                ax.set_xlabel('Repetition within policy (pair order)')
        axes[0].set(title='Peak success within 5 s', ylabel='% of started peak requests', ylim=(0, 100))
        axes[1].set(title='Peak errors', ylabel='% of started peak requests')
        axes[1].set_ylim(bottom=-1)
        axes[2].set(title='Successful peak p95', ylabel='Seconds')
        axes[0].legend(fontsize=8)
        latency_axis = axes[2]
    latency_axis.axhline(5, color='#a16207', linestyle='--', linewidth=1, label='Target: 5 s')
    latency_axis.legend(fontsize=8)
    for ax in axes:
        ax.grid(axis='y', alpha=.25)
        ax.set_axisbelow(True)
    fig.suptitle('Saved peak assessments - failures excluded from latency', fontsize=12)
    for destination in destinations:
        fig.savefig(destination, dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('series', type=Path)
    parser.add_argument('--overwrite', action='store_true', help='Replace only the two derived overview images')
    args = parser.parse_args()
    create(args.series, args.overwrite)


if __name__ == '__main__':
    main()

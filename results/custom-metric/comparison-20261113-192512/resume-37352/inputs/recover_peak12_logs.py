"""Recover rotated CRI records into a separate, explicitly derived attempt."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from run_pilot import reconcile, save_json


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--series-dir', required=True, type=Path)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--uid', required=True)
    parser.add_argument('--node-log', required=True)
    args = parser.parse_args()
    source = args.series_dir / args.attempt
    target = source.with_name(source.name + '-recovered')
    meta = json.loads((source / 'metadata.json').read_text())
    if meta['k6_exit_code'] not in (0, 99) or meta['collector_exit_code'] != 0 or meta['errors']:
        raise ValueError('Recovery requires completed load and healthy observation')
    raw = subprocess.run(['minikube', '-p', 'ai-lab', 'ssh', '--', 'sudo cat ' + args.node_log],
                         check=True, capture_output=True).stdout
    recovered = []
    for line in raw.decode('utf-8').splitlines():
        at, stream, flag, message = line.split(' ', 3)
        if flag != 'F':
            raise ValueError('Partial CRI record requires explicit reconstruction')
        recovered.append(at + ' ' + message)
    shutil.copytree(source, target)
    (target / 'recovered-node-log.cri').write_bytes(raw)
    path = target / 'pod-logs' / (args.uid + '.log')
    original = path.read_text(encoding='utf-8').splitlines()
    # Rotation and the current stream must not overlap; never silently deduplicate evidence.
    if recovered and original and recovered[-1].split(' ', 1)[0] >= original[0].split(' ', 1)[0]:
        raise ValueError('Rotated and saved streams overlap')
    path.write_text('\n'.join(recovered + original) + '\n', encoding='utf-8')
    report = reconcile(target, meta)
    if not report['valid']:
        raise ValueError(str(report['errors']))
    meta.update(collection_valid=True, exit_code=meta['k6_exit_code'],
                status='finished' if meta['k6_exit_code'] == 0 else 'thresholds_failed',
                counts=report['counts'], warnings=report['warnings'])
    meta['log_recovery'] = dict(original_attempt=source.name, node_log=args.node_log,
                               raw_sha256=hashlib.sha256(raw).hexdigest(),
                               original_metadata_sha256=digest(source / 'metadata.json'),
                               note='Derived validation after restoring rotated logs; no new load')
    save_json(target / 'metadata.json', meta)
    save_json(target / 'collection-check.json', report)
    versions = {'run_pilot.py': [meta['source_sha256']['run_pilot.py'],
                               digest(Path(__file__).with_name('run_pilot.py'))]}
    save_json(args.series_dir / 'log-recovery.json', dict(runs={source.name: target.name},
              source_versions=versions, reason='Continuous fixed-mode log capture replaces end-only snapshot'))
    print(f'Recovered {report["counts"]}: {target}')


if __name__ == '__main__':
    main()

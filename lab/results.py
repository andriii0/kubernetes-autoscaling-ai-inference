"""Read saved evidence without changing or re-assessing it."""

import json
import math
from pathlib import Path
import re


GROUPS = ('Pilots', 'Series', 'Checks & diagnostics')


def read_json(path, issues=None):
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(value, dict):
            raise ValueError('expected a JSON object')
        return value
    except (OSError, ValueError) as error:
        if issues is not None:
            issues.append(f'{path.name}: {error}')
        return {}


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def object_field(value, key, issues):
    field = value.get(key)
    if field is None:
        return {}
    if not isinstance(field, dict):
        issues.append(f'{key}: expected a JSON object')
        return {}
    return field


def list_field(value, key, issues):
    field = value.get(key)
    if field is None:
        return []
    if not isinstance(field, list):
        issues.append(f'{key}: expected a JSON list')
        return []
    return field


def group_for(relative):
    if relative.parts[0] == 'follow-up' and len(relative.parts) > 1 and relative.parts[1].startswith('comparison-'):
        return GROUPS[1]
    return {'pilot': GROUPS[0], 'main': GROUPS[1]}.get(relative.parts[0], GROUPS[2])


def short_name(name):
    match = re.match(r'attempt-(\d+)-', name)
    if match:
        return f'Attempt {match[1]}' + (' · recovered' if name.endswith('-recovered') else '')
    return name.replace('series-', '').replace('recalibration-', 'Pilot · ').replace('comparison-', 'Comparison · ')


def outcome(metadata, check, assessment, issues):
    finished = bool(metadata.get('finished_at_utc') or metadata.get('load_finished_at_utc'))
    exit_code = metadata.get('exit_code', metadata.get('load_exit_code'))
    if issues:
        return 'Read error', 'bad'
    if (check.get('valid') is False or metadata.get('collection_valid') is False
            or assessment.get('data_valid') is False or metadata.get('collector_exit_code') not in (None, 0)):
        return 'Data failure', 'bad'
    if metadata.get('errors') or exit_code not in (None, 0, 99):
        return 'Run failed', 'bad'
    if not finished and exit_code is None:
        return 'Incomplete', 'muted'
    if assessment.get('overall') == 'not_assessable':
        return 'Not assessable', 'muted'
    if exit_code == 99 or metadata.get('status') == 'thresholds_failed' or assessment.get('overall') == 'fail':
        return 'Target missed', 'warn'
    if check.get('valid') is True and exit_code == 0:
        return 'Passed', 'good'
    return 'Not assessed', 'muted'


class Results:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def path(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError('Choose a path inside results')
        return path

    def run(self, folder):
        issues = []
        metadata = read_json(folder / 'metadata.json', issues)
        check = read_json(folder / 'collection-check.json', issues)
        assessment = self.assessment(folder, issues)
        status, tone = outcome(metadata, check, assessment, issues)
        relative = folder.relative_to(self.root)
        return dict(id=relative.as_posix(), kind='run', group=group_for(relative), name=short_name(folder.name),
                    mode=metadata.get('mode') or (f"fixed-{metadata['expected_replicas']}" if metadata.get('expected_replicas') else None),
                    date=metadata.get('started_at_utc') or metadata.get('load_started_at_utc'), status=status, tone=tone,
                    complete=bool(metadata.get('finished_at_utc') or metadata.get('load_finished_at_utc')) and metadata.get('exit_code', metadata.get('load_exit_code')) in (0, 99),
                    phase=metadata.get('phase'), profile=metadata.get('profile'), rate=number(metadata.get('rate')), issues=issues)

    def assessment(self, folder, issues):
        manifest = read_json(folder.parent / 'manifest.json', issues)
        if manifest.get('protocol') == 'peak12-v1':
            for row in manifest.get('completed_runs', []):
                if row.get('run') == folder.name:
                    analysis = row.get('analysis')
                    if not isinstance(analysis, str) or Path(analysis).name != analysis:
                        issues.append('Invalid comparison analysis path')
                        return {}
                    path = folder.parent / analysis / 'comparison-assessment.json'
                    if not path.resolve().is_relative_to(self.root) or not path.is_file():
                        issues.append('Comparison assessment is missing or outside results')
                        return {}
                    return read_json(path, issues)
        return read_json(folder / 'assessment.json', issues)

    def catalog(self):
        runs = {}
        for path in self.root.rglob('metadata.json'):
            if 'inputs' not in path.relative_to(self.root).parts and path.resolve().is_relative_to(self.root):
                runs[path.parent] = self.run(path.parent)
        # Parents with actual runs form series, including older series without manifests.
        parents = {path.parent for path in runs if len(path.relative_to(self.root).parts) >= 3}
        parents.update(path.parent for path in self.root.rglob('manifest.json')
                       if 'inputs' not in path.relative_to(self.root).parts and path.resolve().is_relative_to(self.root))
        parents.difference_update(runs)
        entries = list(runs.values())
        for parent in sorted(parents):
            children = [run for path, run in runs.items() if path.parent == parent]
            if not children and not (parent / 'manifest.json').exists():
                continue
            issues = []
            manifest = read_json(parent / 'manifest.json', issues)
            review = read_json(parent / 'review.json', issues)
            recovery = object_field(read_json(parent / 'log-recovery.json', issues), 'runs', issues)
            accepted = {row.get('run') for row in list_field(manifest, 'completed_runs', issues) if isinstance(row, dict)} if manifest.get('protocol') == 'peak12-v1' else set()
            preserved = []
            by_name = {Path(r['id']).name: r for r in children}
            for original, recovered in recovery.items():
                source, replacement = by_name.get(original), by_name.get(recovered)
                if source and replacement and recovered in accepted and replacement['complete'] and replacement['tone'] != 'bad':
                    source['name'] += ' · original'
                    preserved.append(source)
            assessed = [r for r in children if r not in preserved]
            completed = sum(run['complete'] for run in children)
            relative = parent.relative_to(self.root)
            planned = len(manifest['cells']) if isinstance(manifest.get('cells'), list) else None
            if relative.parts[0] == 'main':
                planned = 18
            status, tone = ('Complete', 'good') if assessed and all(r['complete'] for r in assessed) else ('Incomplete', 'muted')
            if planned and completed < planned:
                status, tone = 'Incomplete', 'muted'
            if any(run['tone'] == 'bad' for run in assessed) or issues:
                status, tone = 'Needs review', 'bad'
            if review.get('observed_status') == 'interrupted_process_missing':
                status, tone = 'Interrupted', 'bad'
            dates = [run['date'] for run in children if run['date']]
            name = short_name(parent.name)
            if group_for(relative) == 'Series':
                label = 'Main' if relative.parts[0] == 'main' else 'Follow-up'
                rates = sorted({run['rate'] for run in children if run['rate'] is not None})
                peak = f' · peak {max(rates):g} req / 10 s' if rates else ''
                name = label + peak
            entries.append(dict(id=relative.as_posix(), kind='series', group=group_for(relative),
                                name=name, mode='Mixed modes' if len({r['mode'] for r in children}) > 1 else (children[0]['mode'] if children else None),
                                date=manifest.get('started_at_utc') or (min(dates) if dates else None),
                                status=status, tone=tone, completed=completed, total=planned or len(children),
                                attempts=[run['id'] for run in sorted(children, key=lambda row: row['id'])],
                                saved_status=manifest.get('status'), preserved_originals=len(preserved),
                                target_met=sum(r['status'] == 'Passed' for r in assessed),
                                target_assessed=sum(r['status'] in ('Passed', 'Target missed') for r in assessed), issues=issues))
            for run in children:
                run['parent'] = relative.as_posix()
        return sorted(entries, key=lambda row: (row.get('date') or '', row['id']), reverse=True)

    def plot(self, folder, series=False):
        if series:
            candidates = sorted(folder.glob('*/primary-p95.png'))
        else:
            candidates = sorted(folder.glob('*.png')) + sorted(folder.glob('analysis/*.png'))
            candidates += sorted(folder.parent.glob(f'*/[0-9][0-9]-{folder.name}.png'))
        return next((p.relative_to(self.root).as_posix() for p in candidates
                     if p.resolve().is_relative_to(self.root)), None)

    def detail(self, relative):
        folder = self.path(relative)
        entries = self.catalog()
        entry = next((row for row in entries if row['id'] == relative), None)
        if entry is None:
            raise ValueError('Result no longer exists; refresh the list')
        entry['path'] = str(folder)
        entry['plot'] = self.plot(folder, entry['kind'] == 'series')
        if entry['kind'] == 'series':
            entry['children'] = [next(row for row in entries if row['id'] == child) for child in entry['attempts']]
            return entry
        issues = entry['issues']
        metadata = read_json(folder / 'metadata.json', issues)
        check = read_json(folder / 'collection-check.json', issues)
        assessment = self.assessment(folder, issues)
        summary = read_json(folder / 'summary.json', issues)
        primary = object_field(assessment, 'primary', issues)
        metrics = object_field(summary, 'metrics', issues)
        latency = object_field(metrics, 'successful_latency_ms', issues)
        workload = object_field(metadata, 'workload', issues)
        protocol = object_field(workload, 'main_protocol', issues)
        has_primary = bool(primary) or bool(metadata.get('protocol_version'))
        # Never substitute a whole-run value for a missing primary measurement.
        scope = 'Peak' if primary.get('name') == 'peak' or (has_primary and metadata.get('profile') == 'burst') else 'Whole run'
        p95 = primary.get('p95_ms') if has_primary else latency.get('p(95)')
        counts = object_field(check, 'counts', issues)
        timeout_count = None
        events_path = folder / 'request-events.jsonl'
        if events_path.exists() and number(counts.get('completed')) is not None:
            try:
                with events_path.open(encoding='utf-8') as stream:
                    events = [json.loads(line) for line in stream if line.strip()]
                completed = [event for event in events if event.get('event') == 'completed' and event.get('phase') == 'load']
                ids = [event.get('request_id') for event in completed]
                if (len(completed) == counts['completed'] and len(set(ids)) == len(ids)
                        and all('error_category' in event for event in completed)):
                    timeout_count = sum(event.get('error_category') == 'timeout' for event in completed)
            except (OSError, ValueError, AttributeError) as error:
                issues.append(f'request-events.jsonl: {error}')
        target = metadata.get('slo_ms')
        if metadata.get('protocol_version'):
            target = protocol.get('primary_p95_ms')
        entry.update(rate=number(metadata.get('rate')), low_rate=number(metadata.get('low_rate')),
                     p95_ms=number(p95), p95_scope=scope, target_ms=number(target),
                     successful=number(counts.get('successful')), failed=number(counts.get('failed')),
                     timeouts=timeout_count, unfinished=number(counts.get('unfinished')), dropped=number(counts.get('dropped')),
                     collection_valid=False if metadata.get('collection_valid') is False else check.get('valid'),
                     errors=list_field(check, 'errors', issues) + list_field(metadata, 'errors', issues),
                     warnings=list_field(check, 'warnings', issues) + list_field(metadata, 'warnings', issues))
        if issues:
            entry.update(status='Read error', tone='bad')
        return entry

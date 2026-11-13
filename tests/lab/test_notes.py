import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from lab.notes import Notes
from lab.results import Results


class NotesTests(unittest.TestCase):
    def test_custom_folder_note_is_allowed_only_when_saved_results_exist(self):
        with tempfile.TemporaryDirectory() as folder:
            notes = Notes(Results(folder))
            with self.assertRaises(ValueError):
                notes.get('custom-metric')
            run = Path(folder) / 'custom-metric/comparison/attempt-01'
            run.mkdir(parents=True)
            (run / 'metadata.json').write_text('{}', encoding='utf-8')
            saved = notes.save('custom-metric', 'Active client requests at Envoy.',
                               notes.get('custom-metric')['revision'])
            self.assertEqual(notes.get('custom-metric'), saved)
            with self.assertRaises(ValueError):
                notes.get('custom-metric/../pilot')

    def test_failed_atomic_replace_keeps_previous_note_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder) / 'pilot/example'
            run.mkdir(parents=True)
            (run / 'metadata.json').write_text('{}', encoding='utf-8')
            notes = Notes(Results(folder))
            saved = notes.save('pilot/example', 'original', notes.get('pilot/example')['revision'])
            before = set(run.iterdir())
            with patch('lab.notes.os.replace', side_effect=OSError('disk unavailable')):
                with self.assertRaisesRegex(OSError, 'disk unavailable'):
                    notes.save('pilot/example', 'replacement', saved['revision'])
            self.assertEqual(notes.get('pilot/example'), saved)
            self.assertEqual(set(run.iterdir()), before)
            self.assertEqual(notes.save('pilot/example', 'retry', saved['revision'])['text'], 'retry')

    def test_roundtrip_conflict_and_evidence_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = root / 'pilot/example/attempt-01'
            run.mkdir(parents=True)
            metadata = run / 'metadata.json'
            metadata.write_text('{}', encoding='utf-8')
            notes = Notes(Results(root))
            for result_id in ('pilot/example', 'pilot/example/attempt-01'):
                original = notes.get(result_id)
                saved = notes.save(result_id, 'Проблема с логами\n<script>text</script>', original['revision'])
                self.assertEqual(notes.get(result_id), saved)
                with self.assertRaisesRegex(ValueError, 'changed on disk'):
                    notes.save(result_id, 'stale edit', original['revision'])
                self.assertEqual(notes.get(result_id), saved)
                self.assertEqual(notes.save(result_id, '', saved['revision'])['text'], '')
            self.assertEqual(metadata.read_text(), '{}')
            for invalid in ('../outside', 'pilot', 'pilot/missing', None):
                with self.assertRaises(ValueError):
                    notes.get(invalid)
            with self.assertRaises(ValueError):
                notes.save('pilot/example', 'a' * 20001, '')


if __name__ == '__main__':
    unittest.main()

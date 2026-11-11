import tempfile
from pathlib import Path
import unittest

from lab.notes import Notes
from lab.results import Results


class NotesTests(unittest.TestCase):
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

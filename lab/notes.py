"""Local author notes, kept separate from measured evidence."""

import hashlib
import os
import tempfile
import threading


class Notes:
    def __init__(self, results):
        self.results = results
        self.lock = threading.Lock()

    def path(self, result_id):
        if not isinstance(result_id, str) or not any(row['id'] == result_id for row in self.results.catalog()):
            raise ValueError('Choose a saved run or series')
        path = self.results.path(result_id) / 'notes.md'
        if path.is_symlink():
            raise ValueError('Notes must be a regular local file')
        return path

    @staticmethod
    def read(path):
        raw = path.read_bytes() if path.exists() else b''
        return dict(text=raw.decode('utf-8'), revision=hashlib.sha256(raw).hexdigest())

    def get(self, result_id):
        with self.lock:
            return self.read(self.path(result_id))

    def save(self, result_id, text, revision):
        if not isinstance(text, str) or len(text) > 20000:
            raise ValueError('Notes must contain at most 20,000 characters')
        with self.lock:
            path = self.path(result_id)
            if self.read(path)['revision'] != revision:
                raise ValueError('Notes changed on disk. Copy your draft and reload before saving.')
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, suffix='.tmp', delete=False) as output:
                    temporary = output.name
                    output.write(text.encode('utf-8'))
                os.replace(temporary, path)
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
            return self.read(path)

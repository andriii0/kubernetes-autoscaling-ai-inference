"""Loopback-only server for Inference Lab."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import threading
from urllib.parse import parse_qs, urlsplit
import webbrowser

from .jobs import Jobs, ROOT
from .results import Results
from .launch import pilot_configuration
from .notes import Notes

STATIC = Path(__file__).parent / 'static'


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, results, dry_only=False):
        super().__init__(address, Handler)
        self.results = results
        self.jobs = Jobs(results, dry_only)
        self.token = secrets.token_urlsafe(32)
        self.notes = Notes(results)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def send(self, value, content_type='application/json', status=200):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode() if content_type == 'application/json' else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
        try:
            self.end_headers()
            self.wfile.write(data)
        except ConnectionError:
            # A closed tab can cancel an in-flight catalog or plot request.
            self.close_connection = True

    def local_request(self):
        port = self.server.server_port
        hosts = (f'127.0.0.1:{port}', f'localhost:{port}')
        return self.headers.get('Host') in hosts

    def do_GET(self):
        if not self.local_request():
            self.send({'error': 'Local access only'}, status=403)
            return
        url = urlsplit(self.path)
        query = parse_qs(url.query)
        try:
            if url.path == '/api/results':
                self.send(self.server.results.catalog())
            elif url.path == '/api/pilot-settings':
                self.send(pilot_configuration())
            elif url.path == '/api/detail':
                self.send(self.server.results.detail(query.get('id', [''])[0]))
            elif url.path == '/api/notes':
                self.send(self.server.notes.get(query.get('id', [''])[0]))
            elif url.path == '/api/status':
                self.send(dict(self.server.jobs.status(), token=self.server.token))
            elif url.path == '/plot':
                path = self.server.results.path(query.get('id', [''])[0])
                if path.suffix.lower() != '.png':
                    raise ValueError('Choose a saved PNG plot')
                self.send(path.read_bytes(), 'image/png')
            else:
                name = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css', '/runs.css': 'runs.css'}.get(url.path)
                if not name:
                    self.send({'error': 'Not found'}, status=404)
                    return
                self.send((STATIC / name).read_bytes(), (mimetypes.guess_type(name)[0] or 'text/plain') + '; charset=utf-8')
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.send({'error': str(error)}, status=400)

    def do_POST(self):
        origin = self.headers.get('Origin')
        expected_origin = f"http://{self.headers.get('Host')}"
        if not self.local_request() or (origin and origin != expected_origin) or self.headers.get('X-Lab-Token') != self.server.token:
            self.send({'error': 'Reload Inference Lab to use local actions'}, status=403)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= (160000 if self.path == '/api/notes' else 8192):
                raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(size))
            if self.path == '/api/launch':
                self.send(self.server.jobs.start(body.get('kind'), body.get('dry_run'), body.get('series', ''), body.get('activity', ''), body.get('pilot')))
            elif self.path == '/api/notes':
                self.send(self.server.notes.save(body.get('id'), body.get('text'), body.get('revision')))
            elif self.path == '/api/open':
                path = self.server.results.path(body.get('id', ''))
                if not path.is_dir():
                    raise ValueError('Result folder no longer exists')
                os.startfile(str(path))
                self.send({'opened': True})
            else:
                self.send({'error': 'Not found'}, status=404)
        except (OSError, ValueError, TypeError, AttributeError) as error:
            self.send({'error': str(error)}, status=400)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='Allow only no-load launch checks')
    args = parser.parse_args(argv)
    # OS lock is released on exit, including crashes; the file itself is not a stale lock.
    state = ROOT / '.inference-lab'
    state.mkdir(exist_ok=True)
    with (state / 'server.lock').open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            lock.write(b'0')
            lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                parser.error('Inference Lab is already running for this project')
        server = Server(('127.0.0.1', args.port), Results(ROOT / 'results'), args.dry_run)
        url = f'http://127.0.0.1:{server.server_port}'
        print(f'Inference Lab: {url}', flush=True)
        if not args.no_browser:
            threading.Timer(.3, webbrowser.open, args=(url,)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('Closing Inference Lab. Waiting for any active command cleanup.', flush=True)
            if server.jobs.process:
                server.jobs.process.wait()
        finally:
            server.server_close()

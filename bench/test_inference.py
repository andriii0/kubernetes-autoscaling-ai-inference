import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class InferenceMetricTests(unittest.TestCase):
    def test_concurrent_vus_keep_distinct_complete_request_pairs(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                time.sleep(.02)
                data = b'{"done":true,"response":"Stub answer"}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                wrapper = folder / "scenario.js"
                source = Path(__file__).with_name("inference.js").resolve().as_uri()
                wrapper.write_text(f"import generate from {json.dumps(source)};\n"
                                   "export const options = { vus: 3, iterations: 12 };\nexport default generate;\n")
                events = folder / "events.jsonl"
                result = subprocess.run(
                    [shutil.which("k6"), "run", "--quiet", "--no-usage-report", "--log-format", "raw",
                     "--console-output", str(events), str(wrapper)],
                    env={**{k: v for k, v in os.environ.items() if not k.upper().startswith("K6_")},
                         "BASE_URL": f"http://127.0.0.1:{server.server_port}", "REQUEST_EVENTS": "1", "RUN_ID": "parallel"},
                    capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                records = [json.loads(line) for line in events.read_text().splitlines()]
                started = {e["request_id"]: e for e in records if e["event"] == "started"}
                completed = {e["request_id"]: e for e in records if e["event"] == "completed"}
                self.assertEqual(len(records), 24)
                self.assertEqual(len(started), 12)
                self.assertEqual(started.keys(), completed.keys())
                self.assertGreater(len({e["vu"] for e in records}), 1)
                self.assertTrue(all(e["outcome"] == "success" for e in completed.values()))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_actual_k6_classifies_failed_responses_and_timeouts(self):
        class Handler(BaseHTTPRequestHandler):
            index = 0

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                index = Handler.index
                Handler.index += 1
                if index == 5:
                    self.close_connection = True
                    return
                if index == 4:
                    time.sleep(.4)
                bodies = [b'{"done":true,"response":" "}', b'{"done":false}', b'not json',
                          b'{"error":"unavailable"}', b'{"done":true,"response":"late"}']
                data = bodies[index]
                try:
                    self.send_response(503 if index == 3 else 200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                shutil.copyfile(Path(__file__).with_name("inference.js"), folder / "inference.js")
                workload = json.loads(Path(__file__).with_name("workload.json").read_text())
                workload["timeout_seconds"] = .15
                (folder / "workload.json").write_text(json.dumps(workload))
                wrapper = folder / "scenario.js"
                wrapper.write_text("import generate from './inference.js';\n"
                                   "export const options = { vus: 1, iterations: 6 };\nexport default generate;\n")
                events = folder / "events.jsonl"
                result = subprocess.run(
                    [shutil.which("k6"), "run", "--quiet", "--no-usage-report", "--log-format", "raw",
                     "--console-output", str(events), str(wrapper)],
                    env={**{k: v for k, v in os.environ.items() if not k.upper().startswith("K6_")},
                         "BASE_URL": f"http://127.0.0.1:{server.server_port}", "REQUEST_EVENTS": "1", "RUN_ID": "failures"},
                    capture_output=True, text=True, timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                records = [json.loads(line) for line in events.read_text().splitlines()]
                completed = [e for e in records if e["event"] == "completed"]
                self.assertEqual([e["error_category"] for e in completed],
                                 ["empty_response", "incomplete_response", "invalid_json", "http_status", "timeout", "transport"])
                self.assertEqual(len(records), 12)
                self.assertTrue(all(e["outcome"] == "failure" and e["output_tokens"] is None for e in completed))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_actual_k6_preserves_zeros_and_reports_missing_optional_fields(self):
        executable = shutil.which("k6")
        self.assertIsNotNone(executable, "k6 must be installed for this integration check")
        responses = [
            {},
            {"eval_count": None, "load_duration": None},
            {"eval_count": "56", "load_duration": "1000000"},
            {"eval_count": -1, "load_duration": -1},
            {"eval_count": 1.5, "load_duration": 1.5},
            {"eval_count": True, "load_duration": False},
            {"eval_count": 0, "load_duration": 0},
            {"eval_count": 56, "load_duration": 2000000},
            {"eval_count": 7},
            {"load_duration": 3000000},
        ]

        class Handler(BaseHTTPRequestHandler):
            index = 0

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                payload = {"done": True, "response": "Completed text", **responses[Handler.index]}
                Handler.index += 1
                data = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                wrapper = folder / "scenario.js"
                source = Path(__file__).with_name("inference.js").resolve().as_uri()
                wrapper.write_text(
                    f"import generate from {json.dumps(source)};\n"
                    f"export const options = {{ vus: 1, iterations: {len(responses)} }};\n"
                    "export default generate;\n", encoding="utf-8",
                )
                raw = folder / "requests.json"
                events = folder / "request-events.jsonl"
                result = subprocess.run(
                    [executable, "run", "--quiet", "--no-usage-report", "--no-color", "--log-format", "raw",
                     "--console-output", str(events), "--out", f"json={raw}", str(wrapper)],
                    env={**{k: v for k, v in os.environ.items() if not k.upper().startswith("K6_")},
                         "BASE_URL": f"http://127.0.0.1:{server.server_port}", "REQUEST_EVENTS": "1", "RUN_ID": "optional-fields"},
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                points = [json.loads(line) for line in raw.read_text().splitlines()]

                def values(metric):
                    return [p["data"]["value"] for p in points if p.get("type") == "Point" and p.get("metric") == metric]

                self.assertEqual(values("output_tokens"), [0, 56, 7])
                self.assertEqual(values("model_load_ms"), [0, 2, 3])
                self.assertEqual(values("output_tokens_available"), [0] * 6 + [1, 1, 1, 0])
                self.assertEqual(values("model_load_available"), [0] * 6 + [1, 1, 0, 1])
                self.assertEqual(values("inference_errors"), [0] * len(responses))
                self.assertEqual(Handler.index, len(responses))
                records = [json.loads(line) for line in events.read_text().splitlines()]
                self.assertEqual(len(records), 2 * len(responses))
                completed = [r for r in records if r["event"] == "completed"]
                self.assertEqual(len({r["request_id"] for r in completed}), len(responses))
                self.assertEqual([r["output_tokens"] for r in completed], [None] * 6 + [0, 56, 7, None])
                self.assertEqual([r["model_load_ms"] for r in completed], [None] * 6 + [0, 2, None, 3])
                self.assertTrue(all("response" not in r and r["run_id"] == "optional-fields" for r in records))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

"""Explicit Docker functional checks; excluded from normal unittest discovery."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bench"))
import custom_metric_stack as stack
import custom_metrics as metrics


def prom_cases():
    labels = 'namespace="inference",service="inference-gateway",job="inference-gateway",pod_uid="uid",instance="host:9901"'
    gauge = metrics.SOURCE + "{" + labels + ',inference_listener="inference"}'
    up = "up{" + labels + "}"
    tests = []
    for name, value, healthy, extra, expected in (
            ("three", "3+0x3", "1+0x3", [], 3), ("zero", "0+0x3", "1+0x3", [], 0),
            ("stale", "3 _ _ _", "1+0x3", [], None), ("negative", "-1+0x3", "1+0x3", [], None),
            ("infinite", "+Inf +Inf +Inf +Inf", "1+0x3", [], None),
            ("nan", "NaN NaN NaN NaN", "1+0x3", [], None),
            ("down", "3+0x3", "0+0x3", [], None), ("old-health", "3+0x3", "1 _ _ _", [], None),
            ("duplicate", "3+0x3", "1+0x3", [{"series": gauge[:-1] + ',extra="duplicate"}', "values": "2+0x3"}], None),
            ("missing", "_ _ _ _", "1+0x3", [], None)):
        tests.append({"name": name, "interval": "5s", "input_series": [
            {"series": gauge, "values": value}, {"series": up, "values": healthy}, *extra],
            "promql_expr_test": [{"expr": metrics.adapter_query('namespace="inference",service="inference-gateway"'),
                                 "eval_time": "15s", "exp_samples": [] if expected is None else [{
                                     "labels": '{namespace="inference",service="inference-gateway"}', "value": expected}]}]})
    return {"rule_files": [], "evaluation_interval": "5s", "tests": tests}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    folder = args.output_dir.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    name = "inference-metric-check-" + uuid.uuid4().hex[:10]
    result = {"status": "failed", "checks": [], "images": stack.IMAGES, "errors": []}
    releases = {key: threading.Event() for key in ("a", "b", "c", "cancel", "timeout")}
    seen, lock = [], threading.Lock()
    backend_finished = {key: threading.Event() for key in releases}

    class Backend(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            key = self.headers.get("X-Inference-Request-ID")
            with lock:
                seen.append({"id": key, "peer": self.client_address})
            if key in releases and not releases[key].wait(15):
                return
            body = b'{"done":true,"response":"fixture"}'
            try:
                self.send_response(503 if key == "error" else 200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                pass
            finally:
                if key in backend_finished:
                    backend_finished[key].set()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("0.0.0.0", 0), Backend)
    server.daemon_threads = True
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    created = False
    index = 0

    def command(*parts, timeout=60):
        nonlocal index
        index += 1
        completed = subprocess.run(["docker", *parts], capture_output=True, text=True, timeout=timeout)
        (folder / f"docker-{index:02d}.txt").write_text(completed.stdout + completed.stderr, encoding="utf-8")
        if completed.returncode:
            raise RuntimeError(f"Docker command {index} failed: {completed.stderr[-1500:]}")
        return completed.stdout.strip()

    def write(filename, value):
        (folder / filename).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def wait_for(predicate, label, seconds=15):
        deadline = time.monotonic() + seconds
        last = None
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return
            except (OSError, ValueError, urllib.error.URLError) as error:
                last = error
            time.sleep(.1)
        raise AssertionError(f"Timed out: {label}; last error: {last}")

    try:
        envoy = stack.envoy_config()
        # The host fixture listens on IPv4; Docker Desktop also advertises an IPv6 host address.
        envoy["static_resources"]["clusters"][0]["dns_lookup_family"] = "V4_ONLY"
        envoy["static_resources"]["clusters"][0]["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"] = stack.address(
            "host.docker.internal", server.server_port)
        write("envoy.json", envoy)
        write("prometheus.json", stack.prometheus_config())
        write("query-tests.json", prom_cases())
        mount = f"{folder}:/etc/inference:ro"
        command("run", "--rm", "-v", mount, stack.IMAGES[metrics.GATEWAY], "--mode", "validate", "-c", "/etc/inference/envoy.json", timeout=240)
        result["checks"].append("Envoy config accepted by pinned binary")
        for arguments in (("check", "config", "/etc/inference/prometheus.json"),
                          ("test", "rules", "/etc/inference/query-tests.json")):
            command("run", "--rm", "--entrypoint", "/bin/promtool", "-v", mount,
                    stack.IMAGES["inference-prometheus"], *arguments, timeout=240)
        result["checks"].append("Prometheus config and ten PromQL success/failure cases passed")
        command("run", "--rm", "-d", "--name", name, "-p", "127.0.0.1::8080", "-p", "127.0.0.1::9901",
                "-v", mount, stack.IMAGES[metrics.GATEWAY], "-c", "/etc/inference/envoy.json", "--concurrency", "1")
        created = True
        inspection = json.loads(command("inspect", name))[0]
        ports = inspection["NetworkSettings"]["Ports"]
        client_port = int(ports["8080/tcp"][0]["HostPort"])
        admin = "http://127.0.0.1:" + ports["9901/tcp"][0]["HostPort"]
        client = f"http://127.0.0.1:{client_port}/api/generate"
        result["envoy_image_id"] = inspection["Image"]

        def gauge():
            with urllib.request.urlopen(admin + "/stats/prometheus", timeout=2) as response:
                raw = response.read().decode()
            (folder / "last-metrics.txt").write_text(raw, encoding="utf-8")
            lines = [line for line in raw.splitlines() if line.startswith(metrics.SOURCE + "{")
                     and 'inference_listener="inference"' in line]
            if len(lines) != 1:
                raise ValueError(f"expected one exported gauge, got {lines}")
            return float(lines[0].split()[-1])

        def request(key, timeout=10):
            req = urllib.request.Request(client, data=b"{}", headers={"X-Inference-Request-ID": key, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.status, response.read()

        wait_for(lambda: gauge() == 0, "initial zero")
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {key: pool.submit(request, key) for key in ("a", "b", "c")}
            try:
                wait_for(lambda: gauge() == 3, "three held requests")
                releases["a"].set()
                assert futures["a"].result()[0] == 200
                wait_for(lambda: gauge() == 2, "two remaining requests")
            finally:
                for key in ("a", "b", "c"):
                    releases[key].set()
            for future in futures.values():
                assert future.result()[0] == 200
        wait_for(lambda: gauge() == 0, "returned to zero")
        result["checks"].append("Real downstream gauge: 0 -> 3 -> 2 -> 0")
        try:
            request("error")
            raise AssertionError("backend 503 was hidden")
        except urllib.error.HTTPError as error:
            assert error.code == 503
        wait_for(lambda: gauge() == 0, "HTTP failure cleared")
        try:
            request("timeout", timeout=.5)
            raise AssertionError("slow backend did not exceed client deadline")
        except (TimeoutError, socket.timeout):
            pass
        wait_for(lambda: gauge() == 0, "timed-out client cleared")
        assert not backend_finished["timeout"].is_set(), "backend should still be held after client timeout"
        releases["timeout"].set()
        assert backend_finished["timeout"].wait(2)
        connection = socket.create_connection(("127.0.0.1", client_port), timeout=3)
        try:
            connection.sendall(b"POST /api/generate HTTP/1.1\r\nHost: local\r\nContent-Length: 2\r\nX-Inference-Request-ID: cancel\r\n\r\n{}")
            wait_for(lambda: gauge() == 1 and any(entry["id"] == "cancel" for entry in seen),
                     "cancellation request accepted by gateway and backend")
        finally:
            connection.close()
        wait_for(lambda: gauge() == 0, "cancelled client cleared")
        releases["cancel"].set()
        assert backend_finished["cancel"].wait(2)
        result["checks"].append("503, client timeout and cancellation clear the gauge; late backend work stays separate")
        for _ in range(3):
            with urllib.request.urlopen(admin + "/ready", timeout=2) as response:
                assert response.status == 200
        assert gauge() == 0
        assert len(seen) == 6 and len({tuple(entry["peer"]) for entry in seen}) == 6, seen
        result["checks"].append("Admin health excluded, one backend attempt per request, separate HTTP/1.1 upstream connections")
        starts = [{"event": "started", "request_id": key} for key in ("a", "b", "c", "error", "timeout", "cancel")]

        def access_logs_complete():
            # Envoy flushes access logs asynchronously after requests finish.
            logs = command("logs", name)
            access = [json.loads(line) for line in logs.splitlines() if line.startswith("{")]
            metrics.reconcile_gateway(starts, access)
            return True

        wait_for(access_logs_complete, "complete gateway access records")
        result["checks"].append("Every client start reconciled with exactly one gateway access record")
        command("restart", name)
        restarted = json.loads(command("inspect", name))[0]
        # Docker may reassign an ephemeral published port when the container restarts.
        previous_admin = admin
        admin = "http://127.0.0.1:" + restarted["NetworkSettings"]["Ports"]["9901/tcp"][0]["HostPort"]
        result["restart_admin_addresses"] = {"before": previous_admin, "after": admin}
        wait_for(lambda: gauge() == 0, "zero after gateway restart")
        assert restarted["State"]["StartedAt"] != inspection["State"]["StartedAt"]
        result["checks"].append("Restart creates a new process interval; empty gauge returns to zero")
        result["status"] = "passed"
    except Exception as error:
        result["errors"].append(f"{type(error).__name__}: {error}")
    finally:
        for event in releases.values():
            event.set()
        if created:
            try:
                command("logs", name)
                command("rm", "-f", name)
            except Exception as error:
                result["errors"].append(f"cleanup: {error}")
                result["status"] = "failed"
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        write("backend-requests.json", seen)
        write("result.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

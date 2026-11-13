"""One bounded three-request deployment check, never an HPA experiment."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path("C:/Users/matvi/PycharmProjects/kubernetes-autoscaling-ai-inference")
sys.path.insert(0, str(ROOT / "bench"))
from observe import Observer
from main_protocol import recover
from check_custom_metric import check
from custom_metrics import ZeroGate, reconcile_gateway

folder = ROOT / "results/custom-metric/cluster-check-20261113-160100/requests-attempt-01"
folder.mkdir(exist_ok=False)
(folder / "inputs").mkdir()
for source in [Path(__file__), *[ROOT / "bench" / name for name in
               ("check_custom_metric.py", "custom_metrics.py", "main_protocol.py", "observe.py", "records.py", "autoscaling.py")]]:
    shutil.copyfile(source, folder / "inputs" / source.name)
(folder / "source-sha256.json").write_text(json.dumps({
    p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (folder / "inputs").iterdir()}, indent=2) + "\n")


def save(name, value):
    (folder / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


observer = Observer("ai-lab", "inference", "app=ollama")
outcome = {"status": "failed", "purpose": "three-request-functional-check", "hpa_enabled": False,
           "comparative_run": False, "errors": []}
tunnel = None
stream = None
futures = []

try:
    assert not json.loads(observer.read("get", "hpa", "-A", "-o", "json"))["items"]
    outcome["initial_quiet"] = recover(observer, folder, "ollama")
    print("Existing backend quiet gate passed", flush=True)
    before = {}
    check(observer, before)
    save("signal-before.json", before)
    assert before["signal"]["active_requests"] == 0
    identity = before["identity"]
    stream = (folder / "port-forward.txt").open("w", encoding="utf-8")
    tunnel = subprocess.Popen(["kubectl", "--context", "ai-lab", "-n", "inference", "port-forward",
                               "service/inference-gateway", ":8080", "--address=127.0.0.1"],
                              stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 20
    port = None
    while time.monotonic() < deadline:
        match = re.search(r"127\.0\.0\.1:(\d+) -> 8080", (folder / "port-forward.txt").read_text())
        if match:
            port = int(match[1])
            break
        if tunnel.poll() is not None:
            raise RuntimeError("Gateway port-forward stopped")
        time.sleep(.2)
    if not port:
        raise RuntimeError("Gateway port-forward did not open")
    payload = json.loads((ROOT / "bench/workload.json").read_text())["request"]
    payload["prompt"] = "Write a numbered list of 200 short facts about computers. Continue the list without an introduction or conclusion."
    payload["options"]["num_predict"] = 512
    save("request-settings.json", {"request": payload, "concurrency": 3, "client_timeout_seconds": 90,
                                  "reason": "Longer diagnostic answers make a five-second scrape observable",
                                  "gateway_url": f"http://127.0.0.1:{port}"})

    def request(index):
        request_id = f"chain-check-20261113:{index}"
        result = {"request_id": request_id, "started_at": time.time()}
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/generate",
                                         data=json.dumps(payload).encode(), method="POST",
                                         headers={"Content-Type": "application/json", "X-Inference-Request-ID": request_id})
            with urllib.request.urlopen(req, timeout=90) as response:
                result["http_status"] = response.status
                result["response"] = json.load(response)
            result["successful"] = result["http_status"] == 200 and result["response"].get("done") is True and bool(result["response"].get("response"))
        except Exception as error:
            result.update(successful=False, error=str(error))
        finally:
            result["finished_at"] = time.time()
            save(f"request-{index}.json", result)
        return result

    samples = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(request, index) for index in range(1, 4)]
        for index in range(24):
            record = {"received_start": time.time()}
            try:
                check(observer, record)
                if record["identity"] != identity:
                    raise ValueError("Infrastructure changed during requests")
            except Exception as error:
                record["error"] = str(error)
            save(f"signal-{index:02d}.json", record)
            samples.append(record)
            print("signal", index, record.get("signal"), record.get("error"), flush=True)
            if all(f.done() for f in futures):
                break
            time.sleep(5)
        responses = [f.result() for f in futures]
    save("responses.json", responses)
    assert all(r["successful"] for r in responses), "A diagnostic request failed"
    assert any(r.get("status") == "signal-check-passed" and r["signal"]["active_requests"] > 0 for r in samples), "No verified positive signal"
    after = max(r["finished_at"] for r in responses)
    zero = ZeroGate(after)
    for index in range(12):
        record = {}
        check(observer, record)
        save(f"zero-{index:02d}.json", record)
        if record["identity"] != identity:
            raise ValueError("Infrastructure changed after requests")
        if record["signal"]["source_at"] > after and zero.accept(record["signal"]):
            outcome["final_zero"] = record["signal"]
            break
        time.sleep(5)
    else:
        raise RuntimeError("Two fresh zero scrapes not observed")
    (folder / "quiet-after").mkdir()
    outcome["final_quiet"] = recover(observer, folder / "quiet-after", "ollama")
    print("Backend quiet gate after requests passed", flush=True)
    logs = observer.read("-n", "inference", "logs", "deployment/inference-gateway")
    (folder / "gateway.log").write_text(logs, encoding="utf-8")
    records = [json.loads(line) for line in logs.splitlines() if line.startswith("{")]
    outcome["gateway_reconciliation"] = reconcile_gateway(
        [{"event": "started", "request_id": r["request_id"]} for r in responses], records)
    outcome["values"] = [r["signal"]["active_requests"] for r in samples if r.get("status") == "signal-check-passed"]
    outcome["sample_errors"] = [r["error"] for r in samples if "error" in r]
    assert not outcome["sample_errors"], "Signal sample failures retained; review before accepting"
    outcome["status"] = "passed"
except Exception as error:
    outcome["errors"].append(f"{type(error).__name__}: {error}")
finally:
    if tunnel and tunnel.poll() is None:
        tunnel.terminate()
        tunnel.wait(timeout=10)
    if stream:
        stream.close()
    save("result.json", outcome)
print(json.dumps(outcome, indent=2), flush=True)
raise SystemExit(0 if outcome["status"] == "passed" else 1)

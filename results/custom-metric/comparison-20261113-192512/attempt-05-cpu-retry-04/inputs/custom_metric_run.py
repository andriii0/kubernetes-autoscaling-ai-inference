"""Opt-in observation and lifecycle for the separate gateway HPA experiment."""

import json
import subprocess
import time
from urllib.parse import urlencode

from autoscaling import Logs, Session, hpa_ready
from check_custom_metric import check
from custom_metric_stack import stack
from custom_metrics import (CLOCK_TOLERANCE, GATEWAY, METRIC, NAMESPACE, ZeroGate, infrastructure_identity,
                            reconcile_gateway, selector, validate_clock, validate_signal, validate_source, vector)
from records import read_jsonl, timestamp


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def subset(expected, actual):
    """Compare declared configuration, allowing Kubernetes defaulted fields."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(expected) == len(actual) and all(
            subset(a, b) for a, b in zip(expected, actual))
    return type(expected) is type(actual) and expected == actual


def configuration(objects):
    result = {}
    for obj in objects["items"]:
        key = obj["kind"] + "/" + obj["metadata"]["name"]
        result[key] = {field: obj[field] for field in
                       ("spec", "data", "binaryData", "rules", "roleRef", "subjects") if field in obj}
        result[key]["uid"] = obj["metadata"]["uid"]
    return result


def source_query():
    source = selector('namespace="inference",service="inference-gateway"')
    health = 'up{job="inference-gateway",namespace="inference",service="inference-gateway"}'
    # One evaluation for all four vectors, retaining every original identity label.
    return " or ".join(f'label_replace({expr}, "observation_field", "{name}", "__name__", ".*")'
                       for name, expr in (("source", source), ("source_time", f"timestamp({source})"),
                                          ("health", health), ("health_time", f"timestamp({health})")))


def split_source(reply):
    if reply.get("status") != "success" or reply.get("warnings") or reply.get("infos"):
        raise ValueError("source query failed or returned warnings")
    if reply.get("data", {}).get("resultType") != "vector":
        raise ValueError("source query is not a vector")
    output = []
    for field in ("source", "source_time", "health", "health_time"):
        rows = []
        for row in reply["data"]["result"]:
            labels = dict(row["metric"])
            if labels.pop("observation_field", None) == field:
                rows.append({**row, "metric": labels})
        part = {"status": "success", "data": {"resultType": "vector", "result": rows}}
        vector(part)  # Missing, duplicate and nonfinite data fail before any retry.
        output.append(part)
    return output


def replay(folder, data):
    """Recheck raw source/Adapter observations and request IDs without cluster access."""
    preflight = json.loads((folder / "custom-preflight.json").read_text(encoding="utf-8"))
    identity = preflight["identity"]
    signals = []
    for record in read_jsonl(folder / "custom-metric.jsonl"):
        if record.get("error") or infrastructure_identity(record["pods"]) != identity:
            raise ValueError("invalid custom metric observation or changed infrastructure")
        if (data["metadata"].get("extension_version") == "active-requests-comparison-v2"
                and record.get("clock_contract") != "bounded-clock-v2"):
            raise ValueError("comparison v2 requires recorded query clock bounds")
        bracket = record["brackets"][-1]
        before, after = split_source(bracket["before"]), split_source(bracket["after"])
        if record.get("clock_contract") == "bounded-clock-v2":
            for side, parts in (("before", before), ("after", after)):
                validate_clock(vector(parts[0])[1], bracket[side + "_sent_at"], bracket[side + "_received_at"])
        if any(vector(before[i])[0] != vector(after[i])[0] or vector(before[i])[2] != vector(after[i])[2]
               for i in range(4)):
            raise ValueError("accepted observation did not bracket one scrape")
        signal = validate_signal(*after, bracket["adapter"], gateway_uid=identity[GATEWAY]["uid"],
                                 received_at=record["signal"]["received_at"])
        validate_signal(*before, bracket["adapter"], gateway_uid=identity[GATEWAY]["uid"],
                        received_at=signal["received_at"])
        if signal != record["signal"]:
            raise ValueError("saved custom metric validation differs from replay")
        signals.append(signal)
    start = timestamp(data["check"]["load_window"]["started_at_utc"])
    end = start + data["metadata"]["duration_seconds"]
    prior = [s for s in signals if s["received_at"] <= start]
    after = [s for s in signals if s["received_at"] >= end]
    if not prior or not after:
        raise ValueError("custom metric observations do not cover the load window")
    covered = [prior[-1], *[s for s in signals if start < s["received_at"] < end], after[0]]
    if any(not 0 < b["received_at"] - a["received_at"] <= 10 for a, b in zip(covered, covered[1:])):
        raise ValueError("custom metric load coverage has a gap or moved backwards")
    coverage = json.loads((folder / "gateway/log-coverage.json").read_text(encoding="utf-8"))
    from autoscaling import complete_log_exit
    if set(coverage) != {identity[GATEWAY]["uid"]} or any(
            not r["complete"] or not complete_log_exit(r) for r in coverage.values()):
        raise ValueError("gateway log coverage is incomplete")
    # Allow the same timestamp rounding as the client collection's start boundary.
    gateway = reconcile_gateway(data["events"], gateway_records(folder, start - .001))
    return {"valid": True, "observations": len(covered), "gateway": gateway,
            "max_source_age_seconds": max(s["received_at"] - s["source_at"] for s in covered)}


def gateway_records(folder, after):
    access = []
    for path in (folder / "gateway/pod-logs").glob("*.log"):
        for line in path.read_text(encoding="utf-8").splitlines():
            prefix, _, body = line.partition(" ")
            if body.startswith("{") and timestamp(prefix) >= after:
                access.append(json.loads(body))
    return access


class Monitor:
    def __init__(self, observer, folder):
        self.observer, self.folder = observer, folder
        self.identity = self.config = self.signal = None
        self.logs = None
        self.started = time.time()
        self.last_received = None
        self.output = (folder / "custom-metric.jsonl").open("x", encoding="utf-8")

    def objects(self):
        return json.loads(self.observer.read("get", "-f", str(self.folder / "inputs/custom-stack/stack.json"), "-o", "json"))

    def start(self):
        record = {}
        try:
            check(self.observer, record)
            self.identity = record["identity"]
            actual = self.objects()
            by_key = {(x["kind"], x["metadata"]["name"]): x for x in actual["items"]}
            for expected in stack()["items"]:
                if not subset(expected, by_key[(expected["kind"], expected["metadata"]["name"])]):
                    raise ValueError("installed stack differs from the archived configuration")
            self.config = configuration(actual)
            save(self.folder / "custom-installed-before.json", actual)
            gateway_folder = self.folder / "gateway"
            gateway_folder.mkdir()
            self.logs = Logs(self.observer, gateway_folder, GATEWAY)
            from observe import utc_now
            self.logs.update({"time": utc_now(),
                              "pods": self.gateway_pods(record["pods_after"])})
        finally:
            save(self.folder / "custom-preflight.json", record)

    @staticmethod
    def gateway_pods(pods):
        return {"items": [p for p in pods["items"] if p["metadata"]["labels"].get("app") == GATEWAY]}

    def sample(self):
        record = {"started_at": time.time(), "clock_contract": "bounded-clock-v2", "brackets": []}
        try:
            pods = json.loads(self.observer.read("-n", NAMESPACE, "get", "pods",
                              "-l", "experiment=custom-metric-hpa", "-o", "json"))
            record["pods"] = pods
            if infrastructure_identity(pods) != self.identity:
                raise ValueError("custom metrics infrastructure identity changed")
            current = self.objects()
            if configuration(current) != self.config:
                record["changed_configuration"] = current
                raise ValueError("custom metrics infrastructure configuration changed")
            self.logs.update({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pods": self.gateway_pods(pods)})
            prefix = f"/api/v1/namespaces/{NAMESPACE}/services/http:inference-prometheus:9090/proxy/api/v1/query?"
            query = prefix + urlencode({"query": source_query()})
            for _ in range(3):
                bracket = {}
                record["brackets"].append(bracket)
                bracket["before_sent_at"] = time.time()
                bracket["before"] = json.loads(self.observer.read("get", "--raw", query))
                bracket["before_received_at"] = time.time()
                before = split_source(bracket["before"])
                validate_clock(vector(before[0])[1], bracket["before_sent_at"], bracket["before_received_at"])
                bracket["adapter_sent_at"] = time.time()
                bracket["adapter"] = json.loads(self.observer.read("get", "--raw",
                    f"/apis/custom.metrics.k8s.io/v1beta1/namespaces/{NAMESPACE}/services/{GATEWAY}/{METRIC}"))
                bracket["adapter_received_at"] = time.time()
                bracket["after_sent_at"] = time.time()
                bracket["after"] = json.loads(self.observer.read("get", "--raw", query))
                received = time.time()
                bracket["after_received_at"] = received
                after = split_source(bracket["after"])
                validate_clock(vector(after[0])[1], bracket["after_sent_at"], received)
                # Validate both sides, without substituting an observed value for the adapter.
                # If a scrape crossed the read, only retry after validating each source independently.
                same = all(vector(before[i])[0] == vector(after[i])[0] and vector(before[i])[2] == vector(after[i])[2]
                           for i in range(4))
                if same:
                    signal = validate_signal(*after, bracket["adapter"],
                                             gateway_uid=self.identity[GATEWAY]["uid"], received_at=received)
                    # Before-side freshness/health must also hold. Adapter time can follow its evaluation time.
                    validate_signal(*before, bracket["adapter"],
                                    gateway_uid=self.identity[GATEWAY]["uid"], received_at=received)
                    if self.last_received is not None and received - self.last_received > 10:
                        raise ValueError("custom metric observation gap exceeded 10 seconds")
                    self.last_received = received
                    self.signal = record["signal"] = signal
                    return signal
                # Check source validity before treating this as an acquisition race.
                for parts in (before, after):
                    validate_source(*parts, gateway_uid=self.identity[GATEWAY]["uid"], received_at=received)
                matched = False
                for parts in (before, after):
                    try:
                        validate_signal(*parts, bracket["adapter"],
                                        gateway_uid=self.identity[GATEWAY]["uid"], received_at=received)
                        matched = True
                    except ValueError as error:
                        if str(error) != "adapter value does not match the source":
                            raise
                if not matched:
                    raise ValueError("Adapter value matches neither side of the scrape boundary")
                bracket["scrape_crossed_read"] = True
            raise ValueError("cannot bracket the Adapter with one stable source scrape")
        except Exception as error:
            record["error"] = str(error)
            raise
        finally:
            record["finished_at"] = time.time()
            self.output.write(json.dumps(record, allow_nan=False) + "\n")
            self.output.flush()

    def close(self):
        try:
            if self.logs:
                self.logs.stop()
        finally:
            self.output.close()


class CustomSession(Session):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        policy = json.loads(self.manifest.read_text(encoding="utf-8"))["spec"]["metrics"][0]
        self.active_target = int(policy["object"]["target"]["averageValue"]) if policy["type"] == "Object" else None
        self.monitor = None

    def prepare(self):
        self.monitor = Monitor(self.observer, self.folder)
        self.monitor.start()
        # Do not remove an HPA installed by somebody else, even when named ollama.
        existing = json.loads(self.command("get", "hpa", "-o", "json"))
        if existing["items"]:
            raise ValueError("custom experiment requires no pre-existing HPA")
        super().prepare()

    def accept(self, sample):
        super().accept(sample)
        self.monitor.sample()

    def zero(self, collection=None):
        boundary = time.time()
        # A source clock up to one second ahead must not let a pre-boundary
        # scrape count as a new warmup/cleanup zero.
        gate = ZeroGate(boundary + CLOCK_TOLERANCE)
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if collection:
                collection.wait(collection.interval)
                with collection.lock:
                    signal = self.monitor.signal
            else:
                signal = self.monitor.sample()
            if signal and signal["source_at"] > gate.after and gate.accept(signal):
                return {"successful": True, "after": gate.after, "boundary": boundary,
                        "clock_tolerance_seconds": CLOCK_TOLERANCE, "last_signal": signal}
            if not collection:
                time.sleep(2)
        raise RuntimeError("two fresh zero scrapes were not observed within 120 seconds")

    def enable(self, collection):
        save(self.folder / "custom-zero-before-hpa.json", self.zero(collection))
        super().enable(collection)

    def is_ready(self, sample):
        from autoscaling import target_hpa
        actual = target_hpa(sample, self.deployment)
        expected = json.loads(self.manifest.read_text(encoding="utf-8"))
        if actual and not subset(expected["spec"], actual["spec"]):
            raise ValueError("applied HPA differs from the archived policy")
        # Cluster sample time precedes acquisition of the signal in this same cycle.
        if self.active_target is None:
            return super().is_ready(sample)
        signal = self.monitor.signal
        from datetime import datetime, timezone
        current = {**sample, "time": datetime.now(timezone.utc).isoformat()}
        return hpa_ready(current, self.deployment, active_target=self.active_target, signal=signal)

    def restore(self):
        result = super().restore()
        try:
            if result["successful"]:
                # Reset the observation cadence after independent Kubernetes cleanup.
                self.monitor.last_received = None
                from main_protocol import recover
                cleanup = self.folder / "custom-cleanup"
                cleanup.mkdir()
                result["backend_quiet"] = recover(self.observer, cleanup, self.container)
                result["gateway_zero"] = self.zero()
                save(self.folder / "custom-installed-after.json", self.monitor.objects())
        except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as error:
            result["successful"] = False
            result["errors"].append(str(error))
        finally:
            if self.monitor:
                try:
                    self.monitor.close()
                except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                    result["successful"] = False
                    result["errors"].append(f"gateway log shutdown: {error}")
        save(self.folder / "recovery.json", result)
        return result

    def verify_gateway(self):
        access = gateway_records(self.folder, self.monitor.started)
        result = reconcile_gateway(list(read_jsonl(self.folder / "request-events.jsonl")), access)
        save(self.folder / "gateway-check.json", result)
        return result

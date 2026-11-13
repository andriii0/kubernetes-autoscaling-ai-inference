import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import autoscaling
import check_custom_metric
import custom_metric_stack as stack
import custom_metrics as metrics
from records import timestamp
from tests.bench.fixtures import sample

NOW = timestamp("2026-11-13T12:00:00Z")
LABELS = {"namespace": "inference", "service": metrics.GATEWAY, "job": metrics.GATEWAY,
          "pod_uid": "gateway-uid", "instance": "10.0.0.1:9901", "inference_listener": "inference",
          "__name__": metrics.SOURCE}


def vector(value, labels=None, evaluated=NOW):
    return {"status": "success", "data": {"resultType": "vector",
            "result": [{"metric": copy.deepcopy(LABELS if labels is None else labels), "value": [evaluated, str(value)]}]}}


def replies(active=3):
    source_at = {k: v for k, v in LABELS.items() if k != "__name__"}
    health = {k: v for k, v in source_at.items() if k != "inference_listener"} | {"__name__": "up"}
    health_at = {k: v for k, v in health.items() if k != "__name__"}
    exposed = {"items": [{"describedObject": {"apiVersion": "v1", "kind": "Service", "namespace": "inference",
                         "name": metrics.GATEWAY}, "metricName": metrics.METRIC, "value": str(active),
                         "timestamp": "2026-11-13T12:00:00Z"}]}
    return [vector(active), vector(NOW - 3, source_at), vector(1, health), vector(NOW - 3, health_at), exposed]


def validate(values):
    return metrics.validate_signal(*values, gateway_uid="gateway-uid", received_at=NOW + 1)


def pods():
    items = []
    for name in stack.IMAGES:
        items.append({"metadata": {"name": name + "-pod", "uid": "gateway-uid" if name == metrics.GATEWAY else name + "-uid",
                                   "labels": {"app": name}},
                      "status": {"conditions": [{"type": "Ready", "status": "True"}],
                                 "containerStatuses": [{"containerID": name + "-container", "imageID": name + "-image",
                                                        "restartCount": 0}]}})
    return {"items": items}


class SignalTests(unittest.TestCase):
    def test_bounded_clock_skew_keeps_strict_source_age_and_identity(self):
        for offset in (-.8, .8):
            data = replies(0)
            for part in data[:4]:
                part['data']['result'][0]['value'][0] = NOW + offset
            # A just-written source can be ahead of Windows, but is not ahead
            # of Prometheus's evaluation time.
            for index in (1, 3):
                data[index]['data']['result'][0]['value'][1] = str(NOW + offset - .1)
            metrics.validate_clock(NOW + offset, NOW, NOW + .01)
            self.assertEqual(metrics.validate_signal(*data, gateway_uid='gateway-uid',
                                                    received_at=NOW + .01)['active_requests'], 0)
            data[1]['data']['result'][0]['value'][1] = str(NOW + offset - 10.01)
            with self.assertRaisesRegex(ValueError, 'source sample'):
                metrics.validate_signal(*data, gateway_uid='gateway-uid', received_at=NOW + .01)
        for evaluated, sent, received in ((NOW + 1.1, NOW, NOW), (NOW - 1.1, NOW, NOW),
                                          (NOW, NOW + 1, NOW), (float('nan'), NOW, NOW)):
            with self.assertRaisesRegex(ValueError, 'clocks differ'):
                metrics.validate_clock(evaluated, sent, received)

    def test_adapter_core_group_spelling_keeps_object_identity_strict(self):
        for version in ("v1", "/v1"):
            data = replies(0)
            data[-1]["items"][0]["describedObject"]["apiVersion"] = version
            self.assertEqual(validate(data)["active_requests"], 0)
        for field, value in (("apiVersion", "apps/v1"), ("apiVersion", "v2"),
                             ("apiVersion", ""), ("kind", "Deployment"),
                             ("namespace", "other"), ("name", "ollama")):
            data = replies(0)
            data[-1]["items"][0]["describedObject"][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, "another object"):
                validate(data)

    def test_valid_three_two_zero_and_fresh_milli_adapter_value(self):
        for active in (3, 2, 0):
            data = replies(active)
            data[-1]["items"][0]["value"] = str(active * 1000) + "m"
            result = validate(data)
            self.assertEqual(result["active_requests"], active)
            self.assertEqual(result["source_at"], NOW - 3)
            self.assertEqual(result["received_at"], NOW + 1)

    def test_missing_duplicate_and_bad_value_are_never_zero(self):
        for bad in ([], [vector(1)["data"]["result"][0]] * 2):
            for index in range(4):
                with self.subTest(index=index, size=len(bad)):
                    data = replies()
                    data[index]["data"]["result"] = bad
                    with self.assertRaisesRegex(ValueError, "exactly one"):
                        validate(data)
        for value in ("NaN", "+Inf", "-Inf", "-1", "invalid", ".5"):
            data = replies()
            data[0]["data"]["result"][0]["value"][1] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(data)

    def test_fresh_response_does_not_hide_old_source_or_health(self):
        for index in (1, 3):
            for source_at in (NOW - 11, NOW + 1):
                data = replies()
                data[index]["data"]["result"][0]["value"][1] = str(source_at)
                with self.subTest(index=index, source_at=source_at), self.assertRaisesRegex(ValueError, "source sample"):
                    validate(data)

    def test_mismatched_labels_query_failure_and_unhealthy_target(self):
        for change in ("old-pod", "listener", "instance", "health", "timestamp-series", "error", "warning",
                       "different-evaluation", "wrong-object", "wrong-value", "wrong-metric", "stale-adapter"):
            data = replies()
            if change == "old-pod": data[0]["data"]["result"][0]["metric"]["pod_uid"] = "old"
            if change == "listener": data[0]["data"]["result"][0]["metric"]["inference_listener"] = "admin"
            if change == "instance": data[2]["data"]["result"][0]["metric"]["instance"] = "another"
            if change == "health": data[2]["data"]["result"][0]["value"][1] = "0"
            if change == "timestamp-series": data[1]["data"]["result"][0]["metric"]["extra"] = "different-series"
            if change == "error": data[0]["status"] = "error"
            if change == "warning": data[0]["warnings"] = ["partial response"]
            if change == "different-evaluation": data[1]["data"]["result"][0]["value"][0] -= 1
            if change == "wrong-object": data[4]["items"][0]["describedObject"]["name"] = "ollama"
            if change == "wrong-value": data[4]["items"][0]["value"] = "2000m"
            if change == "wrong-metric": data[4]["items"][0]["metricName"] = "another"
            if change == "stale-adapter": data[4]["items"][0]["timestamp"] = "2026-11-13T11:59:00Z"
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(data)

    def test_zero_gate_requires_new_scrapes_after_warmup(self):
        gate = metrics.ZeroGate(after=100)
        self.assertFalse(gate.accept({"source_at": 101, "active_requests": 0}))
        self.assertFalse(gate.accept({"source_at": 101, "active_requests": 0}))
        self.assertFalse(gate.accept({"source_at": 106, "active_requests": 1}))
        self.assertFalse(gate.accept({"source_at": 111, "active_requests": 0}))
        self.assertTrue(gate.accept({"source_at": 116, "active_requests": 0}))
        for at in (99, 110):
            with self.assertRaises(ValueError):
                gate.accept({"source_at": at, "active_requests": 0})

    def test_quantities_reject_invalid_numbers(self):
        for invalid in ("NaN", "Inf", "-1", "1Gi", None, True, "9" * 400):
            with self.subTest(invalid=str(invalid)[:10]), self.assertRaises(ValueError):
                metrics.quantity(invalid)

    def test_infrastructure_missing_duplicate_restart_unready_and_replacement(self):
        original = metrics.infrastructure_identity(pods())
        replaced = pods()
        replaced["items"][0]["metadata"]["uid"] = "replacement"
        self.assertNotEqual(original, metrics.infrastructure_identity(replaced))
        for change in ("missing", "duplicate", "restart", "unready", "terminating", "missing-id"):
            data = pods()
            pod = data["items"][0]
            if change == "missing": data["items"].pop()
            if change == "duplicate": data["items"].append(copy.deepcopy(pod))
            if change == "restart": pod["status"]["containerStatuses"][0]["restartCount"] = 1
            if change == "unready": pod["status"]["conditions"][0]["status"] = "False"
            if change == "terminating": pod["metadata"]["deletionTimestamp"] = "now"
            if change == "missing-id": pod["status"]["containerStatuses"][0]["containerID"] = ""
            with self.subTest(change=change), self.assertRaises(ValueError):
                metrics.infrastructure_identity(data)

    def test_object_hpa_needs_its_spec_current_value_and_fresh_source(self):
        current = sample("2026-11-13T12:00:01Z")
        hpa = stack.hpa("active", 2)
        hpa["status"] = {"currentReplicas": 1, "desiredReplicas": 1,
                         "conditions": [{"type": "ScalingActive", "status": "True"}],
                         "currentMetrics": [{"type": "Object", "object": {
                             "describedObject": hpa["spec"]["metrics"][0]["object"]["describedObject"],
                             "metric": {"name": metrics.METRIC}, "current": {"averageValue": "0"}}}]}
        current["hpa"]["items"] = [hpa]
        signal = validate(replies(0))
        self.assertTrue(autoscaling.hpa_ready(current, "ollama", active_target=2, signal=signal))
        self.assertFalse(autoscaling.hpa_ready(current, "ollama"))
        self.assertFalse(autoscaling.hpa_ready(current, "ollama", active_target=1, signal=signal))
        self.assertFalse(autoscaling.hpa_ready(current, "ollama", active_target=2))
        for change in ("stale", "status", "inactive", "mixed", "desired"):
            data, evidence = copy.deepcopy(current), copy.deepcopy(signal)
            status = data["hpa"]["items"][0]["status"]
            if change == "stale": evidence["source_at"] = NOW - 11
            if change == "status": status["currentMetrics"][0]["object"]["current"]["averageValue"] = "1"
            if change == "inactive": status["conditions"][0]["status"] = "False"
            if change == "mixed": data["hpa"]["items"][0]["spec"]["metrics"].append(stack.hpa("cpu")["spec"]["metrics"][0])
            if change == "desired": status["desiredReplicas"] = 2
            with self.subTest(change=change):
                self.assertFalse(autoscaling.hpa_ready(data, "ollama", active_target=2, signal=evidence))


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.events = [{"event": "started", "request_id": "run:1"}, {"event": "started", "request_id": "run:2"}]
        self.logs = [{"request_id": r["request_id"], "method": "POST", "path": "/api/generate",
                      "upstream_cluster": "ollama", "attempts": "1"} for r in self.events]

    def test_exact_match_excludes_warmup_and_keeps_failures(self):
        self.logs[1].update(status=503, flags="UF")
        report = metrics.reconcile_gateway(self.events, self.logs + [{"request_id": "-"}])
        self.assertEqual(report["matched"], 2)

    def test_missing_duplicates_retries_wrong_route_and_unexpected_ids_fail(self):
        for change in ("missing", "duplicate", "retry", "route", "cluster", "unknown"):
            logs = copy.deepcopy(self.logs)
            if change == "missing": logs.pop()
            if change == "duplicate": logs.append(copy.deepcopy(logs[0]))
            if change == "retry": logs[0]["attempts"] = "2"
            if change == "route": logs[0]["path"] = "/health"
            if change == "cluster": logs[0]["upstream_cluster"] = "other"
            if change == "unknown": logs.append({"request_id": "other-run:1"})
            with self.subTest(change=change), self.assertRaises(ValueError):
                metrics.reconcile_gateway(self.events, logs)


class StackTests(unittest.TestCase):
    def test_both_policies_have_same_capacity_and_behavior(self):
        cpu = stack.hpa("cpu")["spec"]
        for target in (1, 2):
            custom = stack.hpa("active", target)["spec"]
            self.assertEqual({k: v for k, v in cpu.items() if k != "metrics"},
                             {k: v for k, v in custom.items() if k != "metrics"})
            self.assertEqual(custom["metrics"][0]["object"]["target"]["type"], "AverageValue")
        for policy, target in (("active", 3), ("cpu", 2), ("unknown", None)):
            with self.assertRaises(ValueError):
                stack.hpa(policy, target)

    def test_stack_separates_admin_health_and_backend_and_contains_no_hpa(self):
        objects = stack.stack()["items"]
        self.assertFalse(any(o["kind"] == "HorizontalPodAutoscaler" for o in objects))
        services = {o["metadata"]["name"]: o for o in objects if o["kind"] == "Service"}
        self.assertEqual(services[metrics.GATEWAY]["spec"]["ports"], [{"name": "http", "port": 8080, "targetPort": "http"}])
        deployments = [o for o in objects if o["kind"] == "Deployment"]
        self.assertEqual(len(deployments), 3)
        self.assertTrue(all(o["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"] for o in deployments))
        envoy = stack.envoy_config()
        cluster = envoy["static_resources"]["clusters"][0]
        self.assertEqual(cluster["name"], "ollama")
        protocol = next(iter(cluster["typed_extension_protocol_options"].values()))
        self.assertEqual(protocol["common_http_protocol_options"]["max_requests_per_connection"], 1)
        hcm = envoy["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]
        route = hcm["route_config"]["virtual_hosts"][0]["routes"][0]
        self.assertEqual(route["route"]["timeout"], "0s")
        self.assertNotIn("retry_policy", route["route"])
        self.assertEqual(route["match"]["path"], "/api/generate")
        self.assertEqual(hcm["stream_idle_timeout"], "0s")
        apis = [o["metadata"]["name"] for o in objects if o["kind"] == "APIService"]
        self.assertEqual(apis, ["v1beta1.custom.metrics.k8s.io"])

    def test_bundle_is_deterministic_hashed_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "one", Path(temp) / "two"
            record = stack.render(first)
            self.assertEqual(record, stack.render(second))
            for name, expected in record["sha256"].items():
                self.assertEqual(hashlib.sha256((first / name).read_bytes()).hexdigest(), expected)
            with self.assertRaises(FileExistsError):
                stack.render(first)
            self.assertFalse(record["live_validation"])


class ReadOnlyCheckTests(unittest.TestCase):
    def observer(self, *, replace=False):
        queries = replies(0)
        api = {"spec": {"service": {"name": "inference-metrics-adapter", "namespace": "inference"}},
               "status": {"conditions": [{"type": "Available", "status": "True"}]}}
        final = pods()
        if replace:
            final["items"][0]["metadata"]["uid"] = "changed"
        values = [{"gitVersion": "fixture"}, pods(), api,
                  {"status": "success", "data": {"resultType": "scalar", "result": [NOW, str(NOW)]}},
                  *queries, final]
        observer = Mock()
        observer.read.side_effect = [json.dumps(value) for value in values]
        return observer

    def test_check_reads_only_and_detects_identity_change(self):
        for replace in (False, True):
            observer, record = self.observer(replace=replace), {}
            with patch.object(check_custom_metric.time, "time", return_value=NOW):
                if replace:
                    with self.assertRaisesRegex(ValueError, "changed"):
                        check_custom_metric.check(observer, record)
                else:
                    check_custom_metric.check(observer, record)
                    self.assertEqual(record["status"], "signal-check-passed")
            for call in observer.read.call_args_list:
                self.assertIn("get", call.args)
                self.assertFalse({"apply", "delete", "scale", "patch"} & set(call.args))

    def test_unavailable_cluster_saves_failure_and_does_not_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "check"
            observer = Mock()
            observer.read.side_effect = RuntimeError("API offline")
            with patch.object(check_custom_metric, "Observer", return_value=observer):
                self.assertEqual(check_custom_metric.main(["--output-dir", str(folder)]), 1)
            record = json.loads((folder / "check.json").read_text())
            self.assertEqual(record["errors"], ["API offline"])
            self.assertFalse(record["measured_load_started"])
            observer.read.assert_called_once()


if __name__ == "__main__":
    unittest.main()

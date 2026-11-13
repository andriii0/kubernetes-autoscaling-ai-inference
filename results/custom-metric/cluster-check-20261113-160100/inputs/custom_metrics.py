"""Strict, read-only contracts for the separate active-request HPA extension."""

from collections import Counter
from decimal import Decimal, InvalidOperation
import math
import re

METRIC = "inference_gateway_active_requests"
SOURCE = "envoy_http_downstream_rq_active"
GATEWAY = "inference-gateway"
NAMESPACE = "inference"
MAX_AGE = 10
LISTENER = "inference"


def selector(matchers=""):
    labels = ['job="inference-gateway"', 'inference_listener="inference"']
    if matchers:
        labels.append(matchers)
    return SOURCE + "{" + ",".join(labels) + "}"


def adapter_query(matchers="<<.LabelMatchers>>"):
    """Return no series on bad input. Never synthesize zero or average gateways."""
    source = selector(matchers)
    healthy = 'up{job="inference-gateway"' + ("," + matchers if matchers else "") + "}"
    identity = "namespace,service,pod_uid,instance"
    # Count the unfiltered vectors too: filtering one bad duplicate must not
    # leave a plausible single value behind. A fresh query time is not the
    # original scrape time; timestamp() explicitly tests the source sample.
    valid = (
        f"({source} >= 0 and {source} < +Inf)"
        f" and (time() - timestamp({source}) >= 0)"
        f" and (time() - timestamp({source}) <= {MAX_AGE})"
        f" and on ({identity}) ({healthy} == 1"
        f" and (time() - timestamp({healthy}) >= 0)"
        f" and (time() - timestamp({healthy}) <= {MAX_AGE}))"
    )
    return (
        f"sum by (namespace,service) ({valid})"
        f" and on (namespace,service) (count by (namespace,service) ({source}) == 1)"
        f" and on (namespace,service) (count by (namespace,service) ({healthy}) == 1)"
    )


def quantity(value):
    """Parse the nonnegative decimal/milli quantities returned by this metric."""
    if not isinstance(value, str) or not re.fullmatch(r"(?:\d+(?:\.\d*)?|\.\d+)(?:m)?", value):
        raise ValueError("invalid active-request quantity")
    try:
        result = Decimal(value[:-1]) / 1000 if value.endswith("m") else Decimal(value)
    except InvalidOperation as error:
        raise ValueError("invalid active-request quantity") from error
    if not result.is_finite() or result < 0:
        raise ValueError("invalid active-request quantity")
    converted = float(result)
    if not math.isfinite(converted):
        raise ValueError("active-request quantity is too large")
    return converted


def vector(reply):
    if reply.get("status") != "success" or reply.get("warnings") or reply.get("infos"):
        raise ValueError("Prometheus query failed or returned warnings")
    data = reply.get("data", {})
    if data.get("resultType") != "vector" or not isinstance(data.get("result"), list):
        raise ValueError("expected a Prometheus instant vector")
    rows = data["result"]
    if len(rows) != 1:
        raise ValueError("expected exactly one metric series")
    row = rows[0]
    point = row.get("value", [])
    if len(point) != 2:
        raise ValueError("missing metric value or evaluation timestamp")
    try:
        evaluation, value = float(point[0]), float(point[1])
    except (TypeError, ValueError) as error:
        raise ValueError("invalid metric sample") from error
    if not math.isfinite(evaluation) or not math.isfinite(value) or value < 0:
        raise ValueError("non-finite or negative metric sample")
    return row.get("metric", {}), evaluation, value


def _labels(labels, gateway_uid):
    expected = {"namespace": NAMESPACE, "service": GATEWAY, "job": GATEWAY, "pod_uid": gateway_uid}
    if not gateway_uid or any(labels.get(key) != val for key, val in expected.items()):
        raise ValueError("metric does not belong to the current gateway")
    if not labels.get("instance"):
        raise ValueError("metric has no scrape instance")


def validate_signal(source, source_time, health, health_time, exposed, *, gateway_uid, received_at):
    """Check four queries at one evaluation time and the adapter API response.

    timestamp(selector) supplies source_time/health_time. The timestamp in an
    instant-query result is the evaluation time and cannot establish freshness.
    """
    values = [vector(reply) for reply in (source, source_time, health, health_time)]
    for labels, evaluated, _ in values:
        _labels(labels, gateway_uid)
        if not math.isfinite(received_at) or not 0 <= received_at - evaluated <= MAX_AGE:
            raise ValueError("query evaluation is stale or ahead of the observation clock")
    evaluations = {entry[1] for entry in values}
    if len(evaluations) != 1:
        raise ValueError("metric queries used different evaluation times")
    labels, evaluated, active = values[0]
    if not active.is_integer():
        raise ValueError("active-request gauge is not a whole request count")
    if labels.get("inference_listener") != LISTENER or labels.get("__name__") != SOURCE:
        raise ValueError("wrong source metric or listener")
    identity = lambda lab: {key: val for key, val in lab.items() if key != "__name__"}
    if identity(values[1][0]) != identity(labels):
        raise ValueError("source timestamp belongs to another series")
    if values[2][0].get("__name__") != "up" or identity(values[2][0]) != identity(values[3][0]):
        raise ValueError("health timestamp belongs to another series")
    if any(values[2][0].get(key) != labels.get(key) for key in ("instance", "pod_uid", "namespace", "service")):
        raise ValueError("health sample belongs to another scrape target")
    if values[2][2] != 1:
        raise ValueError("gateway scrape target is unhealthy")
    for source_at in (values[1][2], values[3][2]):
        if not 0 <= evaluated - source_at <= MAX_AGE or not 0 <= received_at - source_at <= MAX_AGE:
            raise ValueError("source sample is stale or ahead of the observation clock")
    items = exposed.get("items", [])
    if len(items) != 1:
        raise ValueError("expected exactly one adapter metric")
    item = items[0]
    obj = item.get("describedObject", {})
    if (obj.get("apiVersion"), obj.get("kind"), obj.get("namespace"), obj.get("name")) != (
            "v1", "Service", NAMESPACE, GATEWAY):
        raise ValueError("adapter metric belongs to another object")
    if item.get("metricName") != METRIC or quantity(item.get("value")) != active:
        raise ValueError("adapter value does not match the source")
    # An old adapter response is invalid too; it cannot establish source age.
    from records import timestamp
    adapter_at = timestamp(item.get("timestamp", ""))
    if not 0 <= received_at - adapter_at <= MAX_AGE:
        raise ValueError("adapter response timestamp is stale or in the future")
    return {"active_requests": active, "source_at": values[1][2], "health_at": values[3][2],
            "evaluated_at": evaluated, "received_at": received_at, "adapter_at": adapter_at,
            "gateway_uid": gateway_uid, "instance": labels["instance"]}


def object_metric_ready(hpa, target, signal, observed_at):
    """An Object HPA needs fresh source proof as well as a numeric status."""
    if type(target) is not int or target not in (1, 2) or not signal:
        return False
    try:
        if any(not 0 <= observed_at - signal[key] <= MAX_AGE
               for key in ("source_at", "health_at", "received_at", "adapter_at")):
            return False
        expected_object = {"apiVersion": "v1", "kind": "Service", "name": GATEWAY}
        expected = {"type": "Object", "object": {"describedObject": expected_object, "metric": {"name": METRIC},
                    "target": {"type": "AverageValue", "averageValue": str(target)}}}
        if hpa.get("spec", {}).get("metrics") != [expected]:
            return False
        metrics = hpa.get("status", {}).get("currentMetrics", [])
        if len(metrics) != 1 or metrics[0].get("type") != "Object":
            return False
        obj = metrics[0].get("object", {})
        return (obj.get("describedObject") == expected_object and obj.get("metric") == {"name": METRIC}
                and quantity(obj.get("current", {}).get("averageValue")) == signal["active_requests"])
    except (KeyError, TypeError, ValueError):
        return False


class ZeroGate:
    """Require two distinct source scrapes after the warmup/cleanup boundary."""

    def __init__(self, after):
        self.after = after
        self.previous = None
        self.zeros = 0

    def accept(self, signal):
        at = signal["source_at"]
        if at <= self.after or self.previous is not None and at < self.previous:
            raise ValueError("source sample precedes the zero gate or moved backwards")
        if at == self.previous:
            return False
        self.previous = at
        self.zeros = self.zeros + 1 if signal["active_requests"] == 0 else 0
        return self.zeros >= 2


def infrastructure_identity(pods):
    """One Ready, non-restarted container per component; call again each sample."""
    result = {}
    for name in (GATEWAY, "inference-prometheus", "inference-metrics-adapter"):
        selected = [p for p in pods.get("items", []) if p.get("metadata", {}).get("labels", {}).get("app") == name]
        if len(selected) != 1:
            raise ValueError(f"expected one {name} pod")
        pod = selected[0]
        from autoscaling import ready
        statuses = pod.get("status", {}).get("containerStatuses", [])
        if not ready(pod) or len(statuses) != 1:
            raise ValueError(f"{name} is not Ready with one container")
        status = statuses[0]
        if status.get("restartCount") != 0 or not status.get("containerID") or not status.get("imageID"):
            raise ValueError(f"{name} restarted or has incomplete identity")
        result[name] = {"uid": pod["metadata"]["uid"], "container_id": status["containerID"],
                        "image_id": status["imageID"]}
    return result


def reconcile_gateway(events, access):
    """One measured ID -> one gateway record; warmup has no measured ID."""
    ids = [e["request_id"] for e in events if e.get("event") == "started"]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("client starts are missing or duplicated")
    expected = set(ids)
    if any(r.get("request_id") not in expected and r.get("request_id") not in (None, "", "-") for r in access):
        raise ValueError("gateway received an unexpected request ID")
    measured = [r for r in access if r.get("request_id") in expected]
    counts = Counter(r["request_id"] for r in measured)
    if set(counts) != expected or any(count != 1 for count in counts.values()):
        raise ValueError("gateway records do not match every client start exactly once")
    for record in measured:
        if record.get("method") != "POST" or record.get("path") != "/api/generate":
            raise ValueError("measured request took a different gateway route")
        if record.get("upstream_cluster") != "ollama":
            raise ValueError("measured request did not select the Ollama backend")
        # Zero attempts can be an explained upstream failure, but no retries.
        if str(record.get("attempts")) not in ("0", "1"):
            raise ValueError("gateway retried a measured request or omitted its attempt count")
    return {"matched": len(measured), "complete": True,
            "scope": "Gateway routing only; native Ollama reconciliation is still required"}

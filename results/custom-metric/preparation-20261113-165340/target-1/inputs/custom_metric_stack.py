"""Render isolated custom-metric infrastructure; never apply it or launch load."""

import argparse
import hashlib
import json
from pathlib import Path

from custom_metrics import GATEWAY, METRIC, NAMESPACE, adapter_query, selector

# Explicit candidate versions, not a claim about the newest releases.
# Server compatibility and resolved image IDs must pass live preflight.
IMAGES = {
    GATEWAY: "envoyproxy/envoy:v1.35.0",
    "inference-prometheus": "prom/prometheus:v3.5.0",
    "inference-metrics-adapter": "registry.k8s.io/prometheus-adapter/prometheus-adapter:v0.12.0",
}
RESOURCES = {
    GATEWAY: {"requests": {"cpu": "100m", "memory": "64Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}},
    "inference-prometheus": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}},
    "inference-metrics-adapter": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}},
}


def address(host, port):
    return {"socket_address": {"address": host, "port_value": port}}


def envoy_config():
    hcm = {
        "@type": "type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager",
        "stat_prefix": "inference", "codec_type": "HTTP1", "generate_request_id": False,
        "stream_idle_timeout": "0s", "request_timeout": "0s",
        "route_config": {"name": "inference", "virtual_hosts": [{
            "name": "inference", "domains": ["*"], "routes": [{
                "match": {"path": "/api/generate", "headers": [{"name": ":method", "string_match": {"exact": "POST"}}]},
                "route": {"cluster": "ollama", "timeout": "0s", "idle_timeout": "0s"},
            }]}]},
        "http_filters": [{"name": "envoy.filters.http.router", "typed_config": {
            "@type": "type.googleapis.com/envoy.extensions.filters.http.router.v3.Router"}}],
        "access_log": [{"name": "envoy.access_loggers.stdout", "typed_config": {
            "@type": "type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog",
            "log_format": {"json_format": {
                "started_at": "%START_TIME%", "request_id": "%REQ(X-INFERENCE-REQUEST-ID)%",
                "method": "%REQ(:METHOD)%", "path": "%REQ(:PATH)%",
                "status": "%RESPONSE_CODE%", "duration_ms": "%DURATION%",
                "flags": "%RESPONSE_FLAGS%", "details": "%RESPONSE_CODE_DETAILS%",
                "upstream_cluster": "%UPSTREAM_CLUSTER%", "upstream_host": "%UPSTREAM_HOST%",
                "attempts": "%UPSTREAM_REQUEST_ATTEMPT_COUNT%",
                "transport_failure": "%UPSTREAM_TRANSPORT_FAILURE_REASON%",
            }},
        }}],
    }
    return {
        "admin": {"address": address("0.0.0.0", 9901)},
        "stats_config": {"use_all_default_tags": False, "stats_tags": [
            {"tag_name": "inference_listener", "regex": r"^http\.((inference)\.)"}]},
        "static_resources": {
            "listeners": [{"name": "generation", "address": address("0.0.0.0", 8080),
                           "filter_chains": [{"filters": [{"name": "envoy.filters.network.http_connection_manager",
                                                          "typed_config": hcm}]}]}],
            "clusters": [{
                "name": "ollama", "type": "STRICT_DNS", "connect_timeout": "30s",
                "load_assignment": {"cluster_name": "ollama", "endpoints": [{"lb_endpoints": [
                    {"endpoint": {"address": address("ollama.inference.svc.cluster.local", 11434)}}]}]},
                "typed_extension_protocol_options": {"envoy.extensions.upstreams.http.v3.HttpProtocolOptions": {
                    "@type": "type.googleapis.com/envoy.extensions.upstreams.http.v3.HttpProtocolOptions",
                    "common_http_protocol_options": {"max_requests_per_connection": 1},
                    "explicit_http_config": {"http_protocol_options": {}},
                }},
            }],
        },
    }


def prometheus_config():
    return {"global": {"scrape_interval": "5s", "scrape_timeout": "4s", "evaluation_interval": "5s"},
            "scrape_configs": [{
                "job_name": GATEWAY, "metrics_path": "/stats/prometheus",
                "kubernetes_sd_configs": [{"role": "pod", "namespaces": {"names": [NAMESPACE]}}],
                "relabel_configs": [
                    {"source_labels": ["__meta_kubernetes_pod_label_app"], "regex": GATEWAY, "action": "keep"},
                    {"source_labels": ["__meta_kubernetes_pod_container_port_name"], "regex": "admin", "action": "keep"},
                    {"source_labels": ["__meta_kubernetes_pod_phase"], "regex": "Running", "action": "keep"},
                    {"source_labels": ["__meta_kubernetes_namespace"], "target_label": "namespace"},
                    {"source_labels": ["__meta_kubernetes_pod_uid"], "target_label": "pod_uid"},
                    {"target_label": "service", "replacement": GATEWAY},
                ],
            }]}


def adapter_config():
    return {"rules": [{"seriesQuery": selector('namespace="inference",service="inference-gateway"'),
                       "resources": {"overrides": {"namespace": {"resource": "namespace"},
                                                   "service": {"resource": "service"}}},
                       "name": {"matches": "^envoy_http_downstream_rq_active$", "as": METRIC},
                       "metricsQuery": adapter_query()}]}


def hpa(policy, target=None):
    if policy not in ("cpu", "active") or policy == "active" and target not in (1, 2) or policy == "cpu" and target is not None:
        raise ValueError("choose cpu, or active with candidate target 1 or 2")
    metric = ({"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 60}}}
              if policy == "cpu" else {"type": "Object", "object": {
                  "describedObject": {"apiVersion": "v1", "kind": "Service", "name": GATEWAY},
                  "metric": {"name": METRIC}, "target": {"type": "AverageValue", "averageValue": str(target)}}})
    return {"apiVersion": "autoscaling/v2", "kind": "HorizontalPodAutoscaler",
            "metadata": {"name": "ollama", "namespace": NAMESPACE},
            "spec": {"scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": "ollama"},
                     "minReplicas": 1, "maxReplicas": 3, "metrics": [metric],
                     "behavior": {"scaleDown": {"stabilizationWindowSeconds": 300}}}}


def resource(kind, name, namespace=NAMESPACE, **fields):
    api = ("apps/v1" if kind == "Deployment" else "rbac.authorization.k8s.io/v1" if kind in (
        "Role", "RoleBinding", "ClusterRole", "ClusterRoleBinding") else
        "apiregistration.k8s.io/v1" if kind == "APIService" else "v1")
    meta = {"name": name, "labels": {"experiment": "custom-metric-hpa"}}
    if namespace:
        meta["namespace"] = namespace
    return {"apiVersion": api, "kind": kind, "metadata": meta, **fields}


def deployment(name, config_file, args, ports, probe, *, storage=False, certs=False):
    container = {"name": name, "image": IMAGES[name], "imagePullPolicy": "IfNotPresent",
                 "args": args, "ports": ports, "resources": RESOURCES[name],
                 "readinessProbe": probe, "volumeMounts": [{"name": "config", "mountPath": "/etc/inference", "readOnly": True}]}
    volumes = [{"name": "config", "configMap": {"name": name, "items": [{"key": config_file, "path": config_file}]}}]
    if storage or certs:
        mount = "/prometheus" if storage else "/var/run/serving-cert"
        volumes.append({"name": "data", "emptyDir": {"sizeLimit": "256Mi" if storage else "16Mi"}})
        container["volumeMounts"].append({"name": "data", "mountPath": mount})
    return resource("Deployment", name, spec={
        "replicas": 1, "strategy": {"type": "Recreate"}, "selector": {"matchLabels": {"app": name}},
        "template": {"metadata": {"labels": {"app": name, "experiment": "custom-metric-hpa"}},
                     "spec": {"serviceAccountName": name, "automountServiceAccountToken": name != GATEWAY,
                              "containers": [container], "volumes": volumes}}})


def stack():
    objects = []
    for name, filename, config in (
            (GATEWAY, "envoy.json", envoy_config()), ("inference-prometheus", "prometheus.json", prometheus_config()),
            ("inference-metrics-adapter", "adapter.json", adapter_config())):
        objects.extend([resource("ServiceAccount", name),
                        resource("ConfigMap", name, data={filename: json.dumps(config, indent=2) + "\n"})])
    objects.extend([
        deployment(GATEWAY, "envoy.json", ["-c", "/etc/inference/envoy.json", "--concurrency", "1"],
                   [{"name": "http", "containerPort": 8080}, {"name": "admin", "containerPort": 9901}],
                   {"tcpSocket": {"port": "http"}, "periodSeconds": 5}),
        deployment("inference-prometheus", "prometheus.json",
                   ["--config.file=/etc/inference/prometheus.json", "--storage.tsdb.path=/prometheus",
                    "--storage.tsdb.retention.time=6h", "--storage.tsdb.retention.size=128MB"],
                   [{"name": "http", "containerPort": 9090}],
                   {"httpGet": {"path": "/-/ready", "port": "http"}, "periodSeconds": 5}, storage=True),
        deployment("inference-metrics-adapter", "adapter.json",
                   ["--config=/etc/inference/adapter.json", "--cert-dir=/var/run/serving-cert", "--secure-port=6443",
                    "--prometheus-url=http://inference-prometheus.inference.svc:9090",
                    "--metrics-relist-interval=5s", "--metrics-max-age=30s"],
                   [{"name": "https", "containerPort": 6443}],
                   {"httpGet": {"path": "/readyz", "port": "https", "scheme": "HTTPS"}, "periodSeconds": 5}, certs=True),
        resource("Service", GATEWAY, spec={"type": "NodePort", "selector": {"app": GATEWAY},
                                           "ports": [{"name": "http", "port": 8080, "targetPort": "http"}]}),
        resource("Service", "inference-prometheus", spec={"selector": {"app": "inference-prometheus"},
                    "ports": [{"name": "http", "port": 9090, "targetPort": "http"}]}),
        resource("Service", "inference-metrics-adapter", spec={"selector": {"app": "inference-metrics-adapter"},
                    "ports": [{"name": "https", "port": 443, "targetPort": "https"}]}),
        resource("Role", "inference-prometheus", rules=[{"apiGroups": [""], "resources": ["pods"], "verbs": ["get", "list", "watch"]}]),
        resource("RoleBinding", "inference-prometheus", roleRef={"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "inference-prometheus"},
                 subjects=[{"kind": "ServiceAccount", "name": "inference-prometheus", "namespace": NAMESPACE}]),
        resource("ClusterRole", "inference-metrics-adapter", namespace=None,
                 rules=[{"apiGroups": [""], "resources": ["namespaces", "services"], "verbs": ["get", "list", "watch"]}]),
    ])
    for name, role in (("inference-metrics-adapter", "inference-metrics-adapter"),
                       ("inference-metrics-auth", "system:auth-delegator")):
        objects.append(resource("ClusterRoleBinding", name, namespace=None,
                                roleRef={"apiGroup": "rbac.authorization.k8s.io", "kind": "ClusterRole", "name": role},
                                subjects=[{"kind": "ServiceAccount", "name": "inference-metrics-adapter", "namespace": NAMESPACE}]))
    objects.extend([
        resource("RoleBinding", "inference-metrics-auth-reader", namespace="kube-system",
                 roleRef={"apiGroup": "rbac.authorization.k8s.io", "kind": "Role", "name": "extension-apiserver-authentication-reader"},
                 subjects=[{"kind": "ServiceAccount", "name": "inference-metrics-adapter", "namespace": NAMESPACE}]),
        resource("ClusterRole", "inference-custom-metric-reader", namespace=None,
                 rules=[{"apiGroups": ["custom.metrics.k8s.io"], "resources": ["services/" + METRIC], "verbs": ["get"]}]),
        resource("ClusterRoleBinding", "inference-hpa-metric-reader", namespace=None,
                 roleRef={"apiGroup": "rbac.authorization.k8s.io", "kind": "ClusterRole", "name": "inference-custom-metric-reader"},
                 subjects=[{"kind": "ServiceAccount", "name": "horizontal-pod-autoscaler", "namespace": "kube-system"}]),
        resource("APIService", "v1beta1.custom.metrics.k8s.io", namespace=None,
                 spec={"group": "custom.metrics.k8s.io", "version": "v1beta1", "groupPriorityMinimum": 100,
                       "versionPriority": 100, "insecureSkipTLSVerify": True,
                       "service": {"name": "inference-metrics-adapter", "namespace": NAMESPACE}}),
    ])
    return {"apiVersion": "v1", "kind": "List", "items": objects}


def render(folder):
    """New directory only. No cluster access, apply, overwrite, or HPA activation."""
    artifacts = {"stack.json": stack(), "hpa-cpu.json": hpa("cpu"),
                 "hpa-active-1.json": hpa("active", 1), "hpa-active-2.json": hpa("active", 2),
                 "envoy.json": envoy_config(), "prometheus.json": prometheus_config(), "adapter.json": adapter_config()}
    folder.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, value in artifacts.items():
        content = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        (folder / name).write_bytes(content)
        hashes[name] = hashlib.sha256(content).hexdigest()
    record = {"status": "rendered-unverified", "live_validation": False, "images": IMAGES,
              "sha256": hashes, "source_sha256": {
                  name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                  for name in ("custom_metric_stack.py", "custom_metrics.py")}}
    (folder / "bundle.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        render(args.output_dir.resolve())
    except (OSError, ValueError) as error:
        parser.exit(1, f"Cannot render new bundle: {error}\n")
    print("Rendered candidate stack and separate HPA manifests. Live validation and load are not started.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

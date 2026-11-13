#!/usr/bin/env python3
"""Render both environments and enforce delivery invariants. No Kubernetes access needed."""
import argparse
import json
import re
import subprocess
from pathlib import Path
import yaml
from common import ROOT, digest, production_ready, site


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(resources, environment, release=False):
    objects = {(r["kind"], r["metadata"]["name"]): r for r in resources if r}
    prod = environment == "prod"
    namespace = "demo-" + environment
    for item in objects.values():
        require(item["metadata"].get("namespace") == namespace, "Unexpected namespace")
        require(item["kind"] not in {"Secret", "ClusterRole", "ClusterRoleBinding", "Ingress"}, "Forbidden app resource")
    kind = "Rollout" if prod else "Deployment"
    workload = objects[(kind, "demo-api")]
    template = workload["spec"]["template"]
    pod = template["spec"]
    container = next(c for c in pod["containers"] if c["name"] == "app")
    require(bool(re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", container["image"])), "Image must use digest")
    image_digest = container["image"].split("@")[1]
    require(template["metadata"]["annotations"]["delivery.example.com/image-digest"] == image_digest, "Version annotation mismatch")
    if release:
        digest(image_digest)
        require("example.com" not in container["image"], "Registry placeholder remains")
        vs = objects[("VirtualService", "demo-api")]
        require(all("example.com" not in h for h in vs["spec"]["hosts"]), "Domain placeholder remains")
    require(pod["automountServiceAccountToken"] is False, "Application must not mount API token")
    require(pod["securityContext"]["runAsNonRoot"] is True, "Non-root required")
    require(container["securityContext"]["readOnlyRootFilesystem"] is True, "Read-only root required")
    require(container["securityContext"]["allowPrivilegeEscalation"] is False, "Privilege escalation prohibited")
    for key in ("startupProbe", "readinessProbe", "livenessProbe", "resources"):
        require(key in container, f"Missing {key}")
    cm = container["envFrom"][0]["configMapRef"]["name"]
    require(("ConfigMap", cm) in objects, "Generated ConfigMap reference is broken")
    require(objects[("PeerAuthentication", "demo-api")]["spec"]["mtls"]["mode"] == "STRICT", "mTLS must be strict")
    policy = objects[("NetworkPolicy", "demo-api")]["spec"]
    require(set(policy["policyTypes"]) == {"Ingress", "Egress"}, "NetworkPolicy must cover both directions")
    require(("AuthorizationPolicy", "demo-api") in objects, "Istio authorization required")
    if prod:
        require(("Deployment", "demo-api") not in objects, "Two controllers cannot own the same pods")
        require("replicas" not in workload["spec"], "HPA must own production replicas")
        hpa = objects[("HorizontalPodAutoscaler", "demo-api")]["spec"]
        require(hpa["minReplicas"] >= 3 and hpa["scaleTargetRef"]["kind"] == "Rollout", "Invalid production HPA")
        require(objects[("PodDisruptionBudget", "demo-api")]["spec"]["minAvailable"] >= 2, "Production PDB missing")
        canary = workload["spec"]["strategy"]["canary"]
        require(any("analysis" in s for s in canary["steps"]), "No analysis gate")
        routes = objects[("VirtualService", "demo-api")]["spec"]["http"][0]["route"]
        require(len(routes) == 2 and sum(r["weight"] for r in routes) == 100, "Invalid canary weights")
        require(("AnalysisTemplate", "demo-api-quality") in objects, "Missing analysis template")
        require(("ServiceMonitor", "demo-api") in objects, "Missing production metrics")
    return len(objects)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--environment", choices=["test", "prod"])
    p.add_argument("--release", action="store_true", help="Fail on unconfigured application release values")
    a = p.parse_args()
    if a.release:
        production_ready(site())
    for env in ([a.environment] if a.environment else ["test", "prod"]):
        raw = subprocess.check_output(["kustomize", "build", str(ROOT / "gitops/apps/demo-api/overlays" / env)], text=True)
        count = validate(list(yaml.safe_load_all(raw)), env, a.release)
        print(f"{env}: {count} resources, delivery invariants passed")
        for folder in (f"argocd/{env}", f"platform/namespaces/{env}", f"platform/istio/{env}"):
            subprocess.run(["kustomize", "build", str(ROOT / folder)], check=True, stdout=subprocess.DEVNULL)
    print("Offline validation only; run server-side dry-run and end-to-end checks on actual clusters.")

if __name__ == "__main__":
    main()

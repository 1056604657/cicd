#!/usr/bin/env python3
"""Observe CD through read-only API and exercise the deployed image before attestation."""
import json
import os
import time
import urllib.request
from pathlib import Path
from common import digest, output, site


def get_json(url, token=None):
    headers = {"Authorization": "Bearer " + token} if token else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        return json.load(r)


def main():
    cfg = site()
    release = json.loads(Path("artifacts/pr.json").read_text())
    image_digest = digest(release["digest"])
    deadline = time.monotonic() + 2700
    merge_commit = release.get("gitopsCommit") if release.get("alreadyDesired") else None
    while merge_commit is None and time.monotonic() < deadline:
        pr = json.loads(output(["gh", "pr", "view", release["url"], "--json", "state,mergeCommit"]))
        if pr["state"] == "CLOSED":
            raise RuntimeError("Test release PR was closed without merge")
        if pr["state"] == "MERGED":
            merge_commit = pr["mergeCommit"]["oid"]
            break
        time.sleep(15)
    if merge_commit is None:
        raise TimeoutError("Test release PR not merged within 45 minutes")
    healthy = False
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        app = get_json(cfg["argocdTestUrl"] + "/api/v1/applications/demo-api-test", os.environ["ARGOCD_TEST_TOKEN"])
        status = app.get("status", {})
        images = status.get("summary", {}).get("images", [])
        healthy = (status.get("sync", {}).get("status") == "Synced"
                   and status.get("health", {}).get("status") == "Healthy"
                   and cfg["imageRepository"] + "@" + image_digest in images)
        if healthy:
            break
        time.sleep(10)
    if not healthy:
        raise TimeoutError("Argo CD did not report the tested digest as Synced/Healthy")
    for _ in range(5):
        result = get_json(cfg["testUrl"] + "/api/greeting?name=release-check")
        if result.get("version") != image_digest or result.get("message") != "Hello from test, release-check":
            raise RuntimeError("Smoke response does not match the intended test release")
        time.sleep(2)
    evidence = {"environment":"test", "digest":image_digest,
                "sourceCommit":release["sourceCommit"], "gitopsCommit":merge_commit,
                "checks":{"argocdHealthy":True,"smokePassed":True},
                "buildUrl":os.environ.get("BUILD_URL", "")}
    Path("artifacts/test-evidence.json").write_text(json.dumps(evidence, indent=2))

if __name__ == "__main__":
    main()

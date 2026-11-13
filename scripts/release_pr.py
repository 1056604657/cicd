#!/usr/bin/env python3
"""Create a GitOps PR; never merge it or write directly to the protected branch."""
import argparse
import json
import tempfile
import subprocess
from pathlib import Path
import yaml
from common import digest, output, production_ready, run, site, SHA


def update_overlay(root, environment, image, image_digest, source_sha):
    digest(image_digest)
    if not SHA.fullmatch(source_sha):
        raise ValueError("source SHA must be a full commit SHA")
    overlay = root / "gitops/apps/demo-api/overlays" / environment
    path = overlay / "kustomization.yaml"
    config = yaml.safe_load(path.read_text())
    item = next(item for item in config["images"] if item["name"] == "demo-api")
    item.pop("newTag", None)
    item.update(newName=image, digest=image_digest)
    path.write_text(yaml.safe_dump(config, sort_keys=False))
    workload = overlay / ("rollout.yaml" if environment == "prod" else "deployment-patch.yaml")
    value = yaml.safe_load(workload.read_text())
    annotations = value["spec"]["template"]["metadata"]["annotations"]
    annotations["delivery.example.com/image-digest"] = image_digest
    annotations["delivery.example.com/source-commit"] = source_sha
    workload.write_text(yaml.safe_dump(value, sort_keys=False))
    return overlay


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--environment", choices=["test", "prod"], required=True)
    p.add_argument("--digest", required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--output", default="artifacts/pr.json")
    args = p.parse_args()
    cfg = site(); production_ready(cfg); digest(args.digest)
    repo = cfg["repository"]
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "gitops"
        git = ["git", "-c", "credential.helper=", "-c", "credential.helper=!gh auth git-credential"]
        run(git + ["clone", "--depth", "1", "--branch", cfg["gitopsBranch"], f"https://github.com/{repo}.git", str(root)])
        branch = f"release/demo-api-{args.environment}-{args.digest[7:19]}-{output(['git','rev-parse','--short','HEAD'], cwd=root)}"
        run(["git", "checkout", "-b", branch], cwd=root)
        overlay = update_overlay(root, args.environment, cfg["imageRepository"], args.digest, args.source_sha)
        run(["kustomize", "build", str(overlay)], stdout=subprocess.DEVNULL)
        # Validate the fresh remote tree too; source checkout may be older than main.
        run(["python3", "scripts/validate.py", "--environment", args.environment, "--release"], cwd=root)
        run(["git", "add", str(overlay.relative_to(root))], cwd=root)
        if not output(["git", "diff", "--cached", "--name-only"], cwd=root):
            record = {"url":f"https://github.com/{repo}/tree/{cfg['gitopsBranch']}",
                      "digest":args.digest,"environment":args.environment,
                      "sourceCommit":args.source_sha,"alreadyDesired":True,
                      "gitopsCommit":output(["git","rev-parse","HEAD"],cwd=root)}
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(json.dumps(record))
            print("Already desired; re-verify deployment without opening a duplicate PR")
            return
        run(["git", "-c", "user.name=platform-delivery-bot", "-c", "user.email=platform-delivery-bot@users.noreply.github.com", "commit", "-m", f"release({args.environment}): demo-api {args.digest[7:19]}"], cwd=root)
        run(git + ["push", "origin", branch], cwd=root)
        body = Path(temp) / "body.md"
        body.write_text(f"Environment: {args.environment}\n\nImage: `{cfg['imageRepository']}@{args.digest}`\n\nSource: `{args.source_sha}`\n\nReview the digest, signature/test evidence and deployment diff before merging. Argo CD deploys after merge.\n")
        url = output(["gh", "pr", "create", "--repo", repo, "--base", cfg["gitopsBranch"], "--head", branch, "--title", f"release({args.environment}): demo-api {args.digest[7:19]}", "--body-file", str(body)])
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps({"url":url,"digest":args.digest,"environment":args.environment,"sourceCommit":args.source_sha}))
        print(url)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Replace infrastructure placeholders in tracked configuration; never write secrets."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from common import ROOT, production_ready


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--site", required=True, help="JSON based on ci/site.json, with all real values")
    p.add_argument("--vault-url", required=True)
    args = p.parse_args()
    config = json.loads(Path(args.site).read_text())
    production_ready(config)
    if not args.vault_url.startswith("https://") or "example.com" in args.vault_url:
        raise ValueError("Real HTTPS Vault URL required")
    replacements = {
        "https://github.com/1056604657/cicd.git": "https://github.com/" + config["repository"] + ".git",
        "harbor.example.com/business/demo-api":config["imageRepository"],
        "demo-test.example.com":urlparse(config["testUrl"]).hostname,
        "demo-prod.example.com":urlparse(config["prodUrl"]).hostname,
        "https://vault.example.com":args.vault_url,
    }
    for folder in ("argocd", "gitops", "platform"):
        for path in (ROOT / folder).rglob("*.yaml"):
            content = path.read_text()
            for old,new in replacements.items(): content = content.replace(old,new)
            path.write_text(content)
    (ROOT/"ci/site.json").write_text(json.dumps(config,indent=2)+"\n")
    print("Review git diff; registry/domain configured. Image digests remain fail-closed until CI publishes a release.")

if __name__ == '__main__': main()

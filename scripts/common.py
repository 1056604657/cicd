import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
SHA = re.compile(r"[0-9a-f]{40}")

def digest(value):
    if not DIGEST.fullmatch(value) or value == "sha256:" + "0" * 64:
        raise ValueError("A real immutable sha256 image digest is required")
    return value

def run(args, **kw):
    return subprocess.run(args, check=True, text=True, **kw)

def output(args, **kw):
    return subprocess.check_output(args, text=True, **kw).strip()

def site():
    return json.loads((ROOT / "ci/site.json").read_text())

def production_ready(config):
    encoded = json.dumps(config)
    if "example.com" in encoded or "0" * 64 in encoded:
        raise ValueError("Configure ci/site.json before publishing; placeholders are blocked")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config["repository"]):
        raise ValueError("Invalid GitHub repository")
    if not re.fullmatch(r"[a-z0-9.:-]+/[a-z0-9/_-]+", config["imageRepository"]):
        raise ValueError("Invalid image repository")
    digest(config["runtimeImage"].split("@")[-1])
    for key in ("argocdTestUrl", "testUrl", "prodUrl"):
        if not config[key].startswith("https://"):
            raise ValueError(f"{key} requires HTTPS")

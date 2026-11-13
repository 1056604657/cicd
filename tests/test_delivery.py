import base64
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import digest, production_ready
from release_pr import update_overlay
from check_attestation import validate as check_evidence
from validate import validate

D = "sha256:" + "a" * 64
SOURCE = "b" * 40

class DeliveryTests(unittest.TestCase):
    def test_rejects_mutable_or_placeholder_images(self):
        for value in ("latest", "sha256:" + "0"*64, D + ";echo injected", "sha256:abc"):
            with self.assertRaises(ValueError): digest(value)

    def test_site_placeholders_fail_closed(self):
        with self.assertRaises(ValueError):
            production_ready({"registry": "harbor.example.com"})

    def test_signed_evidence_must_match_image_and_success(self):
        statement = {"predicateType":"https://delivery.example.com/attestations/test/v1",
                     "subject":[{"digest":{"sha256": D[7:]}}],
                     "predicate":{"environment":"test","digest":D,"sourceCommit":SOURCE,
                                  "checks":{"argocdHealthy":True,"smokePassed":True}}}
        def envelope(s): return [{"payload":base64.b64encode(json.dumps(s).encode()).decode()}]
        self.assertEqual(check_evidence(envelope(statement), D), SOURCE)
        for mutation in ("digest", "checks", "environment"):
            bad = copy.deepcopy(statement)
            bad["predicate"][mutation] = "incorrect"
            with self.assertRaises(ValueError): check_evidence(envelope(bad), D)
        with self.assertRaises(ValueError): check_evidence(envelope(statement), "sha256:"+"c"*64)

    def test_both_rendered_environments(self):
        for env in ("test", "prod"):
            raw = subprocess.check_output(["kustomize", "build", str(ROOT/"gitops/apps/demo-api/overlays"/env)], text=True)
            docs = list(yaml.safe_load_all(raw))
            self.assertGreater(validate(docs, env), 5)
            bad = copy.deepcopy(docs)
            w = next(x for x in bad if x["kind"] in ("Deployment","Rollout"))
            w["spec"]["template"]["spec"]["containers"][0]["image"] = "demo:latest"
            with self.assertRaises(ValueError): validate(bad, env)

    def test_promotion_only_changes_selected_environment(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT/"gitops", root/"gitops")
            test_before = (root/"gitops/apps/demo-api/overlays/test/kustomization.yaml").read_bytes()
            overlay = update_overlay(root, "prod", "registry.internal/team/demo-api", D, SOURCE)
            raw = subprocess.check_output(["kustomize","build",str(overlay)], text=True)
            docs = list(yaml.safe_load_all(raw))
            rollout = next(x for x in docs if x["kind"] == "Rollout")
            self.assertEqual(rollout["spec"]["template"]["spec"]["containers"][0]["image"], "registry.internal/team/demo-api@"+D)
            self.assertEqual(test_before, (root/"gitops/apps/demo-api/overlays/test/kustomization.yaml").read_bytes())
            self.assertEqual(rollout["spec"]["template"]["metadata"]["annotations"]["delivery.example.com/image-digest"], D)

if __name__ == '__main__': unittest.main()

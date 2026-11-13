#!/usr/bin/env python3
import argparse
from pathlib import Path
import yaml
from common import ROOT, site
p=argparse.ArgumentParser()
p.add_argument('--build-public-key',required=True)
p.add_argument('--test-public-key',required=True)
a=p.parse_args()
keys=[Path(a.build_public_key).read_text(),Path(a.test_public_key).read_text()]
for key in keys:
    if '-----BEGIN PUBLIC KEY-----' not in key or 'PRIVATE' in key:
        raise ValueError('Only PEM public keys may be committed')
path=ROOT/'platform/policies/verify-images.yaml'
policy=yaml.safe_load(path.read_text())
v=policy['spec']['rules'][1]['verifyImages'][0]
policy['spec']['rules'][0]['validate']['pattern']['spec']['containers'][0]['image']=site()['imageRepository']+'@sha256:*'
v['imageReferences']=[site()['imageRepository']+'*']
v['attestors'][0]['entries'][0]['keys']['publicKeys']=keys[0]
v['attestations'][0]['attestors'][0]['entries'][0]['keys']['publicKeys']=keys[1]
path.write_text(yaml.safe_dump(policy,sort_keys=False))

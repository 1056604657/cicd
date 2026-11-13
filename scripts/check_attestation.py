#!/usr/bin/env python3
import base64
import json
import sys
from common import digest, SHA


def validate(envelopes, expected):
    digest(expected)
    for envelope in envelopes:
        statement = json.loads(base64.b64decode(envelope["payload"]))
        predicate = statement.get("predicate", {})
        subjects = statement.get("subject", [])
        if (statement.get("predicateType") == "https://delivery.example.com/attestations/test/v1"
            and any(s.get("digest", {}).get("sha256") == expected[7:] for s in subjects)
            and predicate.get("environment") == "test" and predicate.get("digest") == expected
            and predicate.get("checks") == {"argocdHealthy": True, "smokePassed": True}
            and SHA.fullmatch(predicate.get("sourceCommit", ""))):
            return predicate["sourceCommit"]
    raise ValueError("No signed, matching successful test evidence")

if __name__ == "__main__":
    raw = open(sys.argv[2]).read()
    # cosign versions may emit a JSON array or newline-delimited JSON envelopes.
    try:
        data = json.loads(raw)
        items = data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        items = [json.loads(line) for line in raw.splitlines() if line.strip()]
    print(validate(items, sys.argv[1]))

#!/usr/bin/env bash
set -euo pipefail
: "${1:?Usage: smoke.sh https://demo.domain sha256:digest}" "${2:?Expected digest required}"
# Does not accept self-signed TLS silently; install your internal CA in the agent trust store.
curl --fail --silent --show-error --max-time 15 "$1/api/greeting?name=smoke" | \
  python3 -c 'import json,sys; r=json.load(sys.stdin); assert r["version"]==sys.argv[1],r; print("smoke passed:",r)' "$2"

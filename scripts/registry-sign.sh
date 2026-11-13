#!/usr/bin/env bash
set -euo pipefail
: "${IMAGE_REPOSITORY:?}" "${HARBOR_USER:?}" "${HARBOR_PASSWORD:?}" "${COSIGN_KEY:?}"
export DOCKER_CONFIG
DOCKER_CONFIG=$(mktemp -d)
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
printf '%s' "$HARBOR_PASSWORD" | crane auth login "${IMAGE_REPOSITORY%%/*}" -u "$HARBOR_USER" --password-stdin
image="$IMAGE_REPOSITORY@$(cat artifacts/image-digest.txt)"
# A private PKI/key based trust policy is used; no private build data sent to a public log.
cosign sign --yes --key "$COSIGN_KEY" --tlog-upload=false "$image"
cosign attest --yes --key "$COSIGN_KEY" --tlog-upload=false \
  --type spdxjson --predicate artifacts/sbom.spdx.json "$image"

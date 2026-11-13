#!/usr/bin/env bash
set -euo pipefail
: "${IMAGE_REPOSITORY:?}" "${HARBOR_USER:?}" "${HARBOR_PASSWORD:?}" "${TEST_SIGNING_KEY:?}"
export DOCKER_CONFIG
DOCKER_CONFIG=$(mktemp -d)
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
printf '%s' "$HARBOR_PASSWORD" | crane auth login "${IMAGE_REPOSITORY%%/*}" -u "$HARBOR_USER" --password-stdin
cosign attest --yes --key "$TEST_SIGNING_KEY" --tlog-upload=false \
  --type https://delivery.example.com/attestations/test/v1 \
  --predicate artifacts/test-evidence.json "$IMAGE_REPOSITORY@$(cat artifacts/image-digest.txt)"

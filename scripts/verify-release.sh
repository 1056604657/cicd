#!/usr/bin/env bash
set -euo pipefail
: "${IMAGE_REPOSITORY:?}" "${RELEASE_DIGEST:?}" "${BUILD_PUBLIC_KEY:?}" "${TEST_PUBLIC_KEY:?}"
: "${HARBOR_USER:?}" "${HARBOR_PASSWORD:?}"
mkdir -p artifacts
export DOCKER_CONFIG
DOCKER_CONFIG=$(mktemp -d)
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
printf '%s' "$HARBOR_PASSWORD" | crane auth login "${IMAGE_REPOSITORY%%/*}" -u "$HARBOR_USER" --password-stdin
image="$IMAGE_REPOSITORY@$RELEASE_DIGEST"
# Key-based trust without public transparency log; signature and subject claims remain verified.
cosign verify --key "$BUILD_PUBLIC_KEY" --insecure-ignore-tlog=true "$image" > artifacts/signature.json
cosign verify-attestation --key "$TEST_PUBLIC_KEY" --insecure-ignore-tlog=true \
  --type https://delivery.example.com/attestations/test/v1 "$image" > artifacts/attestations.json
python3 scripts/check_attestation.py "$RELEASE_DIGEST" artifacts/attestations.json > artifacts/source-sha.txt

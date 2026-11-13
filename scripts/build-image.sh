#!/usr/bin/env bash
set -euo pipefail
# Credentials are bound only to a trusted, isolated, single-executor release agent.
: "${IMAGE_REPOSITORY:?}" "${RUNTIME_IMAGE:?}" "${GIT_COMMIT:?}" "${BUILD_NUMBER:?}"
: "${HARBOR_USER:?}" "${HARBOR_PASSWORD:?}" "${BUILDKIT_HOST:?}"
mkdir -p artifacts
export DOCKER_CONFIG
DOCKER_CONFIG=$(mktemp -d)
trap 'rm -rf "$DOCKER_CONFIG"' EXIT
printf '%s' "$HARBOR_PASSWORD" | crane auth login "${IMAGE_REPOSITORY%%/*}" -u "$HARBOR_USER" --password-stdin
image_tag="${IMAGE_REPOSITORY}:git-${GIT_COMMIT}-build-${BUILD_NUMBER}"
buildctl --addr "$BUILDKIT_HOST" build --frontend dockerfile.v0 \
  --local context=demo-java --local dockerfile=demo-java \
  --opt "build-arg:RUNTIME_IMAGE=$RUNTIME_IMAGE" \
  --output "type=docker,name=$image_tag,dest=artifacts/image.tar"
syft docker-archive:artifacts/image.tar -o spdx-json=artifacts/sbom.spdx.json
trivy image --input artifacts/image.tar --scanners vuln --severity HIGH,CRITICAL \
  --exit-code 1 --format json --output artifacts/image-scan.json
crane push artifacts/image.tar "$image_tag"
crane digest "$image_tag" > artifacts/image-digest.txt
# Do not archive the large image tar; retain reports and signed evidence.
rm artifacts/image.tar

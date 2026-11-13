# Agent tool contract

This reference uses isolated, ephemeral Linux agents, not the Jenkins controller or a shared host Docker socket.
The agent image Dockerfile is an image-building recipe; supply an approved base digest and verified binaries.

Required binaries in `bin/`: `kustomize` (tested 5.6.0), `buildctl`, `crane`, `cosign` (2.x key-based flags),
`trivy`, `syft`, `gh`. Java 21, Maven 3.9.x, Python 3, PyYAML 6.0.3 and Git are required.
Use organization-approved versions with security maintenance; record their digests/checksums in your platform inventory.
Do not commit actual downloaded executables to this repository.

Provision one rootless BuildKit daemon per trusted release executor, expose only its Unix socket to that agent,
and set `BUILDKIT_HOST=unix:///run/user/<uid>/buildkit/buildkitd.sock` to the real socket.
BuildKit and its worker must trust the registry CA. Do not use anonymous remote TCP BuildKit.
If running rootless BuildKit in Kubernetes, evaluate its seccomp/user-namespace requirements separately;
do not weaken business namespace Pod Security just to run builds.

Pools: `untrusted-check-java21`, `trusted-release-java21`, `trusted-promotion`.
Each credential-bearing agent runs one executor and is destroyed after the job.
The promotion pool needs no BuildKit and has no cluster write credentials.

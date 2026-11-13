# Build and sign this tool image in the platform team's controlled pipeline.
# A digest-pinned Maven/JDK21 image with apt, curl and CA certificates is required.
ARG AGENT_BASE_IMAGE
FROM ${AGENT_BASE_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    git python3 python3-venv ca-certificates curl tar gzip && rm -rf /var/lib/apt/lists/*
COPY scripts/requirements.txt /opt/requirements.txt
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r /opt/requirements.txt
# Platform-supplied, checksum-verified Linux binaries (not downloaded from arbitrary URLs during CI).
COPY jenkins/agent/bin/ /usr/local/bin/
ENV PATH="/opt/venv/bin:${PATH}"
RUN java -version && mvn -version && python3 -c 'import yaml' && \
    kustomize version && buildctl --version && crane version && cosign version && \
    trivy --version && syft version && gh --version
RUN useradd --uid 10001 --create-home --shell /bin/bash jenkins
USER 10001:10001
WORKDIR /home/jenkins

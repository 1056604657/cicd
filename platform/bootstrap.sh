#!/usr/bin/env bash
set -euo pipefail
: "${1:?Usage: bootstrap.sh test|prod expected-kube-context versions.env}"
: "${2:?Explicit kube context required}" "${3:?Pinned versions file required}"
case "$1" in test|prod) ;; *) exit 2;; esac
environment=$1
context=$2
source "$3"
for variable in ISTIO_VERSION ARGOCD_CHART_VERSION ROLLOUTS_CHART_VERSION EXTERNAL_SECRETS_CHART_VERSION PROMETHEUS_CHART_VERSION KYVERNO_CHART_VERSION; do
  value=${!variable:-}
  [[ "$value" =~ ^[0-9]+\.[0-9]+\.[0-9]+([+-][a-zA-Z0-9.-]+)?$ ]] || { echo "Pin $variable to an approved version" >&2; exit 1; }
done
: "${ARGOCD_SSO_VALUES:?Reviewed SSO values required}"
: "${MONITORING_SITE_VALUES:?Reviewed storage and Alertmanager routing values required}"
python3 -c "from scripts.common import site, production_ready; production_ready(site())"
[[ -f "$ARGOCD_SSO_VALUES" && -f "$MONITORING_SITE_VALUES" ]]
command -v helm >/dev/null
command -v kubectl >/dev/null
[[ $(kubectl --context "$context" config current-context) == "$context" ]] || { echo 'Switch to the explicitly selected context first'; exit 1; }
# Read-only validation before any mutation; operator owns platform installation.
kubectl --context "$context" cluster-info
helm repo add istio https://istio-release.storage.googleapis.com/charts
helm repo add argo https://argoproj.github.io/argo-helm
helm repo add external-secrets https://charts.external-secrets.io
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
helm upgrade --install istio-base istio/base --version "$ISTIO_VERSION" --namespace istio-system --create-namespace --kube-context "$context" --wait --timeout 10m
# Istio CNI is required to preserve restricted Pod Security in application namespaces.
helm upgrade --install istio-cni istio/cni --version "$ISTIO_VERSION" --namespace istio-system --kube-context "$context" --wait --timeout 10m
helm upgrade --install istiod istio/istiod --version "$ISTIO_VERSION" --namespace istio-system --kube-context "$context" -f platform/istio/istiod-values.yaml --set pilot.cni.enabled=true --wait --timeout 10m
helm upgrade --install external-secrets external-secrets/external-secrets --version "$EXTERNAL_SECRETS_CHART_VERSION" --namespace external-secrets --create-namespace --kube-context "$context" --set installCRDs=true --wait --timeout 10m
helm upgrade --install argo-rollouts argo/argo-rollouts --version "$ROLLOUTS_CHART_VERSION" --namespace argo-rollouts --create-namespace --kube-context "$context" --set controller.replicas=2 --wait --timeout 10m
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack --version "$PROMETHEUS_CHART_VERSION" --namespace monitoring --create-namespace --kube-context "$context" -f platform/monitoring-values.yaml -f "$MONITORING_SITE_VALUES" --wait --timeout 15m
helm upgrade --install kyverno kyverno/kyverno --version "$KYVERNO_CHART_VERSION" --namespace kyverno --create-namespace --kube-context "$context" --set admissionController.replicas=3 --wait --timeout 10m
# Merge organization SSO values. Admin is disabled in our values by design.
: "${ARGOCD_SSO_VALUES:?Path to reviewed SSO/group mapping values is required}"
helm upgrade --install argocd argo/argo-cd --version "$ARGOCD_CHART_VERSION" --namespace argocd --create-namespace --kube-context "$context" -f argocd/platform-values.yaml -f "$ARGOCD_SSO_VALUES" --wait --timeout 15m
kubectl --context "$context" apply -k "platform/namespaces/$environment"
kubectl --context "$context" apply -k "platform/istio/$environment"
helm upgrade --install istio-ingressgateway istio/gateway --version "$ISTIO_VERSION" --namespace istio-ingress --kube-context "$context" -f platform/istio/gateway-values.yaml --wait --timeout 10m
echo 'Platform installed. Configure Vault, DNS, TLS, signing policy, and release images before creating Argo applications.'

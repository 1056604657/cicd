#!/usr/bin/env bash
set -euo pipefail
: "${1:?Usage: preflight-cluster.sh test|prod explicit-context}" "${2:?Context required}"
case "$1" in test|prod) ;; *) exit 2;; esac
environment=$1
context=$2
python3 scripts/validate.py --environment "$environment" --release
for crd in applications.argoproj.io appprojects.argoproj.io gateways.networking.istio.io virtualservices.networking.istio.io peerauthentications.security.istio.io secretstores.external-secrets.io; do
  kubectl --context "$context" get crd "$crd" -o name
done
if [[ "$environment" == prod ]]; then
  kubectl --context "$context" get clusterpolicy demo-prod-image-trust -o name
  for crd in rollouts.argoproj.io analysistemplates.argoproj.io servicemonitors.monitoring.coreos.com prometheusrules.monitoring.coreos.com; do
    kubectl --context "$context" get crd "$crd" -o name
  done
fi
kubectl --context "$context" -n "demo-$environment" wait --for=condition=Ready externalsecret/harbor-pull --timeout=60s
kubectl --context "$context" -n istio-ingress wait --for=condition=Ready "externalsecret/demo-$environment-tls" --timeout=60s
# Read metadata only, never output the Secret payload.
kubectl --context "$context" -n "demo-$environment" get secret harbor-pull -o name
kubectl --context "$context" -n istio-ingress get secret "demo-$environment-tls" -o name
kustomize build "gitops/apps/demo-api/overlays/$environment" | kubectl --context "$context" apply --dry-run=server -f -
kustomize build "argocd/$environment" | kubectl --context "$context" apply --dry-run=server -f -
echo 'Server validation passed. Check CNI, gateway identity, monitoring reachability and admission policy before activation.'

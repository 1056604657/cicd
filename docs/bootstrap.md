# 从零接入与首次发布

本手册中的集群操作由平台管理员执行。先在测试集群验证，再在独立生产集群重复。不要直接在已有平台重复安装同名 Helm release；已有组件只需核对 CRD、版本和配置后复用。

## 1. 必要条件

- 受维护的 Kubernetes 集群，最低 API 基线 1.31；实际部署选择与 Istio 等组件兼容且仍在维护的版本。
- 支持 NetworkPolicy 的 CNI；metrics-server；生产至少足够节点承载 3 个应用副本及发布临时容量。
- Harbor、DNS、可信 TLS 证书、Vault KV v2、SSO、持久化存储与告警接收渠道。
- 管理端具有 kubectl、Helm、Kustomize、Python、PyYAML；显式选择 kube context。
- CI Agent 到 GitHub、Harbor、依赖源、测试 HTTPS 入口和测试 Argo 只读 API 的网络连通性。

## 2. 配置非敏感站点信息

```bash
mkdir -p .work
cp ci/site.json .work/site.json
# 编辑 .work/site.json：填真实域名、仓库和审核过的 Java21 运行时镜像 digest。
python3 scripts/configure.py --site .work/site.json --vault-url https://vault.your-domain
python3 scripts/validate.py
git diff
```

脚本修改应用镜像仓库、Istio 域名、Vault 地址和 Argo 仓库地址。它不会生成密码、公钥或真实镜像 digest。配置变化先通过 PR 合并；本仓本身就是 GitOps 源，未合并的本地修改不会被 Argo CD 读取。

当前 `gitopsBranch` 应保持 main；改分支须同时修改 Argo Application targetRevision、Jenkins SCM 和保护规则。

确认 `platform/istio/gateway-values.yaml` 的 ServiceAccount 和 selector 与 AuthorizationPolicy 一致。为测试和生产域名分别创建指向对应网关 LoadBalancer 的 DNS 记录。

## 3. 准备固定版本与平台参数

```bash
cp platform/versions.env.example .work/versions.env
# 填写实际批准的、兼容的精确 Helm chart 版本，不能保留 SET_APPROVED_VERSION。
```

为两个集群分别准备 `.work/argocd-sso-test.yaml`、`.work/argocd-sso-prod.yaml`，配置企业 OIDC/Dex 和操作员组；管理员账号默认禁用。为监控准备 `.work/monitoring-test.yaml` 和 `.work/monitoring-prod.yaml`，至少设置可用 storageClass、Prometheus 外部标签、Alertmanager 接收器与路由，避免已装监控却没有告警接收人。

确认 ESO chart 提供 external-secrets.io/v1beta1；若采用只提供 v1 的版本，更新全部 SecretStore/ExternalSecret apiVersion 并进行 server dry-run。不要以忽略缺失 schema 的方式绕过。

```bash
kubectl config use-context YOUR_TEST_CONTEXT
export ARGOCD_SSO_VALUES=.work/argocd-sso-test.yaml
export MONITORING_SITE_VALUES=.work/monitoring-test.yaml
bash platform/bootstrap.sh test YOUR_TEST_CONTEXT .work/versions.env

# 测试完成后再对生产执行；必须选择不同的生产 context。
kubectl config use-context YOUR_PROD_CONTEXT
export ARGOCD_SSO_VALUES=.work/argocd-sso-prod.yaml
export MONITORING_SITE_VALUES=.work/monitoring-prod.yaml
bash platform/bootstrap.sh prod YOUR_PROD_CONTEXT .work/versions.env
```

bootstrap 是明确的写操作，会安装组件及创建平台资源，不会创建业务 Argo Application。安装顺序是 Istio base/CNI/istiod → ESO/Rollouts/监控/Kyverno/Argo CD → 命名空间/网关资源 → 网关 Deployment。

Istio CNI 的安装 namespace、CNI bin/config 路径和权限需要依据节点系统/托管 K8s 约束核对；本入口使用标准 Linux 节点路径。对既有集群变更 CNI 必须先通过平台评审和测试。

## 4. Vault、Harbor 拉取凭据与证书

本工程不替你部署 Vault 存储集群；复用已具备 HA、备份、自动解封与审计的企业 Vault。

在 Vault 为每个集群配置独立 Kubernetes auth mount：kubernetes-test、kubernetes-prod，正确配置 API 地址、CA 和 TokenReview 身份。创建以下 role，绑定准确的 SA/namespace：

| auth mount | role | SA | namespace | policy 文件 |
|---|---|---|---|---|
| kubernetes-test | demo-test | vault-auth | demo-test | test-policy.hcl |
| kubernetes-prod | demo-prod | vault-auth | demo-prod | prod-policy.hcl |
| kubernetes-test | gateway-test | vault-auth | istio-ingress | gateway-test-policy.hcl |
| kubernetes-prod | gateway-prod | vault-auth | istio-ingress | gateway-prod-policy.hcl |

例如，已完成 auth mount 配置后：

```bash
vault policy write demo-test platform/vault/test-policy.hcl
vault write auth/kubernetes-test/role/demo-test \
  bound_service_account_names=vault-auth \
  bound_service_account_namespaces=demo-test \
  policies=demo-test ttl=1h
```

其余 role 同理，对应独立 policy。ESO 控制器必须能在相应命名空间对 vault-auth 创建短期 ServiceAccount token；审核其 RBAC 和 token audience，按现场 Vault 版本配置匹配的 audience。

KV v2 路径及字段：

| 路径 | 字段 | 内容 |
|---|---|---|
| kv/cicd/test/harbor | dockerconfigjson | 仅测试项目拉取权限的完整 Docker auth JSON 字符串 |
| kv/cicd/prod/harbor | dockerconfigjson | 仅生产应用镜像拉取权限的完整 Docker auth JSON 字符串 |
| kv/cicd/test/tls | tls.crt、tls.key | 测试域名证书链、私钥 |
| kv/cicd/prod/tls | tls.crt、tls.key | 生产域名证书链、私钥 |

使用 Vault UI 或从安全文件导入，避免秘密进入命令历史。Harbor pull Secret 在业务 namespace；TLS Secret 在 istio-ingress，因为 Gateway 的 credentialName 在网关所在 namespace 解析。

若 Vault 使用内部 CA，在 SecretStore 配置 caProvider 并在对应 namespace 分发 CA ConfigMap；不要关闭 TLS 验证。生产 registry CA 还必须被各节点容器运行时、BuildKit、Jenkins 和 Kyverno 信任。

## 5. 签名与生产准入

在安全管理环境生成两个独立的 Cosign 密钥对，并按 Jenkins 文档导入私钥和公钥凭据。私钥绝不提交到仓库。

```bash
python3 scripts/configure-signing-policy.py \
  --build-public-key /secure/public/build.pub \
  --test-public-key /secure/public/test.pub
# 审查 public key、镜像路径与策略后提交 Git。
kubectl --context YOUR_PROD_CONTEXT apply --dry-run=server -f platform/policies/verify-images.yaml
kubectl --context YOUR_PROD_CONTEXT apply -f platform/policies/verify-images.yaml
```

Kyverno 需要只读访问私有 Harbor，包括签名与证明；按选定 chart 配置 imagePullSecrets/registryCredentials 并通过 External Secrets 从 Vault 提供。不要复用镜像推送账号。验证 signed+tested 镜像被接受、未签名/错误签名/错误测试证明/其他仓库镜像被拒绝。

默认策略公钥是占位字符串，未替换不得安装。Webhook 必须以 fail-closed 运行并有足够副本；准入服务不可用时新的生产 Pod 可能被阻断，需要独立故障预案。

## 6. Jenkins 与首次测试上线

按 jenkins.md 配置三个任务。首次 release 流水线将：

1. 构建并签名镜像，创建测试 PR。
2. 等待测试 PR 合并，最长 45 分钟。
3. 观察 Argo CD 并做 HTTP 冒烟，最长 15 分钟。

首次测试 PR 合并后，在等待窗口内执行：

```bash
# 本地先拉到已合并的 main。
git pull --ff-only
bash scripts/preflight-cluster.sh test YOUR_TEST_CONTEXT
kubectl --context YOUR_TEST_CONTEXT apply -k argocd/test
```

预检包含完整 Kustomize 渲染、真实镜像检查、Secret Ready、CRD 和服务端 dry-run。Jenkins 的测试 Argo URL 与只读 Token 必须已配置。超时不会签名测试证明；修复后重跑，或按评审流程恢复该次验证。

## 7. 首次生产上线

测试完成后，取得 artifacts/image-digest.txt，运行 demo-api-promote-prod。确认输出生产 PR，检查签名证据、代码版本、镜像及环境 diff，再由授权审批人合并。

```bash
git pull --ff-only
bash scripts/preflight-cluster.sh prod YOUR_PROD_CONTEXT
kubectl --context YOUR_PROD_CONTEXT apply -k argocd/prod
kubectl --context YOUR_PROD_CONTEXT argo rollouts get rollout demo-api -n demo-prod --watch
```

首次部署需明确验收，不具备旧版本可供灰度或回滚。第二次发布必须演练 10%/50% 灰度、低样本暂停、错误率失败、主动中止以及恢复旧 digest。

## 8. 投产门槛

完成：版本兼容、CA/DNS、SSO/RBAC、Vault/ESO、Harbor 保留策略、签名准入、NetworkPolicy 拒绝测试、Prometheus 标签与查询、告警送达、节点维护、灰度失败、数据兼容、备份恢复。资源默认值是起点，必须通过真实流量压测调整。

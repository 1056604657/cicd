# Kubernetes 生产级 CI/CD 参考工程

**Java 21 / Spring Boot → Jenkins + Shared Library → Harbor → Kustomize → Argo CD → Istio + Argo Rollouts。**

本仓库包含可编译的 Java 示例、CI 与生产提升流水线、测试/生产完整应用清单、平台接入代码、验证脚本及运维手册。Jenkins 不执行生产 kubectl/Helm 部署；Argo CD 执行 CD；Rollouts 使用 Istio 进行生产灰度。

> 这是面向生产实施的完整参考工程，不是已经在你公司集群验收通过的部署。真实域名、CA、集群版本、身份认证、Vault、签名公钥和容量需要现场配置。默认镜像 digest 为全零占位值，发布脚本会主动拒绝。未接入的系统和未经执行的测试详见 [验证记录](docs/validation.md)。

## 交付链路

```mermaid
flowchart LR
    C[应用代码合并] --> J[Jenkins / Shared Library]
    J --> T[Java 测试 / 覆盖率 / 密钥扫描]
    T --> B[Rootless BuildKit / 镜像扫描 / SBOM]
    B --> H[Harbor 不可变镜像 / Cosign 签名]
    H --> TP[测试 GitOps PR]
    TP --> AT[测试 Argo CD]
    AT --> IT[Istio / Deployment]
    IT --> E[只读状态检查 / HTTP 冒烟 / 签名测试证据]
    E --> PP[生产提升流水线 / 验签 / 生产 PR]
    PP --> R[CODEOWNERS 审批合并]
    R --> AP[生产 Argo CD]
    AP --> RO[Argo Rollouts / Istio 10% → 50% → 100%]
    RO --> M[Prometheus 样本量与错误率分析]
```

生产提升只改变 Git 中的镜像 digest，不重新编译。生产准入通过 Kyverno 再检查镜像签名及测试证明，防止仅依赖 Jenkins 检查。应用与配置本仓集中展示，正式团队可按文档拆分权限仓库。

## 目录

| 路径 | 内容 |
|---|---|
| `demo-java/` | Spring Boot API、Actuator、Prometheus 指标、结构化日志、测试与 Dockerfile |
| `Jenkinsfile` | 可信主分支构建及测试环境交付入口 |
| `jenkins/Jenkinsfile.ci` | 不可信 PR 检查入口，不绑定发布凭据 |
| `jenkins/Jenkinsfile.promote-prod` | 验证签名和测试证据，创建生产审批 PR |
| `jenkins/shared-library/` | 可复用 CI、生产提升逻辑 |
| `jenkins/agent/` | 构建工具镜像配方及 Agent 隔离契约 |
| `gitops/apps/demo-api/base/` | 共享服务、安全、探针与网络配置 |
| `gitops/apps/demo-api/overlays/test/` | 测试 Deployment、配置、Istio 路由 |
| `gitops/apps/demo-api/overlays/prod/` | Rollout、HPA、PDB、灰度分析、监控与 Istio 路由 |
| `argocd/test/`、`argocd/prod/` | 各自 Application 与 AppProject 权限边界 |
| `platform/` | Istio Gateway/CNI 安装入口、命名空间、Vault/ESO、准入策略、监控 |
| `scripts/`、`tests/` | 构建发布、配置初始化、验证、冒烟、证明校验及测试 |

## 测试与生产的区别

| 能力 | 测试 | 生产 |
|---|---|---|
| 集群 / Argo CD | 独立测试集群与 Argo CD | 独立生产集群与 Argo CD |
| 命名空间 | demo-test | demo-prod |
| 工作负载 | Deployment，1 副本 | Rollout，HPA 最小 3、最大 10 |
| 发布 | Git PR 合并后自动同步 | 审批 PR 合并后自动同步与灰度分析 |
| 网络 | Istio Gateway、STRICT mTLS、授权与 NetworkPolicy | 同左，增加 stable/canary 路由 |
| 策略 | 滚动更新 | 10% → 分析 → 50% → 分析 → 100% |
| 证据 | 实际 HTTP 冒烟后签名测试证据 | 验证构建签名和测试证据；准入再次验证 |
| 运维 | 健康探针、资源限制 | 增加 PDB、拓扑分布、监控告警、HPA |

测试与生产共享库和基础配置，分别维护环境 overlay。生产 Rollout 使用独立 Pod 模板以明确控制器差异；新增公共运行参数时须同时更新两种工作负载，并执行验证。

## 本地验证

需要 JDK 21、Maven 3.9.x、Python 3、Kustomize 5.6.0。

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r scripts/requirements.txt
make -f scripts/Makefile verify
mvn -f demo-java/pom.xml spring-boot:run
# 另一个终端：
curl 'http://localhost:8080/api/greeting?name=platform'
curl http://localhost:8080/readyz
curl http://localhost:8081/actuator/prometheus
```

## 实施顺序

1. 阅读 [架构决策](docs/design.md)，确认基础设施与权限边界。
2. 按 [从零接入手册](docs/bootstrap.md) 配置站点、平台组件、Vault、TLS 和签名准入。
3. 按 [Jenkins 配置](docs/jenkins.md) 接入 Shared Library、Agent、凭据和任务。
4. 执行测试流水线，合并测试 PR，创建测试 Argo Application，完成签名测试证明。
5. 运行生产提升任务，审批生产 PR，完成生产预检后创建生产 Argo Application。
6. 按 [发布与故障手册](docs/runbook.md) 执行首次上线、灰度、回滚和恢复演练。

[原始建设方案](docs/architecture.md) 保留为设计背景；如与工程实现存在差异，以本 README、实施文档和代码为准。当前明确采用 Istio，未使用 NGINX Ingress。

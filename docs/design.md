# 架构决策与生产边界

## 1. 平台职责

- Jenkins：源代码质量检查、构建一次、扫描、签名、提交 GitOps PR。
- Argo CD：读取受保护 Git 主分支，执行部署并观测声明状态。
- Kustomize：公共 base 与环境 overlay；生成有内容哈希的 ConfigMap，配置变化触发新 Pod。
- Argo Rollouts：生产渐进交付控制器；通过 Istio VirtualService 修改流量权重。
- Harbor：不可变镜像及签名/证明存储。签名和 SBOM 必须随镜像一起保留。
- Kyverno：生产 Pod 准入时校验镜像签名、测试证据和不可变镜像引用。
- Vault / External Secrets：同步 Harbor 只读拉取凭据和网关 TLS 证书，不将明文放进 Git。

本工程使用 GitHub PR API。替换为 GitLab 时，需要替换 `release_pr.py` 和 `verify_test.py` 中的 PR/MR 接口；构建与 GitOps 清单可复用。

## 2. 仓库与组织权限

为交付和学习，本仓同时展示应用、流水线库、GitOps 与平台配置。正式团队建议拆为：应用仓库、平台 Shared Library 仓库、GitOps 仓库、平台基础设施仓库。拆分时调整流水线脚本取用路径及仓库配置，不能只修改一个 URL 就认为已完成隔离。

使用本仓部署时，保护 main：禁止 force push、禁止删除、必须 PR、必须平台负责人审查敏感路径、废弃旧审批、最后提交人不可自行批准、必须通过可信 Jenkins 状态检查。GitOps bot 只有分支写入和 PR 创建权限，无绕过保护或自动审批权限。

配置 CODEOWNERS 中的实际账号/团队。仓库所有者/管理员也应启用规则约束。由于 GitHub 套餐和仓库归属不同，本工程不自动修改规则；须在组织设置中实施并验证。

发布任务不应由 GitOps 提交再次触发。Jenkins Git SCM 路径过滤只包含应用、受审查的构建逻辑和人工触发；测试/生产部署变更不触发新的镜像构建。

## 3. 两套集群

默认测试和生产使用不同集群，分别部署 Argo CD，Application 的 server 均为本集群 `https://kubernetes.default.svc`。不要把两套 Application 应用到同一个 Argo CD 后误以为会自动选择两个集群。

如改为集中 Argo CD，必须注册集群并修改 Application 与 AppProject 的目标 server，同时重新评估 Argo 控制面的权限和故障域。

## 4. 生产流量控制

生产以 Rollout 代替 Deployment；Service `demo-api` 是 stable，`demo-api-canary` 是 canary。Rollouts 管理服务 revision selector 和 VirtualService 权重。Argo CD 仅忽略这些明确字段，并启用 RespectIgnoreDifferences，防止把灰度权重恢复为 Git 中的初始值。

HPA 管理 Rollout replicas；Git 中不声明生产 replicas，且 Argo 忽略该字段。使用 ContainerResource 指标只根据 app 容器 CPU 扩容，避免混入 Istio sidecar 的 CPU。

首次部署没有稳定版本，Rollouts 不会执行一次完整的新旧版本灰度。第一次发布是引导发布，必须预检和人工验收；第二次发布才可验证流量比例及失败回退。

目前自动分析样例是请求数与 5xx 比例；业务上线前应添加业务成功率、延迟和关键依赖指标。低流量触发 Inconclusive 暂停，需要补足流量或有记录的人工决策，不能视为通过。

## 5. Istio 安全

业务 HTTP 8080 仅允许 Istio ingress gateway 的实际 ServiceAccount 身份，工作负载启用 STRICT mTLS，DestinationRule 使用 ISTIO_MUTUAL。默认信任域为 cluster.local；现场不同必须修改 principal。

Actuator 8081 不暴露在 Gateway 中。Prometheus 通过明确 NetworkPolicy 访问其明文指标端口；PeerAuthentication 对 8081 关闭 mTLS，AuthorizationPolicy 仅允许 GET /actuator/prometheus。这里依赖 CNI 正确执行 NetworkPolicy，必须用实际集群验证拒绝行为。

Istio 会重写 kubelet 探针。应用命名空间启用 restricted Pod Security，因此需要 Istio CNI，避免具有 NET_ADMIN 的 istio-init。安装 CNI 的平台命名空间需要符合基础设施组件的权限要求，不应照搬业务命名空间限制。

默认 NetworkPolicy 支持 CoreDNS，若使用 NodeLocal DNS、不同监控 Pod 标签、私有根证书或自定义 Istio 网关标签，需要有针对性修改，不能直接允许所有出站流量。

示例服务无数据库、缓存和消息队列，因此不放开业务出站。增加依赖时同步增加精确网络规则、超时、连接池及退出处理。

## 6. 平台可用性与容量

生产参考配置包含三副本下限、PDB、节点拓扑分散、渐进发布、HPA、资源配额。实际至少需要足够节点和空余资源承载稳定版本、灰度副本及 sidecar。3 个副本不等于跨三个可用区；只有具备正确 zone 标签和足够分区的节点才能实现跨区。

Prometheus/Alertmanager、Argo CD、Istio、Rollouts 的副本参数需要结合 chart 版本、leader election、存储与反亲和验证。不能只看副本数就宣称灾备完成。Jenkins 推荐单控制器持久化与可恢复备份、多临时 Agent；不能共享一个 JENKINS_HOME 简单水平扩控制器。

## 7. 版本与可复现性

Java 示例固定 Spring Boot 3.5.7/JDK21、Maven 插件和 PyYAML 版本；这些是可验证的工程基线，不代表永久安全版本。投产前必须升级到组织批准、仍受维护且通过漏洞门禁的补丁版本。

平台 chart 版本在 versions.env 中显式填写并评审。不要使用 latest 或无版本 helm install。现场没有集群版本信息，因此不能负责任地预设所有控制器的兼容组合。必须确认 Kubernetes 支持生命周期、Istio 版本矩阵、ESO v1beta1 CRD served 状态、Rollouts/Argo/Kyverno CRD，以及监控指标标签。

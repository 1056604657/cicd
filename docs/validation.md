# 验证记录与未验证范围

验证日期：2026-11-13。此记录仅陈述本次执行证据，不等于公司生产验收。

## 已执行

- Java 21 / Maven 3.9.9 执行 `mvn verify`：通过。6 项接口/健康测试；JaCoCo 80% 行覆盖率门禁通过。
- Python unittest：5 项测试通过，覆盖不可变 digest、防占位发布、签名证明内容匹配、两环境渲染，以及生产提升不修改测试环境。
- Kustomize 5.6.0：测试应用 9 项资源、生产应用 17 项资源渲染与交付约束检查通过。
- 两环境 AppProject/Application、平台 namespace/ESO、Istio Gateway 配置均可渲染。
- 生产配置确认使用 Rollout，HPA 管理 replicas，生成的 ConfigMap 哈希引用正确，镜像及版本注解一致。

- Kubernetes 1.31 标准 schema 与公开 CRD schema 严格校验：8 份渲染文件共 52 项资源，全部有效，无跳过项。该校验不替代现场 CRD 版本验证。
- Docker 实际构建及运行通过：UID/GID 10001、只读根文件系统、受限 /tmp、移除 capabilities、768 MiB 内存约束；HTTP/Readiness 正常，应用端口不会暴露 Actuator，独立管理端口有 Prometheus 指标，SIGTERM 正常退出。
- 容器测试运行时：`eclipse-temurin@sha256:18bb4a91a3dea3f03ee31d3755af34dfb40f904fc77ab56cdc2f092e32fff9c2`。这是测试使用的 digest，正式使用仍需组织漏洞扫描与批准。
- Python 语法编译及全部 Shell 脚本语法检查通过。
- Kyverno 镜像准入 ClusterPolicy 严格 schema 校验通过。

## 需要目标平台执行

- Jenkins Declarative 校验、Shared Library 与实际插件版本集成、凭据绑定及权限隔离。
- BuildKit、Trivy、Syft、Harbor、Cosign 的真实推送/签名/证明流程。
- GitHub 分支保护、审批、任务状态门禁和机器人权限。
- 实际 K8s/CRD 的 server-side dry-run，以及 Istio/CNI/ESO/Kyverno/Argo/Rollouts 集成。
- Prometheus 查询、canary 流量分配、分析成功/失败/样本不足行为。
- Vault 授权、证书更新、Harbor CA、签名准入拒绝场景。
- 并发发布、节点维护、扩缩容、灰度故障、回滚与平台恢复演练。
- 应用性能容量与目标 SLO；业务变更时数据库兼容性。

未在目标环境执行前，不能把这些项目标记为已通过。现场可用 `scripts/preflight-cluster.sh` 完成部分预检，再按 runbook 逐项验收。

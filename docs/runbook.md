# 发布、灰度与故障处置

## 正常发布

1. 应用 PR 审查与检查通过后合并，可信 Jenkins 构建。
2. 镜像扫描失败就停止；不要临时改 pipeline 忽略漏洞。
3. 审核并合并测试 GitOps PR，Argo CD 同步。
4. Jenkins 验证测试健康及冒烟后生成签名证明。
5. 生产提升任务输入该 digest，验证签名与测试证据，创建生产 PR。
6. 审批合并后 Argo CD 更新 Rollout；Rollouts 按 10%、50%、100% 推进。
7. 检查 Argo 状态、Rollout、AnalysisRun、业务指标、告警与发布记录。

脚本仅通过 gh 创建 PR，没有自动批准或合并生产 PR。发布成功以业务验证及 Rollout Healthy 为准。

## 观测命令

以下示例需要安装 kubectl argo rollouts 插件，并显式指定生产 context。

```bash
kubectl --context YOUR_PROD_CONTEXT argo rollouts get rollout demo-api -n demo-prod
kubectl --context YOUR_PROD_CONTEXT get analysisruns -n demo-prod
kubectl --context YOUR_PROD_CONTEXT get virtualservice demo-api -n demo-prod -o yaml
kubectl --context YOUR_PROD_CONTEXT get pods,hpa,pdb -n demo-prod
kubectl --context YOUR_PROD_CONTEXT logs -n demo-prod -l app.kubernetes.io/name=demo-api -c app --tail=100
```

从应用日志、Prometheus 和发布记录关联 digest/sourceCommit。生产环境 APP_VERSION 来自 Pod annotation，与实际部署镜像摘要保持一致。

## 灰度卡住或分析失败

- Pending：检查节点容量、拓扑约束、quota、PDB 与镜像拉取事件。
- ImagePullBackOff：检查 Harbor 网络/CA、镜像存在性和 harbor-pull 同步状态。
- Admission denied：检查签名、公钥、测试证明、Kyverno 到 Harbor 网络；不能直接删策略绕过。
- Analysis Inconclusive：样本不足。检查 canary 流量和 metrics 标签；可使用审批后的合成流量补足样本。不要无限点击 promote。
- Analysis Error：检查 Prometheus 地址、权限和网络；这是基础设施问题，不应当作业务成功。
- Analysis Failed：停止扩大流量，排查版本，并进入回滚流程。
- Argo OutOfSync：检查是否有人修改 Git 管理字段，以及 ignoreDifferences 是否仅包含 Rollouts/HPA 管理字段。

Prometheus 必须保留 `rollouts_pod_template_hash` 标签。测试查询应能区分稳定/灰度版本；否则样例分析不能用来决定生产发布。

## 主动中止与持久回滚

发生事故时，先由授权操作员中止正在进行的灰度：

```bash
kubectl --context YOUR_PROD_CONTEXT argo rollouts abort demo-api -n demo-prod
```

中止把流量退回可用的稳定 ReplicaSet，但不会自动将 Git 恢复为旧版本。随后使用生产提升任务输入上一已验证 digest，或创建针对生产 overlay 的回退 PR，同时恢复相关 ConfigMap/模板变更，审批合并后由 Argo 同步。

不得使用未经测试、无签名证据的任意镜像回滚。密钥轮换、Harbor GC、依赖变更可能使旧版本不可恢复，因此必须长期保留回滚窗口内的镜像与签名证明。

应用代码回滚不撤销数据库变更。本示例无数据库；加入数据库后必须实施 expand/contract、受控迁移任务和独立的数据恢复预案。

在正在进行的灰度期间重启/更改 HPA、修改网关路由等操作要记录并评估，避免放大事故。

## 故障与平台恢复

| 故障 | 行为与处置 |
|---|---|
| Jenkins 不可用 | 已部署应用继续运行；暂停新构建，按备份恢复控制器和凭据 |
| Git 不可用 | 已有业务继续；暂停 GitOps 变更，避免双写；恢复后核对审计记录 |
| Argo CD 不可用 | 已有工作负载继续；恢复配置与集群访问，再核对实际状态 |
| Harbor 不可用 | 已运行容器通常继续；新 Pod/扩容可能失败；恢复镜像和签名附件 |
| Vault/ESO 不可用 | 已同步 Secret 通常保留；刷新和新环境初始化受影响；检查证书到期 |
| Prometheus 不可用 | 灰度分析无法正常完成；暂停发布，修复监控后再评估 |
| Kyverno 不可用 | fail-closed 可能阻断新 Pod；恢复准入服务，使用受审计的应急流程 |
| Istio 控制面不可用 | 已有代理配置通常继续工作；新代理连接及配置更新受影响，按平台预案恢复 |

备份需覆盖 Git 元数据、Jenkins 配置及凭据加密相关文件、Harbor 数据库和对象存储、Vault 存储/恢复材料、平台 Helm values、签名密钥与信任根。备份与故障域分离并定期恢复演练。

## 必须记录的演练

- 测试失败、镜像高危漏洞和未签名镜像均不能进入生产。
- 测试成功 digest 和生产 digest 相同；生产无重复构建。
- 第二次部署能观察真实流量比例；异常版本被停止扩大。
- 灰度低样本暂停且不会被标为健康放行。
- 节点驱逐、Pod 优雅终止和 HPA 行为符合目标。
- NetworkPolicy 与 Istio AuthorizationPolicy 均有实际拒绝样本。
- 旧镜像、配置、签名附件能在回滚窗口内取回。
- Argo 恢复后不会重置正在管理的灰度权重或 HPA 副本数。

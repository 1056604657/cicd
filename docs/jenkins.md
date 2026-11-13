# Jenkins 接入手册

## 插件与控制器

在受维护的 Jenkins LTS 上固定兼容的插件版本。至少需要 Pipeline/Declarative、Git、Credentials Binding、Pipeline Utility Steps、JUnit、Timestamper、Pipeline Shared Groovy Libraries。部署 Jenkins 应复用企业 SSO、RBAC、持久化存储、备份和日志审计。

控制器不执行构建。按 `jenkins/agent/README.md` 准备工具与隔离 Agent。首次接入须在 Jenkins 执行 Declarative Pipeline 校验；本仓离线测试不等于 Jenkins 插件集成测试。

## Shared Library

1. 在受保护的发布 Folder 内配置名为 platform-ci 的 Folder-level Library。
2. Modern SCM 指向本仓；Library Path 为 jenkins/shared-library。
3. 默认版本使用平台团队审核过的完整 commit SHA，禁止调用方覆盖版本。
4. 应用开发人员不拥有发布 Folder 配置、脚本审批、凭据或 Library 管理权限。
5. PR 检查使用隔离 Folder 和 Agent；不要给不可信分支绑定发布凭据。

将库拆到独立仓库时，库目录 contents 放在该仓根目录后修改 Library Path。

## 三类任务

| 任务 | Jenkinsfile | SCM 与触发 |
|---|---|---|
| demo-api-check | jenkins/Jenkinsfile.ci | PR/分支检查；无发布凭据 |
| demo-api-release | Jenkinsfile | 受保护 main；应用变更触发或人工运行 |
| demo-api-promote-prod | jenkins/Jenkinsfile.promote-prod | 受保护 main；授权人员输入 RELEASE_DIGEST |

release 任务 SCM 必须固定主分支，不允许用户传任意分支或任意 Jenkinsfile。Git 插件 Polling/触发路径过滤至少排除 gitops/**、argocd/** 和纯文档变化，避免测试 PR 合并后再次构建形成循环。若使用 GitHub webhook 直接触发，应在任务触发器同样实施路径条件。

推荐需要构建的路径：demo-java/**、Jenkinsfile、scripts/build-image.sh；Shared Library 变更单独评审、升级 pin，并按需人工验证。生产 promotion 不绑定源码仓库 webhook。

同一个环境的发布 PR 按顺序合并，启用过期分支必须更新/merge queue 等治理。disableConcurrentBuilds 仅约束单任务，不替代跨任务/跨服务的 Git 审批与合并队列。

## 凭据清单

| Jenkins ID | 类型 | 用途 |
|---|---|---|
| harbor-ci-push | Username/password | 项目限定推送与签名附件写入 |
| harbor-ci-read | Username/password | 生产提升验签时只读 |
| github-gitops-pr-token | Secret text | 指定仓库 Contents 写入、Pull requests 写入；不得绕过保护 |
| argocd-test-readonly-token | Secret text | 仅 GET 测试 Application |
| cosign-build-private-key | Secret file | 构建签名私钥 |
| cosign-build-password | Secret text | 构建签名私钥口令 |
| cosign-test-private-key | Secret file | 测试证据签名私钥，独立于构建密钥 |
| cosign-test-password | Secret text | 测试密钥口令 |
| cosign-build-public-key | Secret file | 校验构建签名的固定信任根 |
| cosign-test-public-key | Secret file | 校验测试证明的固定信任根 |

私钥由平台在安全环境生成，存入凭据系统。公钥提交到生产准入策略；更换公钥需要审批并考虑旧版本回滚。机器人 Token 优先使用短期 GitHub App installation token；本工程使用 GH_TOKEN 接口，可由企业凭据机制注入。不要把 Token 粘贴进 Git URL 或日志。

Jenkins 和 GitOps PR bot 都没有生产 kubeconfig。测试观察 Token 也不能同步或修改 Argo Application。Argo CD values 定义了 jenkins-observer 的只读权限；Token 由平台管理员创建并定期轮换。

## 构建与证据

release 流水线执行 Maven 测试和覆盖率 → 密钥扫描 → rootless BuildKit → SBOM → HIGH/CRITICAL 镜像漏洞门禁 → 推送 → 构建签名 → 测试 PR。

镜像扫描无自动忽略未修复漏洞。遇到漏洞应升级依赖或走有期限的例外流程，而非关闭门禁。

PR 合并后，流水线通过 Argo 只读 API 检查测试应用健康及目标 digest，再进行 5 次 HTTPS 冒烟，响应版本必须与 digest 一致。只有此后才使用独立测试密钥签名证明。

生产任务先验证构建签名与测试证明的签名、subject digest、环境、测试结果和源码 SHA，随后创建生产 PR。审批发生在 Git，不再重复设置 Jenkins input。

构建签名采用企业持有密钥，不上传公共透明日志；校验显式忽略公共 tlog，但仍校验签名与镜像 subject。生产的私有透明日志/KMS/HSM 可进一步接入。

Harbor 要配置业务镜像标签不可变。Cosign 2.x 的签名/证明附件可能使用 sha256-*.sig/.att 等标签，不能直接用覆盖所有标签的不可变规则阻止证明追加；应按所用 Cosign/Harbor 版本设计规则并测试签名、证明及垃圾回收。

# CHANGES.md

本文件记录 RobotOps AI 项目的阶段性变更。每完成一个阶段，都必须更新本文件并提交 Git。

## 2026-07-30 阶段 0：项目重新定位与文档约束

修改内容：

- 新建 `RobotBugOps` 项目目录。
- 将项目正式定位为 `RobotOps AI 机器人智能运维与诊断平台`。
- 明确项目不是单纯 Bug 日志分析工具，而是覆盖研发测试阶段和售后运维阶段的一体化平台。
- 明确第一阶段以 Bug 单、日志包、源码关联、AI 诊断为核心。
- 明确第二阶段扩展机器人实时状态、模块心跳、事件告警、售后工单和远程诊断。
- 明确主前端改为 Web 管理台，不再使用 Qt 作为主前端。
- 明确继续参考旧 `DeviceOps` 项目和 `cpp-microservice-kit` 脚手架能力。
- 在 `AGENTS.md` 中写入项目定位、技术路线、模块分层、开发环境、前端方向、Git 提交规范和每次开发注意事项。

原因：

- 原 DeviceOps 项目定位偏通用设备运维，和真实机器人研发测试流程不够贴合。
- 真实业务流程是测试人员提交飞书 Bug，开发工程师基于机器人类型、发生时间、日志包和源码分析问题。
- 后续机器人售出后，平台仍需要扩展为实时运维和售后诊断系统，所以不能只设计成日志分析工具。

影响范围：

- 项目定位。
- 文档结构。
- 后续架构设计方向。
- 前端技术方向。
- 后续 Codex 开发协作规范。

下一步：

- 完善 `docs/` 中的需求文档、架构文档和 MVP 开发计划。
- 将 Web 前端方向写入独立前端设计文档。
- 参考 DeviceOps 的 brpc/protobuf 接口风格，后续再设计新项目 proto。
- 正式开始代码阶段前初始化或关联 Git 仓库。

是否已提交 Git：

- 是。已纳入阶段 0 初始提交。

## 2026-07-30 阶段 0 补充：README 和 Web 前端方向

修改内容：

- 参考 `qinshihu/itops-agent-platform` 的项目表达方式，重写 `README.md`。
- README 从业务痛点、两阶段定位、能力地图、典型诊断场景、技术栈、服务规划和当前状态几个方面描述项目。
- 新增 `docs/05_web_frontend_design.md`，明确主前端使用 Web 管理台，不再使用 Qt。
- 在 MVP 计划中补充“文档优先”验收标准。
- 在 MVP 计划中补充售后运维扩展阶段。

原因：

- 当前阶段先完成文档设计，再进入开发。
- 新项目需要像正式平台项目一样清楚说明业务闭环，而不是只堆服务名和技术栈。
- Web 管理台比 Qt 更适合展示机器人运维平台、Bug 分析、日志检索、AI 诊断报告和售后工单。

影响范围：

- `README.md`
- `docs/04_mvp_plan.md`
- `docs/05_web_frontend_design.md`
- 后续前端开发方向

下一步：

- 继续完善需求、架构和数据模型文档。
- 后续再设计 proto 和服务接口。
- 代码开发前初始化 Git 仓库，并按阶段提交。

是否已提交 Git：

- 是。已纳入阶段 0 初始提交。

## 2026-07-30 阶段 0 补充：开发交接指导

修改内容：

- 新增 `docs/06_development_guide.md`。
- 明确后续开发前的文档阅读顺序。
- 明确 C++ 后端、Python Agent、Web 前端、数据存储和 Git 提交规范。
- 明确继续沿用 DeviceOps/dev 环境中的 brpc/protobuf 和 `cpp-microservice-kit` 思路。
- 明确当前仍处于文档阶段，暂不写业务代码。

原因：

- 后续开发可能由另一个 Codex 窗口完成，需要一份清晰的交接文档。
- 新项目与旧 DeviceOps 在同一套环境下重新开发，必须继承已有联调经验和脚手架约束。
- 用户要求每个阶段都记录变更，并在阶段完成后提交 Git。

影响范围：

- `docs/06_development_guide.md`
- `README.md`
- 后续开发协作流程

下一步：

- 继续完善 API/proto 设计文档。
- 完成全部文档后初始化或关联 Git 仓库并提交阶段 0。

是否已提交 Git：

- 是。已纳入阶段 0 初始提交。

## 2026-07-30 阶段 0 提交准备：初始化仓库

修改内容：

- 将 `reference_projects/` 加入 `.gitignore`，避免把 interaction、aimrt_agent 等参考源码误提交到新仓库。
- 为 `backend/`、`agent_service/`、`samples/`、`scripts/` 添加 `.gitkeep`，保留后续开发目录结构。
- 将阶段 0 文档变更标记为已纳入初始提交。

原因：

- `reference_projects/` 仅用于本地理解机器人模块，不属于 RobotOps AI 新项目源码。
- 新仓库第一次提交应保持轻量，只包含项目文档、规范和必要目录骨架。

影响范围：

- `.gitignore`
- `backend/.gitkeep`
- `agent_service/.gitkeep`
- `samples/.gitkeep`
- `scripts/.gitkeep`
- `CHANGES.md`

下一步：

- 初始化 Git 仓库。
- 关联远端 `ITwei6/RobotOps-AI.git`。
- 提交并推送阶段 0 文档。

是否已提交 Git：

- 是。已纳入阶段 0 初始提交。

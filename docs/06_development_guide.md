# 开发交接指导

本文档用于指导后续开发阶段。当前项目已进入后端服务开发阶段。

## 1. 开发前阅读顺序

任何开发者或 Codex 窗口开始写代码前，必须按顺序阅读：

1. `AGENTS.md`
2. `README.md`
3. `CHANGES.md`
4. `docs/01_product_definition.md`
5. `docs/02_architecture.md`
6. `docs/03_data_model.md`
7. `docs/04_mvp_plan.md`
8. `docs/05_web_frontend_design.md`
9. `docs/06_development_guide.md`
10. `docs/08_agent_service_focus.md`

如果涉及旧项目经验，继续阅读：

```text
../DeviceOps/README.md
../DeviceOps/docs/04_development_guide.md
../DeviceOps/docs/06_backend_runbook.md
../DeviceOps/docs/07_agent_rag_design.md
```

如果涉及 C++ 脚手架，继续阅读：

```text
../cpp-microservice-kit/README.md
../cpp-microservice-kit/source/
```

## 2. 开发原则

必须遵守：

- 项目定位是机器人智能运维与诊断平台，不是普通设备后台。
- 第一阶段先跑通研发测试 Bug 诊断闭环。
- 第二阶段再扩展部署运维实时监控和远程运维。
- C++ 后端继续使用 brpc/protobuf 和 `cpp-microservice-kit`。
- Python 只负责 Agent/RAG/源码分析，不直接承担核心业务落库。
- Web 是主前端，Qt 不进入 MVP。
- 每个阶段完成后必须更新 `CHANGES.md` 并提交 Git。

禁止事项：

- 不要切换成 Java 技术栈。
- 不要把项目缩成单纯日志搜索工具。
- 不要把项目写回通用设备温度/电量监控平台。
- 不要让前端直接访问 MySQL、Redis、Elasticsearch、RabbitMQ、Milvus。
- 不要让 Agent 编造没有日志或源码证据的结论。
- 不要在没有记录 `CHANGES.md` 的情况下完成阶段。

## 3. 推荐开发顺序

### 3.1 阶段 0：文档设计

目标：

- 完成项目定位、需求、架构、数据模型、前端设计和开发规范。

验收：

- README 能讲清业务闭环。
- AGENTS 写清项目规则。
- CHANGES 记录每次阶段变化。
- 暂不写业务代码。

### 3.2 阶段 1：工程骨架

目标：

- 初始化 Git 仓库或关联远端。
- 建立 C++ 后端工程骨架。
- 建立 Python agent-service 骨架。
- 建立 Web 前端工程骨架。
- 保持 README 和 CHANGES 更新。

建议提交：

```text
chore(project): setup robotops project skeleton
```

### 3.3 阶段 2：日志包解析闭环

目标：

- 支持导入本地 `robot_日期` 日志目录。
- 识别模块目录。
- 解析 `interaction.log`、`mc.log`、`agent.log`、`hds.log` 等日志。
- 输出结构化日志。

验收：

- 能识别模块名。
- 能解析日志级别和原始行。
- 能按模块查询日志。

建议提交：

```text
feat(log): parse robot module log packages
```

### 3.4 阶段 3：Bug 诊断闭环

目标：

- 创建 Bug 单。
- 关联机器人类型、问题模块、发生时间和日志包。
- 根据时间窗口提取日志上下文。
- Python Agent 输出初版诊断报告。

验收：

- 输入 Bug 描述和日志包后，能生成结构化诊断报告。
- 报告包含日志证据。

建议提交：

```text
feat(diagnosis): generate bug diagnosis reports
```

### 3.5 阶段 4：源码关联

目标：

- 根据日志关键句检索源码仓库。
- 输出源码文件、函数和相关代码片段。
- 诊断报告包含源码证据。

验收：

- 对 interaction 日志能定位到对应源码文件。
- 报告能说明源码逻辑为什么导致该现象。

建议提交：

```text
feat(agent): link logs with source evidence
```

### 3.6 阶段 5：Web 工作台

目标：

- 实现 Web 前端核心页面。
- 支持 Bug 创建、日志包查看、日志检索、诊断报告展示。

验收：

- 能完整演示“Bug -> 日志 -> AI 诊断报告”。

建议提交：

```text
feat(web): build robot diagnosis console
```

### 3.7 阶段 6：部署运维扩展

目标：

- 引入机器人资产。
- 引入模块心跳和实时状态。
- 引入事件告警和现场工单。

验收：

- 能展示机器人在线状态。
- 能展示 agent/interaction/mc/hal/sm/hds 模块状态。
- 能从告警发起诊断。

建议提交：

```text
feat(ops): add robot realtime monitoring workflow
```

## 4. 后端设计注意点

### 4.0 Docker 编译规范

后端开发环境不是 Ubuntu 宿主机。Ubuntu 虚拟机只是 Codex 和 Docker 的运行入口，C++ 后端服务必须在 `dev-env-service` 容器中编译、运行和测试。

Ubuntu 宿主机禁止直接执行：

```text
cmake
make
gcc/g++
运行 C++ 后端服务
```

开发容器名称：

```text
dev-env-service
```

推荐代码映射：

```text
Ubuntu 宿主机：
~/Desktop/projects/RobotOps-AI

Docker 容器：
/home/dev/workspace/projects/RobotOps-AI
```

正确编译方式：

```bash
docker exec dev-env-service bash -lc "
cd /home/dev/workspace/projects/RobotOps-AI &&
mkdir -p build &&
cd build &&
cmake .. &&
make -j\$(nproc)
"
```

如果项目实际路径不同，先进入容器确认：

```bash
docker exec -it dev-env-service bash
pwd
ls /home/dev/workspace
ls /home/dev/workspace/projects
```

如果 `cpp-microservice-kit` 路径未找到，继续在容器内查：

```bash
cd /home/dev/workspace
find . -maxdepth 5 -path '*cpp-microservice-kit/CMakeLists.txt'
```

如果后端 CMake 已支持 `CPP_MICROSERVICE_KIT_DIR`，推荐显式传入：

```bash
cmake -S . -B build -DCPP_MICROSERVICE_KIT_DIR=<容器内实际cpp-microservice-kit路径>
cmake --build build -j1
```

关键原则：

- 优先使用 `cpp-microservice-kit` 已有能力，不要自己重复封装 brpc、protobuf、日志、配置、MySQL、Redis、ES、RabbitMQ。
- 缺少能力时先检查脚手架是否已有实现，再决定是否补充脚手架。
- 所有后端路径以 Docker 容器内路径为准。
- 虚拟机和开发环境容器的登录凭据通过安全渠道获取，不写入仓库文档。

### 4.1 brpc HTTP JSON

后端接口继续保持 brpc/protobuf 风格，并支持 HTTP JSON 调用。

原因：

- 旧 DeviceOps 已经验证过这种方式。
- Web 前端可以直接通过 HTTP JSON 调试。
- Windows/PowerShell 联调更方便。

### 4.2 proto 契约

后续设计 proto 时遵守：

- 字段命名使用 snake_case。
- 通用响应使用 `CommonResponse`。
- 分页使用 `PageRequest` / `PageResponse`。
- 时间使用毫秒时间戳或明确说明时区。
- 研发阶段 `robot_id` 不强制必填，但接口预留 `robot_sn`。
- 必须包含 `robot_type`、`module_name`、`occurred_time` 等核心字段。

### 4.3 数据存储

第一阶段建议：

```text
MySQL:
  Bug 单、日志包、诊断任务、诊断报告、源码仓库元数据

Elasticsearch:
  多模块日志索引

Redis:
  日志解析任务状态、诊断任务状态

本地文件 / MinIO:
  原始日志包和解压后的日志文件
```

第二阶段扩展：

```text
Redis:
  机器人实时状态、模块心跳

RabbitMQ:
  异步日志、事件、诊断任务

Milvus/Chroma:
  源码片段、知识库、历史案例向量检索
```

## 5. Agent 设计注意点

从阶段 3 开始，后续开发重点转向 `agent-service`。C++ 服务主要负责平台入口、日志、任务和报告保存，Agent 才是 RobotOps AI 的核心诊断能力。

Agent 的输入不是一句简单问题，而是完整诊断上下文：

```text
Bug 描述
机器人类型
发生时间
问题模块
日志上下文
源码仓库
历史案例
知识库
```

Agent 输出必须结构化：

```text
summary
suspected_module
possible_causes
evidence_logs
evidence_sources
recommended_actions
confidence
questions_for_human
```

Agent 必须遵守：

- 没有证据就降低置信度。
- 日志证据必须引用模块、文件、行号或原始日志。
- 源码证据必须引用仓库、文件、函数或匹配语句。
- 不直接修改源码。
- 不直接写业务数据库。

## 6. Web 前端开发注意点

Web 前端第一屏应是工作台，不是营销页。

优先展示：

- 待处理 Bug
- 最近日志包
- 诊断任务状态
- 高风险诊断
- 最近告警预留

AI 报告展示不能只放一段文本，必须分区展示：

- 结论
- 证据
- 源码
- 建议
- 置信度

## 7. Git 和 CHANGES 规范

每个阶段结束时：

1. 更新 `CHANGES.md`。
2. 检查 `git status`。
3. 只提交当前阶段相关文件。
4. 使用清晰 commit message。

不要使用：

```text
update
misc
changes
```

推荐：

```text
docs(readme): describe robotops diagnosis workflow
docs(frontend): define web console design
docs(architecture): add realtime ops extension
```

如果当前项目尚未初始化 Git，需要先与用户确认远端仓库，再执行：

```text
git init
git remote add origin <repo>
```

## 8. 当前状态

当前已进入后端开发阶段。

已完成：

- 阶段 1：`log-service` 初版，支持已解压机器人日志目录导入、查询、上下文和文件列表。
- 阶段 2：`ticket-diagnosis-service` 初版，支持 Bug 单、诊断任务和诊断报告的内存版接口。
- 阶段 3：`agent-service` 初版，支持 FastAPI `/health` 和 `/diagnose`，基于 interaction 规则模板生成结构化诊断报告。
- 阶段 4：`ticket-diagnosis-service` 支持 `RunDiagnosis`，可同步调用 `agent-service` 并保存报告。

下一步应该继续：

- 优先增强 `agent-service`，不要过早继续拆分大量 C++ 服务。
- 让 `agent-service` 主动调用 `log-service` 获取 occurred_time 前后日志上下文。
- 增加 interaction 源码检索、历史案例和知识库/RAG。
- 后续再接入 MySQL、Elasticsearch、Redis 和 RabbitMQ。

# CHANGES.md

本文件记录 RobotOps AI 项目的阶段性变更。每完成一个阶段，都必须更新本文件并提交 Git。

## 2026-07-30 阶段 0：项目重新定位与文档约束

修改内容：

- 新建 `RobotBugOps` 项目目录。
- 将项目正式定位为 `RobotOps AI 机器人智能运维与诊断平台`。
- 明确项目不是单纯 Bug 日志分析工具，而是覆盖研发测试阶段和部署运维阶段的一体化平台。
- 明确第一阶段以 Bug 单、日志包、源码关联、AI 诊断为核心。
- 明确第二阶段扩展机器人实时状态、模块心跳、事件告警、现场工单和远程诊断。
- 明确主前端改为 Web 管理台，不再使用 Qt 作为主前端。
- 明确继续参考旧 `DeviceOps` 项目和 `cpp-microservice-kit` 脚手架能力。
- 在 `AGENTS.md` 中写入项目定位、技术路线、模块分层、开发环境、前端方向、Git 提交规范和每次开发注意事项。

原因：

- 原 DeviceOps 项目定位偏通用设备运维，和真实机器人研发测试流程不够贴合。
- 真实业务流程是测试人员提交飞书 Bug，开发工程师基于机器人类型、发生时间、日志包和源码分析问题。
- 后续机器人交付后，平台仍需要扩展为实时运维和远程诊断系统，所以不能只设计成日志分析工具。

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
- 在 MVP 计划中补充部署运维扩展阶段。

原因：

- 当前阶段先完成文档设计，再进入开发。
- 新项目需要像正式平台项目一样清楚说明业务闭环，而不是只堆服务名和技术栈。
- Web 管理台比 Qt 更适合展示机器人运维平台、Bug 分析、日志检索、AI 诊断报告和现场工单。

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

## 2026-07-30 阶段 1：log-service 日志包解析服务

修改内容：

- 新增顶层 `CMakeLists.txt`，沿用 `cpp-microservice-kit` 和 brpc/protobuf 构建思路。
- 新增 `proto/common.proto` 和 `proto/log.proto`。
- 新增 `backend/services/log_service/` 子服务。
- 实现 `LogService.ImportLogPackage`，支持导入已解压的机器人日志目录。
- 实现 `LogService.QueryLogs`，支持按 Bug、日志包、模块、级别、关键词和时间范围查询。
- 实现 `LogService.GetLogContext`，支持按中心时间提取前后日志上下文。
- 实现 `LogService.ListLogFiles`，支持查看日志包中识别出的模块日志文件。
- 新增样例日志目录 `samples/robot_20260730/`，包含 `interaction`、`mc`、`agent`、`hds` 四个模块日志。
- 更新 `AGENTS.md` 当前阶段说明，进入后端开发阶段。

原因：

- log-service 是 RobotOps AI 第一阶段 Bug 日志分析闭环的核心服务。
- 研发测试阶段的主要输入是测试上传的完整日志包，必须先具备日志包解析、模块识别和上下文查询能力。
- 第一版先实现本地目录导入和内存索引，后续再接入 Elasticsearch、MySQL 和日志包压缩文件解压。

影响范围：

- `CMakeLists.txt`
- `proto/common.proto`
- `proto/log.proto`
- `backend/services/log_service/`
- `samples/robot_20260730/`
- `AGENTS.md`

当前限制：

- MVP 当前只支持已解压日志目录，暂不直接解析 `.zip` / `.tar.gz`。
- 当前日志索引保存在服务内存中，服务重启后需要重新导入日志包。
- 当前尚未接入 Elasticsearch、MySQL、Redis 和 RabbitMQ。

验证结果：

- 已尝试在当前 Windows shell 执行 `cmake -S . -B build`，但本机没有 `cmake` 命令。
- 已尝试检查 Docker 开发容器，但本机没有 `docker` 命令。
- 因此本阶段未完成编译验证，需要在 Linux/dev 容器中执行 CMake 构建。

下一步：

- 在 Linux/dev 容器中验证 CMake 构建。
- 根据验证结果修正编译问题。
- 下一阶段开发 `ticket-diagnosis-service`，建立 Bug 单和诊断任务入口。

是否已提交 Git：

- 是。已纳入阶段 1 log-service 提交。

## 2026-07-30 阶段 1 补充：Linux 后端开发交接

修改内容：

- 新增 `docs/07_backend_linux_handoff.md`。
- 记录 Linux 容器中 `cmake` 失败的原因：`cpp-microservice-kit` 路径被硬编码为不存在的 `/home/dev/workspace/cpp-microservice-kit`。
- 给出推荐修复方案：将 `CPP_MICROSERVICE_KIT_DIR` 改为 CMake cache path，并支持自动探测多个候选路径。
- 写明 log-service 当前能力、限制、编译方式、curl 验证方式。
- 写明后续每个子服务一个阶段的开发顺序和提交要求。

原因：

- 用户准备在 Linux 环境开启新的 Codex 窗口继续后端开发，需要明确交接当前状态。
- Linux 环境可以直接编译测试，必须先修复构建路径问题再继续开发新服务。

影响范围：

- `docs/07_backend_linux_handoff.md`
- `README.md`
- `CHANGES.md`

下一步：

- Linux Codex 先修复顶层 CMake 脚手架路径探测。
- 完成 log-service 编译、启动和 HTTP JSON 接口验证。
- 更新 `CHANGES.md` 后提交并推送。

是否已提交 Git：

- 是。已纳入阶段 1 Linux 交接文档提交。

## 2026-07-30 阶段 1 补充：Docker 容器编译规范

修改内容：

- 在 `AGENTS.md` 中补充 Docker 开发环境强制规范，明确后端不能在 Ubuntu 宿主机直接编译。
- 在 `docs/06_development_guide.md` 中补充 `dev-env-service` 容器编译命令、路径映射、脚手架查找方式。
- 在 `docs/07_backend_linux_handoff.md` 中补充给 Linux Codex 使用的容器编译流程。
- 明确虚拟机和开发环境容器凭据不写入仓库文档。

原因：

- 后端依赖 `cpp-microservice-kit`、brpc、protobuf 和容器内统一基础库，必须通过 Docker 开发容器保证环境一致。
- 后续每个子服务都是独立开发阶段，需要统一编译入口，避免另一个 Codex 窗口在 Ubuntu 宿主机误执行 `cmake` 或 `make`。

影响范围：

- `AGENTS.md`
- `docs/06_development_guide.md`
- `docs/07_backend_linux_handoff.md`
- `CHANGES.md`

下一步：

- Linux Codex 进入 `dev-env-service` 容器后，先修复 `CPP_MICROSERVICE_KIT_DIR` 路径探测，再继续编译验证 log-service。

是否已提交 Git：

- 是。已纳入 Docker 容器编译规范文档提交。

## 2026-07-30 阶段 1 补充：log-service 容器编译验证与构建修复

修改内容：

- 将顶层 `CMakeLists.txt` 中的 `CPP_MICROSERVICE_KIT_DIR` 改为 CMake cache path，并支持多个候选路径自动探测。
- 新增 `ROBOTOPS_USE_FULL_CPP_MICROSERVICE_KIT` 构建选项。
- 默认使用 `cpp-microservice-kit` 的 `log.cc` 和 `rpc.cc` 组成最小脚手架目标，避免当前 log-service 被 FFmpeg、ODB、MQTT 等未使用依赖阻塞。
- 调整 `log-service` 链接目标为 `${ROBOTOPS_SCAFFOLD_TARGET}`。
- 在 `dev-env-service` Docker 容器内完成 `log_service` 编译和 HTTP JSON 接口验证。

原因：

- `cpp-microservice-kit` 当前全量 CMake 会检查 MQ、ES、FastDFS、FFmpeg、ODB、Redis、MQTT 等依赖，其中容器缺少 `avcodec`，导致只依赖日志和 RPC 的 log-service 也无法配置。
- 当前阶段应先保证日志包解析服务在统一容器环境中可编译、可启动、可验证。
- 后续如果服务需要全量脚手架能力，可以打开 `ROBOTOPS_USE_FULL_CPP_MICROSERVICE_KIT=ON` 或补齐容器依赖。

影响范围：

- `CMakeLists.txt`
- `backend/services/log_service/CMakeLists.txt`

验证结果：

- 已在 `dev-env-service` 容器内执行：

```text
cmake -S . -B build -DCPP_MICROSERVICE_KIT_DIR=/home/dev/workspace/cpp-microservice-kit
cmake --build build -j1
```

- `log_service` 编译成功。
- `ROBOTOPS_LOG_RPC_PORT=9501` 启动成功。
- `ImportLogPackage` 导入 `samples/robot_20260730` 成功，识别 4 个日志文件和 10 条日志。
- `QueryLogs` 按 `interaction` 模块查询成功。
- `QueryLogs` 按 `PASSIVE_DEFAULT` 关键词查询成功，命中 `interaction` 和 `mc` 日志。
- `GetLogContext` 按中心时间窗口查询成功。
- `ListLogFiles` 查询日志文件列表成功。

当前限制：

- 默认构建当前只链接 log/rpc 最小脚手架源码，暂未启用全量脚手架依赖。
- log-service 仍是内存索引，尚未接入 Elasticsearch / MySQL / Redis / RabbitMQ。

下一步：

- 开发 `ticket-diagnosis-service`，建立 Bug 单、诊断任务和报告保存入口。

是否已提交 Git：

- 是。已纳入本次阶段提交。

## 2026-07-30 阶段 2：ticket-diagnosis-service Bug 与诊断任务服务

修改内容：

- 新增 `proto/ticket_diagnosis.proto`。
- 新增 `backend/services/ticket_diagnosis_service/` 子服务。
- 实现 `TicketDiagnosisService.CreateBugTicket`，支持创建研发 Bug 单。
- 实现 `TicketDiagnosisService.GetBugTicket` 和 `ListBugTickets`，支持按机型、主模块、状态和关键词查询。
- 实现 `TicketDiagnosisService.CreateDiagnosisTask` 和 `GetDiagnosisTask`，支持创建诊断任务并预留 `agent_request_id`。
- 实现 `TicketDiagnosisService.SaveDiagnosisReport` 和 `GetDiagnosisReport`，支持保存和查询结构化诊断报告。
- 诊断报告结构包含疑似责任模块、摘要、可能原因、日志证据、源码证据、建议、置信度和人工确认问题。
- 更新 `README.md`、`docs/06_development_guide.md` 和 `AGENTS.md` 的当前阶段说明。

原因：

- 真实研发流程从飞书 Bug 工单开始，ticket-diagnosis-service 是把 Bug 描述、发生时间、机器人类型、主模块、日志包和源码仓库串起来的入口。
- 第一阶段 log-service 只解决日志包解析和查询，下一步必须建立 Bug 单和诊断任务模型，才能形成 `Bug -> 日志上下文 -> Agent -> 诊断报告` 的闭环。
- MVP 阶段不强制要求 `robot_sn`，但接口保留字段以支持后续部署运维阶段。

影响范围：

- `CMakeLists.txt`
- `proto/ticket_diagnosis.proto`
- `backend/services/ticket_diagnosis_service/`
- `README.md`
- `docs/06_development_guide.md`
- `AGENTS.md`
- `CHANGES.md`

当前限制：

- 当前 Bug、诊断任务和诊断报告保存在服务内存中，服务重启后数据丢失。
- 当前只预留 Agent 调用字段，尚未真正调用 Python `agent-service`。
- 当前尚未接入 MySQL、Redis、RabbitMQ。

验证结果：

- 已在 `dev-env-service` 容器内完成 `ticket_diagnosis_service` 编译。
- `ROBOTOPS_TICKET_DIAGNOSIS_RPC_PORT=9502` 启动成功。
- `CreateBugTicket` 创建 `interaction` 主模块的 T 型机器人 Bug 成功。
- `ListBugTickets` 按 `main_module=interaction` 和关键词查询成功。
- `GetBugTicket` 查询 Bug 详情成功。
- `CreateDiagnosisTask` 创建 `diag-task-000001` 成功，状态为 `TASK_STATUS_PENDING`。
- `SaveDiagnosisReport` 保存带 interaction 日志证据和源码证据的报告成功。
- `GetDiagnosisReport` 按 `bug_id` 查询报告成功。
- `GetDiagnosisTask` 验证报告保存后任务状态更新为 `TASK_STATUS_SUCCEEDED`。

下一步：

- 开发 Python `agent-service`，提供 `/health` 和 `/diagnose`。
- 第一版 Agent 先基于 Bug 描述、机器人类型、主模块、日志证据和 interaction 源码规则生成结构化诊断报告。
- 后续再由 `ticket-diagnosis-service` 编排调用 agent-service，并将报告落库。

是否已提交 Git：

- 是。已纳入本次阶段提交。

## 2026-07-30 阶段 3：agent-service 规则模板诊断服务

修改内容：

- 新增 `agent_service/requirements.txt`。
- 新增 Python 包 `agent_service/app/`。
- 新增 FastAPI 服务入口 `agent_service/app/main.py`。
- 新增 Pydantic 请求响应模型 `agent_service/app/models.py`。
- 新增规则模板诊断核心 `agent_service/app/rules.py`。
- 新增单元测试 `agent_service/tests/test_rules.py`。
- 新增 `agent_service/README.md`，说明当前 Agent 技术路线和后续 LangGraph / LangChain 演进方式。
- 更新 `AGENTS.md` 当前阶段说明。

原因：

- RobotOps AI 第一阶段需要把 `Bug -> 日志上下文 -> Agent -> 诊断报告` 跑通。
- 当前真实排障重点是 interaction 研发 Bug，第一版 Agent 应优先基于明确日志证据和源码位置输出结构化报告，而不是直接接大模型生成不可追溯文本。
- 规则模板版可以先覆盖 `CheckTouch`、self check、低电量/充电、TaskFactory、WorkerManager、ActionSkill、MoveSkill 等 interaction 常见链路。

影响范围：

- `agent_service/`
- `AGENTS.md`
- `CHANGES.md`

当前能力：

- `GET /health` 返回服务健康状态。
- `POST /diagnose` 接收 Bug 上下文、日志证据、源码证据、历史案例和知识文本。
- 命中规则时输出结构化诊断报告：
  - `summary`
  - `suspected_module`
  - `possible_causes`
  - `evidence_logs`
  - `evidence_sources`
  - `recommended_actions`
  - `confidence`
  - `questions_for_human`
- 证据不足时输出低置信度报告，不编造确定结论。

当前限制：

- 当前是 `rule-template-v1`，尚未接入 LLM。
- 当前尚未接入 LangGraph / LangChain。
- 当前尚未主动调用 `log-service` 或源码检索，只处理调用方传入的日志证据和源码证据。

验证结果：

- `dev-env-service` 容器原本没有 `pip`，已通过 `apt-get install -y python3-pip` 安装。
- 默认 PyPI 下载 FastAPI 超时，已使用清华 PyPI 镜像安装：

```text
python3 -m pip install --default-timeout 180 -i https://pypi.tuna.tsinghua.edu.cn/simple -r agent_service/requirements.txt
```

- 已在容器内执行单元测试：

```text
python3 -m unittest discover -s agent_service/tests
```

- 测试结果：2 个测试通过。
- 已验证 FastAPI app 可导入。
- 已启动：

```text
python3 -m uvicorn agent_service.app.main:app --host 0.0.0.0 --port 9601
```

- `GET /health` 验证通过。
- `POST /diagnose` 使用 interaction 触摸拦截日志验证通过，输出 `suspected_module=interaction`、`T1Checker::CheckTouch` 源码提示和 `confidence=0.92`。

下一步：

- 将 `ticket-diagnosis-service` 编排调用 `agent-service`。
- 给 `agent-service` 增加日志检索工具，从 `log-service` 拉取 occurred_time 前后上下文。
- 后续引入 LangGraph 编排诊断流程，LangChain 用作日志检索、源码检索、知识库/RAG 和历史案例工具封装。

是否已提交 Git：

- 是。已纳入本次阶段提交。

## 2026-07-30 阶段 4：Agent 诊断闭环编排

修改内容：

- 在 `AGENTS.md` 中新增“后续开发重心”，明确后续重点转向 `agent-service`。
- 新增 `docs/08_agent_service_focus.md`，记录 Agent 侧模块规划、LangGraph / LangChain 使用边界、interaction 优先知识和近期优先级。
- 在 `README.md` 和 `docs/06_development_guide.md` 中补充 Agent 优先方向。
- 扩展 `proto/ticket_diagnosis.proto`，新增 `RunDiagnosis` RPC。
- 新增 `backend/services/ticket_diagnosis_service` 的 `AgentClient`，使用 HTTP JSON 调用 FastAPI `agent-service`。
- `ticket-diagnosis-service` 新增同步诊断编排：
  - 查询 Bug 单。
  - 创建诊断任务。
  - 调用 `agent-service /diagnose`。
  - 将 Agent 返回的结构化报告保存到内存存储。
  - 更新诊断任务状态。
- `ROBOTOPS_AGENT_SERVICE_URL` 环境变量用于配置 Agent 地址，默认 `http://127.0.0.1:9601`。

原因：

- 用户明确说明本项目后续重点是 Agent 模块，不是继续堆叠后端服务。
- RobotOps AI 的核心价值在 Agent 能否复现开发工程师分析 interaction Bug 的过程。
- C++ 服务应主要负责 Bug、日志、任务和报告的入口与编排，Agent 侧负责日志证据、源码证据、历史案例、知识库/RAG 和诊断工作流。
- 阶段 3 虽然已有 agent-service，但 `ticket-diagnosis-service` 还不能真正调用它，因此需要补齐最小诊断闭环。

影响范围：

- `AGENTS.md`
- `README.md`
- `docs/06_development_guide.md`
- `docs/08_agent_service_focus.md`
- `proto/ticket_diagnosis.proto`
- `backend/services/ticket_diagnosis_service/`
- `CHANGES.md`

当前能力：

- `TicketDiagnosisService.RunDiagnosis` 可接收 Bug ID、日志证据和源码证据。
- 服务会同步调用 `agent-service /diagnose`。
- Agent 返回的报告会保存为 `DiagnosisReport`。
- 诊断任务状态会从 `PENDING` 更新为 `SUCCEEDED` 或 `FAILED`。

当前限制：

- `RunDiagnosis` 当前仍需要调用方传入日志证据和源码证据。
- `agent-service` 尚未主动调用 `log-service` 获取 occurred_time 时间窗口上下文。
- `agent-service` 尚未实现 interaction 源码自动检索、历史案例检索和 LangGraph 工作流。

验证结果：

- 已在 `dev-env-service` 容器内执行 C++ 构建：

```text
cmake --build build -j1
```

- `ticket_diagnosis_service` 编译成功。
- 复用 `agent-service` 端口 `9601`。
- 启动 `ticket-diagnosis-service`：

```text
ROBOTOPS_TICKET_DIAGNOSIS_RPC_PORT=9502
ROBOTOPS_AGENT_SERVICE_URL=http://127.0.0.1:9601
```

- `CreateBugTicket` 创建 T 型 interaction Bug 成功。
- `RunDiagnosis` 使用 interaction 触摸拦截日志调用成功。
- `RunDiagnosis` 返回 `diag-task-000001`，状态为 `TASK_STATUS_SUCCEEDED`。
- 保存报告 `diag-report-000001` 成功，报告包含：
  - `suspected_module=interaction`
  - `T1Checker::CheckTouch` 源码证据提示
  - 日志证据 `interaction.log:3`
  - `confidence=0.92`
- `GetDiagnosisReport` 按 `bug_id` 查询保存报告成功。

下一步：

- 继续重点开发 `agent-service`。
- 增加 `log_tool`，让 Agent 主动从 `log-service` 获取 Bug 发生时间前后日志上下文。
- 增加 `source_tool`，让 Agent 自动检索 interaction 源码。
- 将真实 interaction Bug 分析文档沉淀为历史案例。
- 后续引入 LangGraph 编排诊断节点，LangChain 只作为工具封装层。

是否已提交 Git：

- 是。已纳入本次阶段提交。

# CHANGES.md

本文件记录 RobotOps AI 项目的阶段性变更。每完成一个阶段，都必须更新本文件并提交 Git。

## 2026-07-31 阶段 6.2：本地 interaction 源码证据链

修改内容：

- 增强 `agent_service/app/tools/source_tool.py`：本地源码注册配置的 branch/commit 会附加到真实源码证据；没有显式 commit 时，使用本地 Git 工作区同步返回的 revision。
- 修复 C++ 函数识别：命中 `AIMRTE_WARN` 等全大写日志宏或函数体内部调用时，继续向外识别真实的 `T1Checker::CheckTouch` 等方法定义，不把日志宏或 `StateManager::GetInstance` 误报为函数名。
- 新增本地 registry 元数据、日志宏函数识别测试。
- 使用现有本地 interaction 源码完成真实 source search，确认返回 `interaction/src/scheduler/checker/t1_checker.cpp`、`T1Checker::CheckTouch` 和代码片段。

原因：

- 当前没有可用于远程 clone/pull 验证的独立源码仓库，阶段验证必须基于本地 interaction 源码完成。
- 源码证据只有在文件路径、函数名、匹配文本和上下文片段可信时，才适合进入诊断报告供开发工程师追溯。

影响范围：

- `agent_service/app/tools/source_tool.py`
- `agent_service/tests/test_tools.py`
- `README.md`
- `AGENTS.md`
- `agent_service/README.md`
- `CHANGES.md`

开发过程记录：

- 发现本地源码中日志关键句命中 `AIMRTE_WARN` 后，旧函数识别器会返回日志宏名；增加“优先识别带类名的方法定义、跳过全大写宏”的解析规则。
- 在 `dev-env-service` 容器内对现有本地 interaction 源码执行 source search，未访问远程仓库。

验证结果：

- Agent 全量测试：23 个测试全部通过。
- 本地源码 live smoke：返回 `interaction/src/scheduler/checker/t1_checker.cpp`、`T1Checker::CheckTouch` 和非空 snippet。
- `git diff --check`：待提交前执行。

下一步：

- 基于本地 interaction 源码继续沉淀 `CheckTouch`、`CheckMove`、`TaskFactory`、`WorkerManager`、`ActionSkill` 和 `MoveSkill` 的证据规则。
- 远程 Git 仓库具备后，再单独验证 clone/pull 和 branch/commit 固定。

是否已提交 Git：

- 是。本阶段记录与代码一并提交。

## 2026-07-31 阶段 6.1：源码证据真实性与 Agent 取证路由修复

修改内容：

- 修复 `agent_service/app/rules.py`：规则模板命中的 `T1Checker::CheckTouch` 等源码位置不再直接写入 `evidence_sources`，改为写入 `questions_for_human`，提示继续执行源码检索。
- 保留真实 `source_search` 结果进入 `evidence_sources` 的路径，并要求结果包含实际 `file_path`，避免把导航 hint 当成已验证源码证据。
- 修复 LangGraph planner：`source_search` 已尝试但仓库未配置或检索失败时，不再重复调用源码工具；工作流可以继续检索历史案例和知识库。
- 清理 source search 请求中的重复 `module_name` 字段。
- 更新规则和工作流测试，覆盖规则-only 无源码证据、真实工具源码证据保留、LLM 合并后证据边界和失败工具继续路由。

原因：

- 真实 DeepSeek live 验证发现，规则模板生成的源码路径和函数名只是排查方向，不能标记为已经从目标仓库检索并核验的证据。
- 源码仓库未配置时，重复 source search 会耗尽 LangGraph 工具轮次，导致历史案例和知识库无法执行。

影响范围：

- `agent_service/app/rules.py`
- `agent_service/app/workflow/nodes.py`
- `agent_service/tests/test_rules.py`
- `agent_service/tests/test_workflow.py`
- `README.md`
- `AGENTS.md`
- `CHANGES.md`

开发过程记录：

- 在不写入文件、命令行参数或测试日志的前提下，用安全注入方式完成真实 DeepSeek 三服务链路验证。
- 验证结果：`task_status=TASK_STATUS_SUCCEEDED`、`suspected_module=interaction`、日志证据 4 条、置信度 `0.75`；修复后规则 fallback 报告保留日志证据，源码证据为空，并给出 `T1Checker::CheckTouch` 的源码检索提示。
- 定位并修复 source search 失败后的重复路由，随后验证历史案例和知识库检索测试恢复通过。

验证结果：

- `dev-env-service` 容器内 Agent 全量测试：21 个测试全部通过。
- `dev-env-service` 容器内 C++ 构建：`ticket_diagnosis_service` 构建通过。
- `git diff --check`：通过。

下一步：

- 使用现有本地 `interaction` 源码目录验证 source search 和真实源码证据返回；远程 Git 仓库 URL、clone/pull、branch/commit 固定验证待仓库具备后再进行。
- 继续将 interaction 的 `CheckTouch`、`CheckMove`、`TaskFactory`、`WorkerManager`、`ActionSkill` 和 `MoveSkill` 排障经验沉淀为可检索证据与历史案例。

是否已提交 Git：

- 是。本阶段记录与代码一并提交。

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

## 2026-07-31 阶段 5.4：历史案例检索工具接入

修改内容：

- 新增 `agent_service/app/tools/case_tool.py`，支持读取配置目录中的 `.json` 和 `.jsonl` 历史案例。
- 案例检索按 Bug 标题、描述、日志关键词匹配，并对 `robot_type`、`main_module` 精确匹配加权，最多返回 20 条结果。
- 将 `case_search` 接入 LangGraph planner 和 tool executor；默认工具预算从 2 次提升到 3 次，允许完成“日志 -> 源码 -> 历史案例”的取证顺序。
- deterministic fallback 会把案例内容明确标记为“历史案例参考原因/建议”，不把历史案例当作当前 Bug 的事实证据。
- 新增 `agent_service/tests/test_case_tool.py`，覆盖案例排序和缺少案例目录时的空结果降级。
- 更新 `AGENTS.md`、`README.md`、`agent_service/README.md`，记录配置项和当前阶段。

原因：

- 真实 interaction Bug 排障高度依赖已确认案例，只有日志和源码检索仍然无法复用团队已有判断和处理经验。
- `case_search` 原先只是空结果 stub，无法验证 LangGraph 的第三类取证工具，也无法让无 LLM 环境复用历史排障建议。
- 先采用本地 JSON/JSONL 索引，保持 agent-service 独立、可测试、无需提前引入数据库；后续再替换为 knowledge-service 或向量检索后端。

影响范围：

- `agent_service/app/tools/case_tool.py`
- `agent_service/app/tools/__init__.py`
- `agent_service/app/settings.py`
- `agent_service/app/workflow/nodes.py`
- `agent_service/tests/test_case_tool.py`
- `AGENTS.md`
- `README.md`
- `agent_service/README.md`
- `CHANGES.md`

开发过程记录：

- 开发前核对了 `AGENTS.md`、`README.md`、`agent_service/README.md`、`CHANGES.md` 和 LangGraph 工作流代码，确认本阶段只扩展 agent-service 工具边界，不新增 C++ 服务。
- 首次大补丁因节点上下文顺序不匹配被 `apply_patch` 拒绝，没有产生半成品；随后拆分为工具、配置、工作流、测试四组小补丁完成修改。
- 案例文件解析只接受本地只读路径，单个文件损坏或编码异常会跳过，不阻断诊断流程。
- 宿主机使用 `py_compile` 和 `git diff --check` 完成静态检查；运行时测试按项目规范使用 `dev-env-service` 容器。

验证结果：

- `python3 -m py_compile agent_service/app/tools/case_tool.py agent_service/app/settings.py agent_service/app/workflow/nodes.py agent_service/tests/test_case_tool.py`：通过。
- `git diff --check`：通过。
- 容器内 `python3 -m unittest agent_service.tests.test_case_tool agent_service.tests.test_workflow`：7 个测试通过。
- 待文档更新后继续执行 `python3 -m unittest discover -s agent_service/tests` 全量测试。

当前限制：

- 案例库仍是本地 JSON/JSONL 文件，不支持案例管理 API、向量召回或权限控制。
- `knowledge_search` 仍是空实现。
- 本阶段没有将案例内容新增为报告独立字段；fallback 仅把案例原因和建议标记后并入文本字段，LLM 场景通过 prompt 读取完整历史案例。

下一步：

- 接入知识库/RAG 工具，统一案例和 SOP 的检索接口，并保留来源标识。
- 让 `ticket-diagnosis-service.RunDiagnosis` 携带 `log_package_id`，完成 C++ 编排到 Agent 自动取证的联调。

是否已提交 Git：

- 待本阶段全量测试通过后提交。

## 2026-07-31 阶段 5.6：RunDiagnosis 日志包自动取证联调

修改内容：

- 扩展 `proto/ticket_diagnosis.proto` 的 `RunDiagnosisRequest`，新增 `log_package_id` 字段。
- 修改 `ticket-diagnosis-service` 的 `AgentClient`：使用 `RunDiagnosisRequest.log_package_id` 作为显式值；调用方未传时，回退使用已保存 `BugTicket.log_package_id`。
- 继续复用现有 Agent workflow 的 `log_context` 工具，使 C++ `RunDiagnosis` 可以在 logs 为空时触发 `agent-service -> log-service.GetLogContext`。
- 更新 `AGENTS.md`、`README.md`、`agent_service/README.md`，明确跨服务字段传递和自动取证链路。

原因：

- `BugTicket` 虽然已经保存日志包 ID，但 `RunDiagnosisRequest` 缺少显式字段，接口调用方无法在诊断时明确指定或覆盖日志包。
- 阶段 5.2 之后 Agent 已具备按 `log_package_id` 自动取证能力，本阶段补齐 C++ RPC 到 Agent HTTP JSON 的字段贯通，形成可联调的最小闭环。
- 采用请求值优先、ticket 值兜底，兼容已有调用方和历史数据。

影响范围：

- `proto/ticket_diagnosis.proto`
- `backend/services/ticket_diagnosis_service/src/agent_client.cc`
- `AGENTS.md`
- `README.md`
- `agent_service/README.md`
- `CHANGES.md`

开发过程记录：

- 开发前检查发现已有 `BugTicket.log_package_id` 和 Agent 自动取证逻辑，但 `RunDiagnosisRequest` 没有对应字段；因此采用向后兼容的 proto 新字段方案，没有修改外部 `/diagnose` 请求结构。
- 未改动用户提供的 API key，也没有把任何凭据写入 proto、C++ 或测试。
- protobuf 重新生成和 C++ 编译按项目规范在 `dev-env-service` 容器中执行，宿主机不直接运行 CMake、make 或 C++ 编译器。

验证结果：

- 已在 `dev-env-service` 容器执行 `cmake --build build -j1 --target ticket_diagnosis_service`，protobuf 重新生成成功，`ticket_diagnosis_service` 编译链接成功。
- Agent-service 全量测试通过：16 个测试全部 `OK`。
- `git diff --check` 通过。

当前限制：

- 当前 C++ 服务仍是内存 store，尚未连接真实 MySQL/日志包持久化环境。
- 本阶段验证字段和编译链路，不代替真实 log-service、ticket-diagnosis-service、agent-service 三服务联调。

下一步：

- 启动三服务完成真实 HTTP/RPC 联调，验证空 logs 请求能按日志包 ID返回日志证据。
- 再将知识检索从本地文件扩展到 knowledge-service/向量检索。

是否已提交 Git：

- 待容器编译和测试通过后提交。

## 2026-07-31 阶段 5.7：三服务真实冒烟与 Agent 超时加固

修改内容：

- 新增 `samples/robot_20260730/`，包含 interaction、mc、agent、hds 四个模块的最小可导入日志。
- 新增 `docs/11_three_service_smoke_test.md`，记录 log-service 导入、Bug 创建、RunDiagnosis 和 Agent 自动取证的容器内验证步骤。
- 将 C++ `AgentClient` HTTP 超时从固定 5 秒改为 `ROBOTOPS_AGENT_HTTP_TIMEOUT_MS`，默认 120 秒，适配 DeepSeek 结构化报告调用。
- C++ AgentClient 的非 2xx 响应现在携带最多 512 字符响应摘要，便于定位 Agent HTTP 错误。
- 更新 `AGENTS.md`、`README.md`、`agent_service/README.md` 和三服务冒烟文档。

原因：

- 仅编译和 mock 测试无法确认 `RunDiagnosis -> agent-service -> log-service` 的真实 HTTP/RPC 链路。
- 真实冒烟首次启用 DeepSeek 时，ticket-diagnosis-service 5 秒超时导致 502；关闭 LLM 的基线验证成功，证明链路正常，问题收敛到模型响应时延。
- 生产诊断报告需要允许模型调用在合理时间内完成，同时保留可配置能力，避免所有环境被固定超时时间绑定。

影响范围：

- `backend/services/ticket_diagnosis_service/include/ticket_diagnosis_service/agent_client.h`
- `backend/services/ticket_diagnosis_service/src/agent_client.cc`
- `backend/services/ticket_diagnosis_service/src/main.cc`
- `samples/robot_20260730/`
- `docs/11_three_service_smoke_test.md`
- `AGENTS.md`
- `README.md`
- `agent_service/README.md`
- `CHANGES.md`

开发过程记录：

- 首次冒烟命令误在宿主机执行，因容器路径不存在立即退出，没有启动服务；随后改为容器内执行。
- DeepSeek key 只通过运行时标准输入注入容器环境，没有写入文件、命令参数、日志或提交；本记录不保存 key。
- 首次真实链路导入样例成功（4 个文件、7 条日志），但 RunDiagnosis 返回 502。
- 关闭 LLM 的独立端口基线返回 `response.message=ok`，确认 C++、Agent 和 log-service 编排正常；随后定位到 AgentClient 原有 5000ms 固定超时。
- 直接调用 Agent 时一次 shell 测试因手写 JSON 引号得到 422，改用 `json.dumps` 后 `/diagnose` 返回 200，确认 Agent 请求格式正常。
- C++ 重新编译验证通过；DeepSeek live 调用在本阶段已发起，但受原 5 秒超时影响未完成最终报告，扩大超时后需再次执行 live 冒烟。

验证结果：

- 样例日志导入成功：`file_count=4`、`log_count=7`。
- 关闭 LLM 三服务基线：`RunDiagnosis` 返回 `response.message=ok`。
- 直接 Agent deterministic `/diagnose`：HTTP 200。
- C++ `log_service` 和 `ticket_diagnosis_service` 在容器内编译成功。
- Agent-service 全量测试基线：16 个测试全部通过。
- 待扩大超时后的 DeepSeek live 冒烟完成后补充最终结果。

当前限制：

- 三服务仍使用内存 store，重启后日志和 Bug 数据会丢失。
- DeepSeek live 结果依赖账号额度、模型可用性和网络；本阶段已验证调用路径，但原超时问题修复后的最终 live 结果仍待复测。

下一步：

- 用 `ROBOTOPS_AGENT_HTTP_TIMEOUT_MS=120000` 重跑 DeepSeek 三服务冒烟，确认真实结构化报告和自动日志证据均返回。
- 后续将冒烟流程固化为 CI 或集成测试，并继续替换本地知识索引为 knowledge-service/向量检索。

是否已提交 Git：

- 待扩大超时后的 live 冒烟和全量测试完成后提交。

## 2026-07-31 阶段 5.8：源码仓库同步与源码感知诊断

修改内容：

- 扩展 `source_tool.search_source()`：源码检索前先确保 source workspace 可用。
- 本地已有 Git 仓库执行 `git pull --ff-only`；远程仓库未缓存时 clone 到 `ROBOTOPS_SOURCE_WORKSPACE_ROOT`；可按 branch/commit checkout 固定版本。
- 非 Git 本地目录继续直接复用，兼容现有 interaction 源码挂载和单元测试。
- 新增 `source_sync` 结果元数据，记录 `action`、`local_path` 和 revision；同步失败时不生成源码证据并返回可诊断错误。
- 新增源码同步测试，覆盖已有仓库 pull 和远程仓库失败降级。
- 更新 `AGENTS.md`、`README.md`、`agent_service/README.md`，明确源码仓库是 Agent 的主要分析依赖。

原因：

- Agent 的源码证据不能依赖调用方手工把代码提前放在某个目录；诊断输入包含 `source_repo` 时，应由 Agent 管理可复现的本地源码工作区。
- 已有本地仓库必须先更新，否则报告可能引用旧分支或旧提交；指定 commit 时需要固定到对应版本，避免源码证据与 Bug 软件版本不一致。
- 同步失败必须显式降级，不能用历史路径或猜测内容伪造源码证据。

影响范围：

- `agent_service/app/settings.py`
- `agent_service/app/tools/source_tool.py`
- `agent_service/app/workflow/nodes.py`
- `agent_service/tests/test_source_sync.py`
- `AGENTS.md`
- `README.md`
- `agent_service/README.md`
- `CHANGES.md`

开发过程记录：

- 三服务 live 冒烟在扩大 C++ 超时后已返回成功任务，但首次报告无日志证据；随后隔离验证确认 Agent + log-service 直接调用可返回 2 条日志，源码同步因此作为下一条核心能力推进。
- C++ 关闭 LLM 基线和显式 endpoint 均返回 `ok`，但当前报告证据为空，后续需继续检查 C++ 到 Agent 的请求上下文记录；本阶段不伪造“已完成全链路证据”。
- 源码同步命令使用参数数组调用 `git`，不拼接 shell 命令，避免仓库 URL、branch 或 commit 注入 shell。
- API key 仍只通过运行时标准输入使用，不写入源码同步逻辑、测试、文档或提交。

验证结果：

- 首次全量测试为 20 个测试、1 个失败；失败是源码同步测试对 mock 参数位置的断言错误，已修正测试断言。
- 修正后容器内 Agent 全量测试为 20 个测试全部通过。
- C++ `ticket_diagnosis_service` 在容器内编译成功。
- `py_compile` 和 `git diff --check` 通过。

当前限制：

- 尚未对私有仓库认证做实现；SSH key、HTTPS token 等凭据必须由运行环境提供，不能由 Agent 保存。
- `pull --ff-only` 遇到本地未提交改动会失败并降级，避免自动覆盖开发者源码。
- `source_search` 仍是文本检索和启发式函数名推断，尚未接 source-index-service、clangd 或 tree-sitter。

下一步：

- 完成 C++ AgentClient 请求上下文可观测性，确保 `source_repo`、`log_package_id` 和 endpoint 在服务间可追踪。
- 增加 C++ AgentClient 脱敏请求审计日志，记录 endpoint、Bug、日志包是否存在、模块和手工证据数量，不记录完整请求或凭据。
- 修复 `log_context` 过滤问题：存在唯一 `package_id` 时不再同时传递可能由 ticket store 新生成的 `bug_id`，避免导入日志和诊断 Bug ID 不一致导致上下文为空。
- 使用真实 interaction Git 仓库验证 clone/pull/commit 与源码证据版本一致。

是否已提交 Git：

- 待源码同步测试和全量验证通过后提交。

## 2026-07-31 阶段 5.9：平台源码仓库注册表

修改内容：

- 新增 `agent_service/app/source_registry.py`，以 JSON 文件持久化模块源码仓库配置。
- 新增 `GET /source-repositories` 和 `PUT /source-repositories/{module_name}` 管理接口，支持配置 `repo_url`、默认 `branch`、可选 `commit` 和 `local_path`。
- `source_search` 优先按 `main_module` 从平台注册表读取仓库，不再要求测试人员在每个 Bug 中填写源码地址；旧 `source_repo` 字段保留为兼容兜底。
- 新增 `ROBOTOPS_SOURCE_REPOSITORY_FILE` 配置和注册表持久化测试。
- 更新 `AGENTS.md`、`README.md`、`agent_service/README.md` 和三服务冒烟文档，明确测试人员输入边界。

原因：

- 测试人员只负责提供 Bug 现象、发生时间和日志包，不应承担维护 interaction、mc、agent、hds 等源码仓库地址的职责。
- 源码仓库属于平台基础配置，应首次由管理员录入，后续由 Agent 根据问题模块自动 clone/pull；只有仓库管理员需要时才通过管理接口修改。
- 按模块维护仓库可以避免 Bug 请求携带错误仓库，也便于后续统一管理分支、版本和访问凭据。

影响范围：

- `agent_service/app/source_registry.py`
- `agent_service/app/models.py`
- `agent_service/app/settings.py`
- `agent_service/app/main.py`
- `agent_service/app/tools/source_tool.py`
- `agent_service/app/workflow/nodes.py`
- `agent_service/tests/test_source_registry.py`
- `agent_service/tests/test_source_sync.py`
- `AGENTS.md`
- `README.md`
- `agent_service/README.md`
- `docs/11_three_service_smoke_test.md`
- `CHANGES.md`

开发过程记录：

- 根据用户澄清，将“测试人员填写 source_repo”调整为“平台管理员维护模块仓库注册表”。
- planner 已改为传递 `module_name`，source tool 按模块读取 registry；`BugContext.source_repo` 只保留兼容旧请求，不再作为主流程设计。
- 注册表写入采用临时文件替换，避免进程中断留下半截 JSON；仓库凭据不由接口或 Agent 保存。
- 源码同步仍使用 subprocess 参数数组执行 git，不拼接 shell 命令。

验证结果：

- 容器内 Agent 全量测试通过：21 个测试全部 `OK`，包含注册表管理函数、模块配置持久化和源码 pull/clone 降级测试。
- C++ `ticket_diagnosis_service` 在容器内编译成功。
- `py_compile` 和 `git diff --check` 通过。

当前限制：

- 当前管理接口没有接入登录鉴权，只适合内部 MVP 环境；生产环境必须放在管理权限和 HTTPS 之后。
- JSON 注册表是单实例本地配置，多实例部署时需要迁移到配置中心或 source-repository-service。
- 私有 Git 仓库认证仍依赖运行环境已有 SSH/HTTPS 凭据，不由平台接口传入。

下一步：

- 增加注册表接口鉴权和模块配置校验。
- 使用真实 interaction、mc、agent 仓库验证 clone/pull/branch/commit 后的源码证据版本。

是否已提交 Git：

- 待本阶段全量验证通过后提交。

## 2026-07-31 阶段 6.0：诊断日志包关联修复

修改内容：

- 修改 `agent_service/app/tools/log_tool.py`：当请求带有 `log_package_id` 时，将 `bug_id` 置空，只使用 package_id 查询日志上下文。
- 新增工具测试，验证 package_id 存在时请求 payload 不携带 bug_id。
- 增加 C++ `AgentClient` 脱敏请求审计日志，记录 endpoint、bug_id、日志包是否存在、模块和手工证据数量，不记录完整 payload。
- 更新阶段文档，明确日志包是跨服务稳定关联键。

原因：

- 真实三服务冒烟发现，日志导入使用的 bug_id 可能来自外部系统，而 `ticket-diagnosis-service` 内存 store 创建 Bug 时会生成新的 bug_id。
- `log-service` 原先同时按 bug_id 和 package_id 过滤，两个 ID 不一致时返回空日志，导致 Agent 输出低置信度报告。
- package_id 在日志包和 Bug 单之间是稳定关联键，有 package_id 时不应再附带可能过期的 bug_id。

影响范围：

- `agent_service/app/tools/log_tool.py`
- `agent_service/tests/test_tools.py`
- `backend/services/ticket_diagnosis_service/src/agent_client.cc`
- `AGENTS.md`
- `README.md`
- `agent_service/README.md`
- `CHANGES.md`

开发过程记录：

- 临时回显 Agent 测试脚本两次因 Python 单行 handler 语法错误未启动，未产生项目代码影响；随后通过脱敏 C++ 审计日志确认 C++ 已正确识别 `log_package_id`。
- 审计验证显示 C++ 请求包含日志包，进一步用不同导入 bug_id 和诊断 bug_id 重现空证据问题，定位到 log-service 双字段过滤。
- 修复后真实三服务验证成功：日志导入 4 个文件、7 条日志，RunDiagnosis 返回 `response.message=ok`、`interaction`、4 条日志证据和置信度 0.85。
- API key 未参与本次修复测试，不写入代码、日志或提交。

验证结果：

- 容器内 Agent 全量测试：21 个全部通过。
- `py_compile` 和 `git diff --check`：通过。
- C++ `ticket_diagnosis_service` 构建：通过。
- 真实 C++ -> agent-service -> log-service 链路：日志证据 4 条，`suspected_module=interaction`，置信度 0.85。

当前限制：

- 三服务仍使用内存 store；生产环境需要数据库中的 Bug、日志包和日志索引统一关联。
- DeepSeek live 报告还需要在 package 关联修复后重新验证，之前 live 请求虽然任务成功，但因 package 过滤问题报告没有日志证据。

下一步：

- 在 package 关联修复基础上重新执行 DeepSeek live 三服务冒烟，确认结构化报告保留 4 条日志证据。
- 完善 C++ 请求和 Agent workflow trace 的统一诊断任务追踪。

是否已提交 Git：

- 待本阶段提交。

## 2026-07-31 阶段 5.5：知识库检索工具接入

修改内容：

- 新增 `agent_service/app/tools/knowledge_tool.py`，支持读取本地 `.json` / `.jsonl` SOP、错误码和模块知识条目。
- 知识检索按 Bug 标题、描述、主模块和日志关键词匹配，返回排序后的 `knowledge_items`，并保留 `source` / `source_id` 来源标识。
- 将 `knowledge_search` 接入 LangGraph planner 和 tool executor；默认工具预算从 3 次提升到 4 次，允许完成“日志 -> 源码 -> 历史案例 -> 知识库”的取证顺序。
- 修复空结果重复调用问题：planner 通过 `observations` 判断 `case_search` / `knowledge_search` 是否已经尝试过，每类工具最多调用一次。
- deterministic fallback 将知识条目标记为“知识库参考（source）”后加入排查建议；LLM 场景继续通过请求上下文读取完整知识条目。
- 新增知识工具和工作流测试，覆盖 JSONL、来源保留、空目录降级及端到端参考建议。

原因：

- 历史案例解决“以前遇到过什么”，知识库还需要承载 SOP、错误码和模块边界，二者不能混为一个案例索引。
- `knowledge_search` 原先为空 stub，Agent 无法复用团队排障规范；本阶段先提供无外部数据库依赖的可替换检索接口，为后续 knowledge-service / 向量数据库接入保留边界。
- 同时修复空索引反复规划同一工具的路由缺陷，避免无效消耗工具预算。

影响范围：

- `agent_service/app/tools/knowledge_tool.py`
- `agent_service/app/tools/__init__.py`
- `agent_service/app/settings.py`
- `agent_service/app/workflow/state.py`
- `agent_service/app/workflow/nodes.py`
- `agent_service/tests/test_knowledge_tool.py`
- `agent_service/tests/test_workflow.py`
- `AGENTS.md`
- `README.md`
- `agent_service/README.md`
- `CHANGES.md`

开发过程记录：

- 开发前重新核对了项目协作说明、Agent 服务文档、Agent 重点规划和 LangGraph 状态设计，确认本阶段仍限定在 Python agent-service。
- 检查历史案例工作流时发现：案例索引为空时，planner 仅根据 `history_cases` 判断，会重复请求 `case_search`；已用工具观察记录修复，并增加工作流覆盖。
- 知识文件损坏、编码异常或目录不存在时跳过并返回空结果，不阻断报告生成。
- API key 未写入代码、文档、测试或命令行；本阶段所有测试均为本地索引测试，不调用 DeepSeek 网络接口。

验证结果：

- 已完成 `py_compile` 和 `git diff --check` 静态检查。
- 首次全量测试为 16 个测试、1 个失败；失败暴露源码工具成功后观察节点直接进入报告、未继续案例/知识检索的问题。
- 修正观察节点的“是否还有未尝试取证阶段”判断后，容器内全量测试为 16 个测试全部通过。

当前限制：

- 当前检索是本地文本匹配，不是向量 RAG；尚未接入 embedding、Milvus/Chroma 或 knowledge-service。
- 知识条目当前以参考建议形式进入 deterministic fallback，报告 schema 尚未增加独立知识证据字段。

下一步：

- 设计 knowledge-service / 向量检索适配层，统一返回来源、版本和片段位置。
- 让 `ticket-diagnosis-service.RunDiagnosis` 携带 `log_package_id`，完成 C++ 编排到 Agent 自动取证的联调。

是否已提交 Git：

- 待本阶段全量测试通过后提交。

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

## 2026-07-30 阶段 4 补充：LangGraph / LangChain / ReAct Agent 调研

修改内容：

- 新增 `docs/09_langgraph_langchain_agent_research.md`。
- 调研 LangGraph、LangChain Agents、ReAct、Open Canvas、Open Agent Platform、Social Media Agent、LangGraph Supervisor、Agent Protocol 等资料。
- 记录 RobotOps AI 后续 Agent 架构建议：
  - LangGraph 用于诊断流程编排。
  - LangChain 用于工具封装。
  - ReAct 用于 `reason -> tool action -> observation -> next step` 的诊断取证循环。
  - 不过早做复杂多 Agent supervisor。
  - 不把全部业务逻辑塞进一个大 prompt。
- 更新 `README.md` 文档索引。

原因：

- 用户明确要求先学习网上开源优秀 LangGraph / LangChain Agent 项目，再重点开发 RobotOps AI 的 Agent 部分。
- 用户补充要求学习 ReAct 思想。
- RobotOps AI 的核心是复现 interaction Bug 排障过程，必须让 Agent 具备可审计的取证和推理流程。

影响范围：

- `docs/09_langgraph_langchain_agent_research.md`
- `README.md`
- `CHANGES.md`

下一步：

- 按调研结论开发 `agent-service` 的 LangGraph workflow skeleton。
- 新增 `DiagnosisState`、`log_tool`、`diagnosis_planner_node`、`tool_executor_node`、`observation_analyzer_node`。
- `/diagnose` 保持现有接口不变，但内部逐步切换到 LangGraph 工作流。

是否已提交 Git：

- 是。已纳入本次阶段提交。

## 2026-07-31 阶段 5：LangGraph Agent 工作流设计

修改内容：

- 新增 `docs/10_langgraph_workflow_design.md`。
- 详细设计 `agent-service` 后续 LangGraph 工作流：
  - `DiagnosisState` 字段、更新方式和读写节点。
  - `normalize_input_node`、`rule_evidence_node`、`planner_node`、`tool_executor_node`、`observation_analyzer_node`、`llm_report_node`、`fallback_report_node`、`confidence_check_node`、`finalize_node`。
  - `planner -> tool action -> observation -> report` 的受控 ReAct 图结构。
  - `log_context`、`source_search`、`case_search`、`knowledge_search` 工具接口边界。
  - DeepSeek / LangChain 接入方式和无 API key fallback 策略。
  - 置信度上限、测试计划和分阶段验收标准。
- 更新 `AGENTS.md` 和 `README.md` 当前阶段说明，明确当前先设计 LangGraph 状态和图结构，再进行后续代码开发。

原因：

- 用户明确要求不要直接瞎写 LangGraph / LangChain 代码，必须先学习优秀实践并设计状态和图结构。
- `agent-service` 是项目后续重点，必须先把诊断过程拆成可观测、可测试、可降级的工作流。
- RobotOps AI 需要复现真实 interaction Bug 排障过程，不能把日志、源码、历史案例和报告生成塞进一个大 prompt。

影响范围：

- `docs/10_langgraph_workflow_design.md`
- `AGENTS.md`
- `README.md`
- `CHANGES.md`

下一步：

- 按设计实现 `agent_service/app/workflow/state.py`、`graph.py`、`nodes.py`、`routing.py` 和 `confidence.py`。
- 保持 `/diagnose` 外部接口不变，内部切换到 LangGraph workflow。
- 先保证没有 `DEEPSEEK_API_KEY` 时仍可通过现有规则诊断测试，再接入 `ChatDeepSeek` 报告节点。

是否已提交 Git：

- 是。已纳入本次阶段提交。

## 2026-07-31 阶段 5.1：LangGraph Agent 工作流骨架

修改内容：

- 更新 `agent_service/requirements.txt`，新增 `langgraph`、`langchain-deepseek` 和 `typing-extensions`。
- 新增 `agent_service/app/settings.py`，集中读取 DeepSeek 和 Agent workflow 配置。
- 新增 `agent_service/app/workflow/`：
  - `state.py` 定义 `DiagnosisState`、`DiagnosisPlan`、`ToolRequest`、`ToolObservation`、`Hypothesis` 和 `GraphTraceEvent`。
  - `graph.py` 实现 `build_diagnosis_graph()` 和 `run_diagnosis_workflow()`。
  - `nodes.py` 实现 normalize、rule evidence、planner、tool executor、observation analyzer、choose report、LLM report、fallback report、confidence check 和 finalize 节点。
  - `routing.py` 实现 LangGraph conditional edge 路由函数。
  - `confidence.py` 实现证据强度驱动的置信度校准。
- 新增 `agent_service/app/llm/deepseek.py`，预留 `ChatDeepSeek` 结构化报告生成入口。
- 修改 `agent_service/app/main.py`，保持 `/diagnose` 外部接口不变，内部切换为 LangGraph workflow。
- 新增 `agent_service/tests/test_workflow.py`，覆盖无 DeepSeek API key 时的规则 fallback 和低置信度场景。
- 更新 `agent_service/README.md`、`AGENTS.md` 和 `README.md` 阶段说明。

原因：

- 用户要求先设计 LangGraph 状态和图结构，再进入后续开发。
- Agent 是 RobotOps AI 后续重点，需要把诊断过程从单个规则函数演进为可观测、可测试、可扩展的工作流。
- 第一版工作流必须在没有 LLM API key 时仍可运行，避免本地测试和 C++ 编排链路依赖外部模型。

影响范围：

- `agent_service/requirements.txt`
- `agent_service/app/main.py`
- `agent_service/app/settings.py`
- `agent_service/app/workflow/`
- `agent_service/app/llm/`
- `agent_service/tests/test_workflow.py`
- `agent_service/README.md`
- `AGENTS.md`
- `README.md`
- `CHANGES.md`

验证结果：

- 已在 `dev-env-service` 容器中安装更新后的 Python 依赖：

```text
python3 -m pip install --default-timeout 180 -i https://pypi.tuna.tsinghua.edu.cn/simple -r agent_service/requirements.txt
```

- 已在 `dev-env-service` 容器中执行：

```text
python3 -m unittest discover -s agent_service/tests
```

- 结果：4 个测试全部通过。

下一步：

- 接入真实 `log_context` 工具，调用 `log-service.GetLogContext` 获取发生时间窗口日志。
- 接入真实 `source_search` 工具，优先检索本地 `../interaction` 源码。
- 完善 DeepSeek LLM 报告节点，在有 `DEEPSEEK_API_KEY` 时生成并校验结构化报告。

是否已提交 Git：

- 是。已纳入本次阶段提交。

## 2026-07-31 阶段 5.2：Agent 工具取证循环初版

修改内容：

- 新增 `agent_service/app/tools/` 工具模块。
- 新增 `log_tool.fetch_log_context()`，通过 HTTP JSON 调用 `log-service.GetLogContext`，并归一化为 Agent 的 `LogEvidence` 字段。
- 新增 `source_tool.search_source()`，支持按关键日志语句检索本地 interaction 源码，返回 `SourceEvidence`，包含文件路径、函数名、匹配文本和上下文片段。
- `source_search` 优先使用 `rg`，当容器或环境缺少 `rg` 时，自动降级为 Python 标准库递归文本搜索。
- 扩展 `agent_service/app/settings.py`，新增：
  - `ROBOTOPS_LOG_SERVICE_URL`
  - `ROBOTOPS_SOURCE_SEARCH_ROOTS`
  - `ROBOTOPS_AGENT_TOOL_TIMEOUT_SECONDS`
  - `ROBOTOPS_AGENT_MAX_TOOL_ITERATIONS`
- 修改 `workflow.nodes._execute_tool()`，将 `log_context` 和 `source_search` 从 stub 接入真实工具。
- 修正工具取证后的报告生成逻辑：`fallback_report_node` 和 `llm_report_node` 会基于当前 state 中新增的日志和源码证据重新运行规则 baseline，避免工具取证成功后仍输出取证前的低置信度报告。
- 新增 `agent_service/tests/test_tools.py`，覆盖 log-service HTTP JSON 响应归一化和源码检索片段。
- 扩展 `agent_service/tests/test_workflow.py`，覆盖无入参日志但有 `log_package_id` 时，workflow 通过 `log_context -> source_search` 工具取证后命中 interaction 规则报告。
- 更新 `README.md`、`agent_service/README.md` 和 `AGENTS.md` 当前阶段说明。

原因：

- 阶段 5.1 已完成 LangGraph workflow skeleton，但工具执行仍是空结果，不能真正复现 `planner -> tool action -> observation -> report` 的 ReAct 取证流程。
- 当前 RobotOps AI 的重点是 Agent 诊断能力，下一步必须让 Agent 主动获取发生时间窗口日志和 interaction 源码证据，而不是继续依赖调用方手工传入全部证据。
- 真实研发排障要求报告必须基于日志和源码证据，工具取证后的证据必须进入最终规则 baseline 和置信度校准。

影响范围：

- `agent_service/app/settings.py`
- `agent_service/app/tools/`
- `agent_service/app/workflow/nodes.py`
- `agent_service/tests/test_tools.py`
- `agent_service/tests/test_workflow.py`
- `README.md`
- `agent_service/README.md`
- `AGENTS.md`
- `CHANGES.md`

开发过程记录：

- 首次在宿主机执行 `python3 -m unittest discover -s agent_service/tests` 失败，原因是宿主机 Python 环境缺少 `pydantic`，不作为项目代码失败处理。
- 按项目规范切换到 `dev-env-service` 容器验证；文档示例路径 `/home/dev/workspace/projects/RobotOps-AI` 不存在，实际路径为 `/home/dev/workspace/RobotOps-AI`。
- 容器内首次完整测试发现 `source_search` 测试没有结果，确认原因是容器未安装 `rg`。
- 为保证工具环境鲁棒性，保留 `rg` 优先策略，同时补充标准库递归文本搜索兜底。
- 源码函数名推断初版曾把 `LOG(...)` 宏误判为函数名，已改为优先识别 C++ `Class::Function`，普通函数签名必须包含定义体 `{`。

验证结果：

- 宿主机已执行：

```text
python3 -m unittest agent_service.tests.test_tools
```

- 结果：2 个工具测试通过。
- 已在 `dev-env-service` 容器中执行：

```text
cd /home/dev/workspace/RobotOps-AI
python3 -m unittest discover -s agent_service/tests
```

- 结果：7 个测试全部通过。

当前限制：

- `log_context` 依赖 `log-service` 已导入对应 `log_package_id` 的日志；服务不可用或未导入时会记录工具失败并降级。
- `source_search` 当前是文本检索和启发式函数名推断，尚未接 tree-sitter、clangd index 或 source-index-service。
- `case_search` 和 `knowledge_search` 仍为空实现。
- DeepSeek 结构化报告节点仍是预留入口，尚未完成有 API key 场景的端到端验证。

下一步：

- 完善 DeepSeek LLM 报告节点，支持有 `DEEPSEEK_API_KEY` 时生成并校验结构化报告，失败自动 fallback。
- 接入真实历史案例和知识库/RAG 工具。
- 后续让 `ticket-diagnosis-service.RunDiagnosis` 传入 `log_package_id`，使 Agent 能自动从 `log-service` 拉取上下文。

是否已提交 Git：

- 是。已纳入本次阶段提交。

## 2026-07-31 阶段 5.3：DeepSeek 结构化报告节点加固

修改内容：

- 加固 `agent_service/app/llm/deepseek.py`：
  - 继续使用 `langchain-deepseek` 的 `ChatDeepSeek.with_structured_output(DiagnosisReport)`。
  - 将 LLM 初始化、调用和结构化校验中的异常统一包装为 `DeepSeekUnavailable`。
  - 压缩传入 prompt 的日志、源码、历史案例和知识库条目，避免无边界传入超长上下文。
  - 在 prompt 中明确证据边界、禁止编造日志/源码/责任模块、证据不足时降低置信度。
- 加固 `workflow.nodes.llm_report_node()`：
  - LLM 报告生成前基于当前 state 证据重新运行规则 baseline。
  - LLM 报告生成成功后合并规则报告中的日志证据、源码证据和人工确认问题，避免 LLM 漏掉可追溯证据。
  - LLM 调用失败时记录 `errors`，走 `fallback_report_node`，再由 `confidence_check_node` 将置信度压到安全上限。
- 新增 `agent_service/tests/test_deepseek.py`，用 fake `langchain_deepseek.ChatDeepSeek` 覆盖结构化输出路径，不依赖真实网络和 API key。
- 扩展 `agent_service/tests/test_workflow.py`：
  - 覆盖有 `DEEPSEEK_API_KEY` 且 LLM 成功时，workflow 保留规则日志和源码证据。
  - 覆盖 LLM 失败时自动 fallback，报告仍合法且置信度不超过 0.75。
- 更新 `README.md`、`agent_service/README.md` 和 `AGENTS.md` 当前阶段说明。

原因：

- 阶段 5.1 已预留 DeepSeek 节点，但只有最小调用路径，缺少失败降级和证据一致性测试。
- RobotOps AI 的 Agent 报告必须可追溯，不能让 LLM 覆盖或丢弃规则命中的日志与源码证据。
- 用户提供了 DeepSeek API key，但该 key 不应写入仓库、文档、测试或命令行；本阶段先用 mock 完成可重复验证的结构化报告路径。

影响范围：

- `agent_service/app/llm/deepseek.py`
- `agent_service/app/workflow/nodes.py`
- `agent_service/tests/test_deepseek.py`
- `agent_service/tests/test_workflow.py`
- `README.md`
- `agent_service/README.md`
- `AGENTS.md`
- `CHANGES.md`

开发过程记录：

- 用户在对话中提供 DeepSeek API key；本阶段未将 key 写入任何文件、提交、测试或命令行。
- 已通过 DeepSeek 官方文档核对当前模型名，`deepseek-v4-flash` 和 `deepseek-v4-pro` 是当前可用模型，`deepseek-chat` 和 `deepseek-reasoner` 已标注废弃。
- 宿主机执行 `python3 -m unittest agent_service.tests.test_deepseek agent_service.tests.test_tools` 仍因缺少 `pydantic` 失败；该问题属于宿主机 Python 环境不完整，项目准验收以 `dev-env-service` 容器为准。
- 容器内完整测试通过，证明新增 LLM mock 路径、fallback 路径和现有规则/工具路径没有回归。

验证结果：

- 已在 `dev-env-service` 容器中执行：

```text
cd /home/dev/workspace/RobotOps-AI
python3 -m unittest discover -s agent_service/tests
```

- 结果：10 个测试全部通过。

当前限制：

- 本阶段没有使用真实 DeepSeek API key 发起 live 网络调用，避免 key 泄露到命令行和测试日志。
- `ChatDeepSeek` 真实联网调用仍需在安全注入 `DEEPSEEK_API_KEY` 的运行环境中手动或通过安全 CI secret 验证。
- `case_search` 和 `knowledge_search` 仍为空实现。

下一步：

- 接入历史案例检索工具，优先沉淀 interaction 触摸、self check、WorkerManager、ActionSkill、MoveSkill 等真实案例。
- 接入知识库/RAG 工具，但继续保证 RAG 只作为工具，不替代 Agent 工作流和证据校验。
- 让 `ticket-diagnosis-service.RunDiagnosis` 携带 `log_package_id`，触发 Agent 自动取证。

是否已提交 Git：

- 是。已纳入本次阶段提交。

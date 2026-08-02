# RobotOps AI

RobotOps AI 是一个面向机器人研发测试和部署运维场景的智能运维与诊断平台。

它不是传统的设备管理后台，也不是单纯的日志搜索工具。项目目标是把机器人研发和部署运维中最常见的排障流程平台化：

```text
Bug / 工单 / 告警
  ↓
日志包 / 实时状态 / 模块事件
  ↓
interaction / mc / agent / hal / sm / hds 多模块关联分析
  ↓
源码仓库 / 历史案例 / 知识库检索
  ↓
AI Agent 生成带证据的诊断报告
```

项目当前目录名暂定为 `RobotBugOps`，正式产品名为 **RobotOps AI**。

## 为什么需要它

机器人系统不是一个单体程序，而是由多个模块共同组成：

```text
上层：Agent / App / 语音 / 业务指令
中间层：interaction 交互编排模块
底层：mc / hal_camera / hal_audio / hal_touch / bms / sm / hds
```

在研发测试阶段，测试人员通常会在飞书提交 Bug，并上传完整日志包。组长把 Bug 分配给开发工程师后，工程师需要根据问题描述、发生时间、机器人类型和日志内容定位原因。

真实排障往往不是“看到 ERROR 就知道原因”，而是要回答：

- Agent 有没有发出指令？
- interaction 有没有收到触摸、语音或动作请求？
- self check 是否通过？
- 当前 action 是否支持该动作？
- T 型和 Q 型机器人的规则是否不同？
- bms 是否处于低电量或充电状态？
- hds 是否存在高等级故障？
- WorkerManager 是否创建任务成功？
- Skill 调用 mc/hal 是否失败？
- 对应日志在源码里是哪一段逻辑打出来的？

这些工作如果完全靠人工查日志、grep 源码和回忆历史 Bug，效率会很低。RobotOps AI 的价值就是把这些动作串成一个可复用的诊断闭环。

## 两阶段定位

### 研发测试阶段

第一阶段面向研发测试流程：

```text
测试提交 Bug
  ↓
上传 robot_日期.zip 完整日志包
  ↓
平台解析 interaction / mc / agent / hal / sm / hds 日志
  ↓
按发生时间提取日志上下文
  ↓
Agent 根据日志关键句检索源码
  ↓
结合历史案例和知识库生成诊断报告
```

核心输出：

- 相关日志证据
- 相关源码位置
- 疑似责任模块
- 可能原因
- 修复或排查建议
- 可沉淀的历史案例

### 部署运维阶段

机器人交付并部署到客户现场后，平台扩展为远程运维系统：

```text
机器人侧 collector / gateway
  ↓
上报模块心跳、实时状态、事件、关键日志
  ↓
平台监控机器人和模块健康状态
  ↓
产生告警或现场工单
  ↓
Agent 结合近期日志、实时状态和历史案例给出远程诊断建议
```

核心输出：

- 机器人在线状态
- 模块健康状态
- 告警事件
- 现场工单
- 远程诊断报告
- 维修和处理记录

## 核心能力地图

```text
RobotOps AI
  ├── Bug / 工单管理
  │   ├── 研发 Bug
  │   └── 现场工单
  ├── 日志包管理
  │   ├── robot_日期.zip 上传
  │   ├── 多模块目录识别
  │   └── 日志解析与索引
  ├── 多模块日志检索
  │   ├── interaction.log
  │   ├── mc.log
  │   ├── agent.log
  │   ├── hal_*.log
  │   ├── sm.log
  │   └── hds.log
  ├── 机器人实时运维
  │   ├── 机器人资产
  │   ├── 模块心跳
  │   ├── 实时状态
  │   └── 事件告警
  ├── 源码感知诊断
  │   ├── 日志关键句定位
  │   ├── 源码文件检索
  │   ├── 函数和调用链分析
  │   └── T/Q 机型差异分析
  ├── AI Agent 诊断
  │   ├── 日志证据提取
  │   ├── 源码证据提取
  │   ├── 历史案例检索
  │   └── 结构化诊断报告
  └── 知识库
      ├── 历史 Bug 案例
      ├── 模块设计文档
      ├── 错误码说明
      └── 排障 SOP
```

## 典型诊断场景

### 场景：触摸后机器人没有反应

输入：

```text
机器人类型：T 型
问题模块：interaction
问题描述：机器人坐下后拍触摸板，没有站起
发生时间：2026-07-30 15:32:10
日志包：robot_20260730.zip
源码仓库：interaction / mc
```

系统处理：

```text
1. 解压日志包
2. 识别 interaction.log、mc.log、hds.log、bms 日志
3. 抽取发生时间前后 5 分钟日志
4. 检索 touch event、self check、action、battery、hds 等关键字段
5. 根据日志关键句搜索 interaction 源码
6. 定位 checker / task factory / worker / skill 调用链
7. 生成诊断报告
```

输出：

```text
疑似原因：
  触摸事件已到达 interaction，但被 T 型机器人当前 action 前置检查拦截。

日志证据：
  Current action is DAMPING_DEFAULT or PASSIVE_DEFAULT, ignore touch trigger

源码证据：
  interaction/src/scheduler/checker/t1_checker.cpp
  CheckTouch() 中在特定 action 下 return false

建议：
  确认产品预期是否允许坐下状态下触摸触发站起。
  如允许，需要调整 T1 CheckTouch 白名单或增加特殊站起逻辑。
```

## 技术栈

本项目继续参考现有 DeviceOps/dev 环境和 `cpp-microservice-kit` 脚手架，不切换到 Java。

```text
C++ 微服务：
  brpc / protobuf / CMake / cpp-microservice-kit

Python AI 服务：
  FastAPI / LangGraph / LangChain / RAG

Web 前端：
  React 或 Vue
  企业运维平台风格

数据层：
  MySQL          Bug、工单、日志包、诊断报告
  Elasticsearch 多模块日志检索
  Redis         实时状态、任务状态
  RabbitMQ      异步日志、事件、诊断任务
  Milvus/Chroma 源码片段、知识库、历史案例向量检索
```

## 服务规划

第一版不盲目拆太多服务，但接口按微服务边界设计。

MVP 服务：

```text
robot-gateway
log-service
ticket-diagnosis-service
agent-service
web-console
```

后续拆分：

```text
robot-service
module-service
event-service
ticket-service
diagnosis-service
knowledge-service
source-index-service
```

## Web 工作台

主前端采用 Web 管理台，不再使用 Qt 作为平台主前端。

页面规划：

- 总览仪表盘
- Bug / 工单列表
- Bug 详情
- 日志包上传
- 多模块日志检索
- 时间线分析
- AI 诊断报告
- 源码证据视图
- 机器人资产
- 模块实时状态
- 告警事件
- 知识库 / 历史案例

Web 视觉和产品组织方式参考 `qinshihu/itops-agent-platform` 这类运维 Agent 平台：重点是清晰呈现“输入、分析、执行、证据、结论”的闭环，而不是做一个普通表格后台。

当前已提供 `frontend/` Web 工作台 MVP，使用 React + TypeScript + Vite + Lucide。开发服务器默认监听 `4173`，`/api` 请求通过 Vite 代理到本地 `ticket-diagnosis-service`。完整联调环境一键启动：

```bash
./scripts/run_dev_stack.sh
```

脚本启动并连通以下端口：

```text
9001  log-service
9002  ticket-diagnosis-service
9003  agent-service
4173  web-console
```

如需启用 DeepSeek，先在当前终端通过安全方式设置 `DEEPSEEK_API_KEY`，再执行脚本。未设置时 Agent 使用 deterministic fallback。只启动前端的方式：

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

## 开发状态

当前已进入后端开发阶段。

已有文档：

```text
docs/01_product_definition.md
docs/02_architecture.md
docs/03_data_model.md
docs/04_mvp_plan.md
docs/05_web_frontend_design.md
docs/06_development_guide.md
docs/07_backend_linux_handoff.md
docs/08_agent_service_focus.md
docs/09_langgraph_langchain_agent_research.md
```

后续开发必须先阅读：

```text
AGENTS.md
README.md
docs/
```

每完成一个阶段，必须更新：

```text
CHANGES.md
```

并提交 Git。

## 当前状态

当前处于：

```text
阶段 7.5：Agent 模型驱动的迭代源码分析
```

已完成：

- `log-service` 初版：导入已解压日志目录、查询日志、提取上下文、列出日志文件。
- `ticket-diagnosis-service` 初版：创建 Bug 单、创建诊断任务、保存和查询诊断报告。
- `agent-service` 初版：FastAPI `/health` 和 `/diagnose`，基于 interaction 规则模板生成结构化诊断报告。
- `ticket-diagnosis-service` 已支持 `RunDiagnosis`，可同步调用 `agent-service` 并保存诊断报告。
- 已实际使用 LangGraph 编排 `normalize -> rule -> planner -> tool_executor -> observation -> source_analysis -> report -> confidence -> finalize` 工作流。
- 已实际使用 LangChain `StructuredTool` 和 Pydantic schema 包装日志、源码、案例、知识检索工具；DeepSeek 使用 `ChatDeepSeek.with_structured_output(DiagnosisReport, method="json_mode")`。
- `agent-service` 已接入 `log_context` 和通用 `source_search` 工具，可主动拉取多模块日志，并按模块检索平台注册的源码仓库。
- 源码查询由本次 Bug 和日志动态生成，不使用固定函数或文件路径；命中后向 DeepSeek 提供函数级或扩展文件上下文。
- `source_analysis` 会让 DeepSeek 从本轮真实源码中规划后续查询；候选必须通过模块白名单、源码原文、证据引用和重复查询校验，模型不可用时通用提取被调符号继续分析。
- 迭代源码分析在没有新证据、模型确认可停止或达到独立轮次上限时结束，不会无限调用工具。
- `agent-service` 已加固 DeepSeek 结构化报告节点：LLM 成功时保留规则证据，LLM 失败时自动 fallback 并压低置信度。
- C++ `DiagnosisReport` 已透传 `execution_chain`、`module_relations`、`agent_version`、`generation_mode` 和 `generation_detail`，Web 工作台直接展示真实 Agent 结果。

当前限制：

- 后端服务当前使用内存存储，尚未接入 MySQL / Elasticsearch / Redis / RabbitMQ。
- 日志包当前只支持已解压目录，尚未直接解析 `.zip` / `.tar.gz`。
- `RunDiagnosis` 当前仍以调用方传入证据为主，但 Agent 已具备基于 `log_package_id` 主动拉取日志上下文的工具入口。
- `case_search` 已支持本地 JSON/JSONL 案例索引，按 Bug 描述、机器人类型、主模块和日志关键词排序；没有案例目录时安全返回空结果。
- Web 工作台已完成总览、Bug 分析、日志时间线和模块状态四个核心视图，通过 `CreateBugTicket -> RunDiagnosis` 调用完整后端链路。
- `knowledge_search` 已支持本地 JSON/JSONL 知识索引，按 Bug 描述、主模块和日志关键词排序，并保留 `source` 来源标识。
- DeepSeek 真实 API key 场景已完成 live 网络调用验证；API key 仅注入运行进程，不写入仓库。

后续开发重心：

- 优先增强 `agent-service`，而不是继续堆叠 C++ 后端服务。
- Agent 侧重点建设日志证据提取、主模块及关联模块源码上下文检索、历史案例、知识库/RAG、LangGraph 诊断工作流和结构化报告生成；interaction 是第一批重点知识，不是固化的唯一分析模块。
- `RunDiagnosisRequest` 已增加显式 `log_package_id`，C++ AgentClient 按“请求值优先、BugTicket 值兜底”传给 agent-service；Agent 可据此自动从 log-service 获取时间窗口日志。
- C++ AgentClient 的 HTTP 超时通过 `ROBOTOPS_AGENT_HTTP_TIMEOUT_MS` 配置，默认 300 秒，覆盖多轮源码规划和 DeepSeek 结构化报告的响应时间。
- 下一阶段优先建设源码符号、文件摘要和调用关系索引，提升大仓库检索的准确性与效率。
- 源码仓库由平台管理员按模块配置，不由测试人员每次提交；支持 `interaction`、`mc`、`agent`、`hds` 等模块，管理接口为 `GET/PUT /source-repositories/{module_name}`。
- 已验证真实 DeepSeek 诊断链路：日志包按 `log_package_id` 关联，成功返回 interaction 规则结论和日志证据。
- 规则命中的源码位置现在只作为 `questions_for_human` 导航提示；只有 `source_search` 返回真实文件路径时，才允许进入 `evidence_sources`。
- Agent 工具路由已记录失败工具的尝试状态，源码仓库未配置时不会重复消耗工具轮次，仍可继续检索历史案例和知识库。
- 当前源码验证以本地 `interaction` 源码目录为准；远程 Git 仓库暂未提供，clone/pull live 验证延后。
- 本阶段已验证本地 interaction 源码能返回真实文件路径、`T1Checker::CheckTouch` 函数名、匹配文本和完整 19 行函数上下文。
- 源码证据会附带平台注册的本地 branch/commit；本地 Git 工作区同步返回的 revision 也会作为证据版本。
- 诊断报告新增 `execution_chain`，当前已实现触摸事件进入 interaction、`CheckTouch` 拦截、未进入任务创建/派发阶段的执行链表达。
- LangChain Tool 的输入校验、异常和源码同步状态会进入 LangGraph observation；单个模块工具失败不会中断整条诊断流程。
- 报告新增 `module_relations`，记录主模块到关联模块的触发原因、证据类型和证据引用，关联模块检索由该状态驱动。
- `module_relations` 进一步记录主模块日志与关联模块日志的时间差、双方文件和行号，用于判断跨模块调用顺序。
- 日志上下文按发生时间窗口获取全部模块；源码先分析 `main_module`，再根据模块引用、共享 correlation ID 或异常日志时间近邻按需检索关联模块，不写死 `mc`、`hal_*`、`hds`、`sm` 等名称。
- Agent 的 `source_search` 会在远程 Git 仓库未缓存时 clone，已有 Git 工作区先 `pull --ff-only`，再按 branch/commit 搜索源码。
- 规则模板只作为历史知识和无模型 fallback，不向源码工具注入 Checker、机型、函数名或文件路径；真实 `evidence_sources` 只能来自本次仓库检索结果。
- DeepSeek 必须结合函数控制流分析命中位置；缺少起止模块或证据引用的模型关系会在报告合并时被丢弃。
- 下一步将源码同步和三服务冒烟流程固化为 CI 或集成测试，并把本地知识索引替换或扩展为 knowledge-service/向量检索。
- 测试人员输入保持聚焦于 Bug 现象、发生时间、机器人类型/模块和日志包；仓库更新由 Agent 根据平台注册表自动完成。
- 日志上下文查询优先使用唯一 `log_package_id`，避免日志导入时的外部 bug_id 与平台新生成 Bug ID 不一致导致证据为空。

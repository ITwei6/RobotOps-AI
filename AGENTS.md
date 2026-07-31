# AGENTS.md

本文件是 RobotOps AI 项目的最高优先级协作说明。后续任何 Codex 窗口、开发者或 AI Agent 进入本项目后，必须先阅读本文件，再阅读 `README.md` 和 `docs/`。

## 1. 项目定位

项目正式名称：

```text
RobotOps AI 机器人智能运维与诊断平台
```

当前目录名暂定为：

```text
RobotBugOps
```

注意：本项目不是只做 Bug 日志分析，也不是普通设备管理后台。

它的完整定位是：

```text
面向机器人研发测试阶段和部署运维阶段的一体化 AI 诊断平台。
```

项目分为两个阶段：

| 阶段 | 目标 | 核心能力 |
|---|---|---|
| 研发测试阶段 | 辅助开发工程师分析测试 Bug | Bug 单、日志包解析、源码关联、AI 诊断报告 |
| 部署运维阶段 | 支持机器人交付后的远程运维 | 实时状态、模块心跳、事件告警、远程日志、现场工单 |

第一阶段重点是：

```text
测试人员提交 Bug
  ↓
上传 robot_日期.zip 完整日志包
  ↓
系统解析 interaction / mc / agent / hal / sm / hds 等模块日志
  ↓
Agent 结合 Bug 描述、发生时间、机器人类型、日志上下文和源码仓库分析原因
  ↓
生成诊断报告
```

第二阶段扩展为：

```text
机器人售出/客户现场部署
  ↓
robot-collector / robot-gateway 上报状态、心跳、事件、关键日志
  ↓
平台监控 agent / interaction / mc / hal / sm / hds 模块健康状态
  ↓
告警、工单、远程诊断、历史案例沉淀
```

## 2. 真实业务背景

当前真实研发流程是：

```text
测试人员在飞书提交 Bug
  ↓
组长分配给开发工程师
  ↓
开发工程师根据 Bug 描述、发生时间、机器人类型和日志包排查
  ↓
重点分析 interaction.log
  ↓
必要时关联 mc / hal / sm / hds / agent 日志和源码
  ↓
给出原因、责任模块和修复建议
```

MVP 阶段不强制要求 `robot_id`。真实测试流程里通常先区分：

```text
robot_type: T 型 / Q 型
main_module: interaction / mc / agent / hal_camera / sm / hds
software_version / branch / commit
occurred_time
log_package
source_repo
```

后续部署运维阶段再引入：

```text
robot_sn
customer_id
site_id
online_status
last_heartbeat_at
```

## 3. 机器人模块分层

必须按真实机器人系统理解模块边界：

```text
上层：
  agent / App / 语音 / 业务指令

中间交互编排层：
  interaction

底层能力层：
  mc / hal_camera / hal_audio / hal_touch / bms / sm / hds
```

关键说明：

- `agent` 属于上层，负责对话、意图或业务指令。
- `interaction` 是中间交互编排模块，是 Bug 分析最常看的核心模块。
- `mc` 和 `hal_*` 属于底层能力模块。
- `sm` 表示整机系统状态。
- `hds` 表示健康诊断、故障码和故障等级。

很多问题表面是“机器人没反应”，实际需要通过 `interaction` 判断：

- 上层请求有没有到。
- 触摸/语音/动作请求有没有被接收。
- self check 是否通过。
- 当前 action 是否支持该动作。
- 当前机器人类型是 T 型还是 Q 型。
- bms 是否低电量或正在充电。
- hds 是否存在高等级故障。
- WorkerManager 是否创建任务成功。
- Skill 是否调用 mc/hal 成功。

## 4. 日志包约定

测试人员通常上传完整日志压缩包，命名可能类似：

```text
robot_20260730.zip
robot_20260730.tar.gz
```

解压后建议识别如下结构：

```text
robot_20260730/
  interaction/
    interaction.log
    interaction.log.1
  mc/
    mc.log
  agent/
    agent.log
  hds/
    hds.log
  sm/
    sm.log
  hal_camera/
    hal_camera.log
  hal_audio/
    hal_audio.log
  hal_touch/
    hal_touch.log
```

日志分析不是项目唯一功能，但它是第一阶段的核心入口。

## 5. 技术路线

本项目继续沿用 DeviceOps/dev 环境里已经验证过的技术栈和脚手架思路。

必须优先参考：

```text
../DeviceOps
../cpp-microservice-kit
```

后端技术方向：

- C++17
- brpc + protobuf
- `cc_generic_services = true`
- CMake
- `cpp-microservice-kit`
- MySQL / ODB
- Redis
- Elasticsearch
- RabbitMQ
- Python FastAPI Agent 服务
- LangGraph / LangChain / RAG

不要改成 Java。当前开发者主要掌握 C++ 和 Python，机器人方向也更适合 C++ + Python。

## 6. 服务边界

第一版不要拆太多服务，但文档和接口要按微服务边界设计。

建议第一版服务：

```text
robot-gateway
log-service
ticket-diagnosis-service
agent-service
```

后续演进服务：

```text
robot-service
module-service
event-service
ticket-service
diagnosis-service
knowledge-service
source-index-service
```

职责边界：

- `robot-gateway`：接入机器人侧日志包、状态、心跳、事件。研发阶段处理日志包导入，部署运维阶段处理实时上报。
- `log-service`：日志解析、日志索引、日志检索、时间窗口上下文。
- `ticket-service`：研发 Bug 单和现场工单。
- `diagnosis-service`：诊断任务编排、报告保存、状态流转。
- `agent-service`：Python AI Agent，负责日志证据、源码证据、历史案例和诊断建议生成。
- `knowledge-service`：知识库和历史案例管理，后续再独立。

## 7. 前端方向

本项目不再使用 Qt 作为主前端。

主前端改为 Web 管理台，风格参考：

```text
qinshihu/itops-agent-platform
```

前端定位：

```text
机器人运维与诊断 Web 工作台
```

建议页面：

- 总览仪表盘
- Bug / 工单列表
- Bug 详情与日志包
- 多模块日志检索
- 时间线分析
- AI 诊断报告
- 源码证据视图
- 机器人资产
- 模块实时状态
- 告警事件
- 知识库 / 历史案例

MVP 阶段优先做 Web，不做 Qt。Qt 更适合机器人本体工具或内部调试器，不适合作为这个平台的主展示形态。

## 8. 开发环境约束

后端开发优先在 Linux / dev 容器中完成。

### 8.1 Docker 开发环境规范

项目后端开发环境不是 Ubuntu 宿主机。

所有 C++ 后端服务开发、编译、运行和测试，必须在 Docker 开发容器中完成。

Codex 运行入口可以是 Ubuntu 虚拟机，但是 Ubuntu 宿主机禁止直接执行：

```text
cmake
make
gcc/g++
运行 C++ 后端服务
```

原因：

- 后端依赖由开发容器统一管理。
- `cpp-microservice-kit`、brpc、protobuf 和基础库路径以容器内路径为准。
- 避免 Windows、Ubuntu 宿主机、Docker 容器三套环境产生不一致。

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

如果项目实际放在 `/home/dev/workspace/RobotOps-AI`，以容器内实际路径为准，但必须先进入容器。

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

如果 `cpp-microservice-kit` 路径未找到，先进入容器检查：

```bash
docker exec -it dev-env-service bash
cd /home/dev/workspace
find . -maxdepth 5 -path '*cpp-microservice-kit/CMakeLists.txt'
```

如果后端 CMake 支持 `CPP_MICROSERVICE_KIT_DIR`，则显式传入容器内实际路径：

```bash
docker exec dev-env-service bash -lc "
cd /home/dev/workspace/projects/RobotOps-AI &&
cmake -S . -B build -DCPP_MICROSERVICE_KIT_DIR=<容器内实际cpp-microservice-kit路径> &&
cmake --build build -j1
"
```

虚拟机和开发环境容器的登录凭据通过安全渠道获取，不写入仓库文档。

推荐环境分工：

```text
Linux / dev 容器：
  C++ 后端服务
  Python agent-service
  MySQL / Redis / Elasticsearch / RabbitMQ
  日志包解析和本地联调

Windows：
  Web 前端开发
  浏览器调试
  PowerShell / SSH 端口转发
```

brpc 服务要继续支持 HTTP JSON 调用，方便 Web 前端和 Windows 调试。

PowerShell 调 brpc HTTP JSON 时要注意 JSON 引号问题。推荐使用 `Invoke-RestMethod` 或 `ConvertTo-Json`，避免 curl 引号被 PowerShell 破坏。

## 9. DeviceOps 已有经验必须继承

从旧 DeviceOps 项目继承以下经验：

- 前端不要直接连接 MySQL、Redis、Elasticsearch、RabbitMQ。
- 前端统一通过后端 HTTP JSON / RPC 接口访问。
- brpc/protobuf 接口字段以 `proto/` 为准。
- C++ 服务复用 `cpp-microservice-kit`，不要重复造 RPC、日志、Redis、ES、MQ 封装。
- Python Agent 独立为服务，不要塞进 C++ diagnosis-service。
- Agent 负责分析和生成建议，诊断报告落库由 C++ 业务服务负责。
- RAG 是 Agent 的工具，不等于 Agent。
- 如果证据不足，Agent 必须输出低置信度报告，不能编造结论。
- 研发阶段日志包分析是核心，部署运维阶段实时监控是扩展，不要把二者割裂。

## 10. 每次开发必须注意

每次开始任务前：

1. 先读本文件。
2. 再读 `README.md`。
3. 再读相关 `docs/*.md`。
4. 如果涉及旧项目经验，先查 `../DeviceOps/docs/` 和 `../DeviceOps/proto/`。
5. 如果涉及脚手架能力，先查 `../cpp-microservice-kit/README.md` 和 `source/`。

每次修改时：

- 不要偏离“机器人智能运维与诊断平台”的定位。
- 不要把项目缩窄成单纯日志分析工具。
- 不要把项目写回通用设备运维平台。
- 不要把实时监控作为第一阶段唯一主线。
- 不要把 `robot_id` 设计成研发阶段必填。
- 不要忽略 T 型 / Q 型机器人差异。
- 不要忽略 `interaction` 是核心分析模块。
- 不要在没有说明的情况下切换技术栈。
- 不要在文档里写已经实现但实际没有实现的能力。

每次完成一个阶段后：

1. 更新 `CHANGES.md`。
2. 写清楚本阶段改了什么、为什么改、影响范围、下一步。
3. 检查 `git status`。
4. 按阶段提交 Git commit。
5. 如果用户明确要求 push，再推送到远端。

提交信息建议使用 Conventional Commit：

```text
docs(scope): describe robotops platform positioning
feat(scope): implement log package parser
fix(scope): correct diagnosis task state handling
chore(scope): setup project skeleton
```

## 11. CHANGES.md 规范

`CHANGES.md` 是项目阶段记录，不等同于最终发布 changelog。

每条记录至少包含：

```text
日期
阶段
修改内容
原因
影响范围
下一步
是否已提交 Git
```

任何文档、架构、代码、接口、目录结构的重要变化都必须记录。

## 12. 当前阶段

当前处于：

```text
阶段 5.5：知识库检索工具接入阶段
```

当前已完成 `log-service` 初版、`ticket-diagnosis-service` 初版、`agent-service` 规则模板初版、`ticket-diagnosis-service -> agent-service` 同步诊断编排、`agent-service` LangGraph 工作流骨架、`log_context` / `source_search` / `case_search` / `knowledge_search` 工具取证入口，以及 DeepSeek 结构化报告节点的 mock 可测路径和失败 fallback。当前阶段已接入本地 JSON/JSONL 知识检索，并修复空结果工具重复调用问题。每个阶段完成后必须更新 `CHANGES.md` 并提交 Git。

## 13. 后续开发重心

从当前阶段开始，RobotOps AI 的研发重点转向 `agent-service`。

必须明确：

- 本项目的核心价值在 Agent 诊断能力，不在继续堆叠很多 C++ 后端服务。
- C++ 服务主要承担 Bug 单、日志包、诊断任务、报告保存和接口编排。
- `agent-service` 才是后续重点，要围绕真实 interaction Bug 排障流程持续增强。

后续优先建设 Agent 侧模块：

```text
Bug 上下文解析
日志证据提取
interaction 源码检索
T/Q 机型规则理解
历史案例检索
知识库 / RAG
诊断工作流编排
置信度与证据校验
结构化报告生成
```

LangGraph / LangChain 使用原则：

- LangGraph 用于编排诊断流程。
- LangChain 用于封装日志检索、源码检索、知识库/RAG、历史案例工具。
- RAG 是 Agent 的工具，不等于 Agent 本身。
- 没有日志或源码证据时，Agent 必须输出低置信度，不能编造结论。

后续开发应优先把 interaction 真实 Bug 修复经验沉淀到 Agent 能力中，例如：

- `CheckTouch` / `CheckMove` / self check 拦截。
- `TaskFactory` 是否创建任务。
- `TaskDescription` 是否生成正确 `SkillParamList`。
- `WorkerManager` 是否拒绝、抢占或并行执行。
- `ActionSkill` 是否成功调用 MC `SetMcAction`。
- `MoveSkill` 是否成功发布速度并收到 odom / MC 状态反馈。

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

## 文档优先

当前阶段先完成文档设计，再进入开发。

已有文档：

```text
docs/01_product_definition.md
docs/02_architecture.md
docs/03_data_model.md
docs/04_mvp_plan.md
docs/05_web_frontend_design.md
docs/06_development_guide.md
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
阶段 0：项目重新定位和文档设计
```

当前只完善文档，不写业务代码。

# agent-service 后续重点规划

从阶段 3 开始，RobotOps AI 后续开发重点转向 `agent-service`。

项目不是为了继续拆很多 C++ 服务，也不是做普通后台 CRUD。C++ 服务负责平台入口、日志、任务和报告保存；真正的产品核心是 Agent 能否复现开发工程师分析 interaction Bug 的过程。

## 1. Agent 核心目标

Agent 要模拟真实排障流程：

```text
飞书 Bug 描述 / 发生时间 / 机器人类型
  ↓
日志包 interaction / mc / hds / sm / agent
  ↓
发生时间前后上下文
  ↓
interaction 源码链路
  ↓
历史案例和知识库
  ↓
带证据的诊断报告
```

报告必须回答：

- 请求有没有到 interaction。
- self check 有没有通过。
- Checker 有没有拦截。
- TaskFactory 有没有创建任务。
- TaskDescription 有没有生成正确 Skill。
- WorkerManager 有没有拒绝、抢占或并行执行。
- Skill 有没有调用 MC / HAL 成功。
- MC / HAL / HDS / SM 状态是否符合预期。

## 2. Agent 模块规划

建议按模块建设：

```text
agent_service/
  app/
    main.py                 FastAPI 入口
    models.py               请求响应模型
    rules.py                规则模板
    workflow/               LangGraph 工作流
    tools/
      log_tool.py           调 log-service 获取日志上下文
      source_tool.py        interaction 源码检索
      case_tool.py          历史案例检索
      knowledge_tool.py     知识库 / RAG 检索
    analyzers/
      interaction_analyzer.py
      mc_analyzer.py
      hds_analyzer.py
      sm_analyzer.py
    prompts/
      diagnosis_report.md
```

## 3. 技术路线

当前阶段：

```text
FastAPI + rule-template-v1
```

下一阶段：

```text
FastAPI + LangGraph + LangChain tools
```

使用边界：

- FastAPI 是服务入口。
- LangGraph 负责编排诊断流程。
- LangChain 负责工具封装，不要把所有逻辑塞进一个 prompt。
- RAG 用于知识库、源码片段、历史案例检索，不等同于 Agent。

## 4. interaction 优先知识

Agent 首先要吃透 interaction 链路：

```text
RPC / Topic 输入
  ↓
Scheduler
  ↓
ServicePlugin / SubscribePlugin
  ↓
Checker
  ↓
TaskFactory
  ↓
TaskDescription
  ↓
WorkerManager
  ↓
Skill
  ↓
MC / HAL / Audio / Light
```

优先沉淀的源码位置：

- `interaction/src/scheduler/plugin/service/play_move_service_plugin.cpp`
- `interaction/src/scheduler/plugin/sub/touch_plugin.cpp`
- `interaction/src/scheduler/checker/t1_checker.cpp`
- `interaction/src/scheduler/checker/q1_checker.cpp`
- `interaction/src/task/task_factory.cpp`
- `interaction/src/task_description/t1_move_task_description.cpp`
- `interaction/src/task_description/t1_interaction.cpp`
- `interaction/src/worker/worker_manager.cpp`
- `interaction/src/skill/atomic/action_skill.cpp`
- `interaction/src/skill/atomic/move_skill.cpp`

## 5. 近期优先级

优先级从高到低：

1. `agent-service` 调用 `log-service`，自动获取 occurred_time 前后日志上下文。
2. `agent-service` 增加 interaction 源码检索工具。
3. 将真实 interaction Bug 分析文档沉淀为历史案例。
4. 引入 LangGraph，把规则诊断拆成可观测节点。
5. 引入 LangChain 工具封装和 RAG 检索。
6. 再考虑更多 C++ 服务拆分和持久化增强。

## 6. 约束

- 证据不足必须低置信度。
- 日志证据必须能追溯到模块、文件、行号和原始日志。
- 源码证据必须能追溯到仓库、文件、函数和匹配语句。
- 不要让 Agent 直接修改源码。
- 不要让 Agent 直接写业务数据库。

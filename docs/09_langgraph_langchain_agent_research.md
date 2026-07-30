# LangGraph / LangChain Agent 调研与 RobotOps AI 落地方案

本文记录对 LangGraph、LangChain 以及相关开源 Agent 项目的调研结论，用于指导 RobotOps AI 后续重点开发 `agent-service`。

调研优先级：

1. LangGraph / LangChain 官方文档。
2. LangChain 官方 GitHub 项目。
3. 真实开源 Agent 应用。

## 1. 调研来源

主要参考：

- LangGraph 官方仓库：<https://github.com/langchain-ai/langgraph>
- LangChain Agents 官方文档：<https://docs.langchain.com/oss/python/langchain/agents>
- LangGraph persistence / checkpoint 文档：<https://docs.langchain.com/oss/javascript/langgraph/persistence>
- ReAct 项目页与论文：<https://react-lm.github.io/>
- Google Research ReAct 介绍：<https://research.google/blog/react-synergizing-reasoning-and-acting-in-language-models/>
- LangGraph `create_react_agent` 参考：<https://reference.langchain.com/python/langgraph.prebuilt/chat_agent_executor/create_react_agent>
- LangChain v1 migration / `create_agent` 说明：<https://docs.langchain.com/oss/python/migrate/langchain-v1>
- Open Agent Platform：<https://github.com/langchain-ai/open-agent-platform>
- Open Canvas：<https://github.com/langchain-ai/open-canvas>
- Social Media Agent：<https://github.com/langchain-ai/social-media-agent>
- LangGraph Supervisor：<https://github.com/langchain-ai/langgraph-supervisor-py>
- Agent Protocol：<https://github.com/langchain-ai/agent-protocol>

## 2. 核心结论

### 2.1 LangGraph 适合做诊断流程编排

LangGraph 的价值不在“调用一次大模型”，而在把长流程 Agent 做成可控状态图。

对 RobotOps AI 来说，诊断流程天然是图：

```text
parse_bug
  ↓
fetch_log_context
  ↓
extract_log_evidence
  ↓
search_interaction_source
  ↓
retrieve_history_cases
  ↓
generate_diagnosis_report
  ↓
confidence_check
  ↓
human_review_if_needed
```

这比一个大 prompt 更适合，因为每个节点都有明确输入、输出、失败原因和可测试边界。

### 2.2 LangChain 适合做工具层

LangChain 的 Agent 文档强调 Agent = model + tools。工具可以是函数，也可以封装外部服务。

RobotOps AI 不应该把 LangChain 当成业务框架，而应该把它用在工具层：

```text
log_tool              调 log-service 获取日志上下文
source_tool           检索 interaction 源码
case_tool             检索历史 Bug 案例
knowledge_tool        检索知识库 / RAG
report_tool           生成结构化报告
```

核心诊断状态、证据约束、置信度策略应该留在我们自己的 Agent 工作流里。

### 2.3 ReAct 是 Agent 的基本思想

ReAct = Reasoning + Acting。它的关键不是“让模型输出一段思考”，而是让 Agent 在推理和行动之间循环：

```text
Thought / Reason
  判断下一步需要什么证据
Action
  调用工具，例如查日志、查源码、查历史案例
Observation
  读取工具返回的证据
Thought / Reason
  根据新证据更新判断
...
Final
  输出带证据的结论
```

RobotOps AI 的诊断 Agent 非常适合 ReAct：

```text
Reason:
  "表面现象是触摸后没反应，需要先确认触摸事件有没有到 interaction。"
Act:
  log_tool.query(module="interaction", keyword="touch", time_window=occurred_time)
Observe:
  interaction.log 显示 touch event 到达，并出现 CheckTouch 拦截日志。
Reason:
  "请求已到 interaction，问题不在上游 Agent/App，下一步确认 MC action。"
Act:
  log_tool.query(module="mc", keyword="PASSIVE_DEFAULT", time_window=occurred_time)
Observe:
  mc.log 显示当前 action 仍为 PASSIVE_DEFAULT。
Final:
  输出 interaction CheckTouch 基于 MC action 拦截的报告，并给出源码位置。
```

后续实现时要注意：

- 不要把 ReAct 的内部推理原文直接当最终报告。
- 最终报告必须是结构化 schema。
- 每一次 Action 都应该落到可审计工具调用。
- 每一个 Observation 都应该成为日志证据、源码证据或历史案例证据。
- 如果 Action 无法取得证据，confidence 必须下降。

### 2.4 持久化和 human-in-the-loop 很重要

LangGraph 的 checkpoint / persistence 适合保存图执行状态。

RobotOps AI 需要这个能力：

- 诊断任务可能被人工打断。
- 证据不足时需要开发工程师补日志或确认时间。
- Agent 输出报告后需要人工确认责任模块。
- 后续同一个 Bug 可能重新诊断。

因此后续 LangGraph 工作流应预留：

```text
thread_id = diagnosis_task_id
checkpoint = 每个诊断节点的输入输出
human_review = 低置信度或高风险结论时暂停
```

### 2.5 多 Agent 不要过早做复杂 Supervisor

LangGraph Supervisor 项目说明了层级多 Agent 的模式，但也提醒多数场景可以直接用工具调用方式实现 supervisor pattern。

RobotOps AI 当前不应该一开始就做很多 Agent：

```text
interaction_agent
mc_agent
hds_agent
source_agent
report_agent
```

更稳妥的第一版是一个诊断图，内部有多个 analyzer node：

```text
interaction_analyzer
mc_analyzer
hds_analyzer
sm_analyzer
source_analyzer
```

等规则稳定后，再考虑拆成多 Agent。

### 2.6 开源项目可借鉴点

Open Canvas 可借鉴：

- artifact / report 版本化。
- memory / reflection 保存用户偏好和历史经验。
- 前端不是只显示聊天，而是显示结构化产物。

Social Media Agent 可借鉴：

- human-in-the-loop。
- 外部工具认证和调用。
- 任务不是一次 prompt，而是多步骤流程。

Open Agent Platform 可借鉴：

- Agent 配置和工具配置分离。
- RAG、MCP、agent supervisor 都是可插拔能力。
- 但它已归档，不建议照搬平台架构。

Agent Protocol 可借鉴：

- 后续如果要统一 Agent 服务 API，可以参考 thread / run / stream / state 这类抽象。
- 当前 MVP 不需要一次性实现完整协议。

## 3. RobotOps AI 推荐 Agent 架构

### 3.1 目录结构

建议从当前 `agent_service` 演进为：

```text
agent_service/
  app/
    main.py
    models.py
    settings.py
    rules.py
    workflow/
      state.py
      graph.py
      nodes.py
      prompts.py
    tools/
      log_tool.py
      source_tool.py
      case_tool.py
      knowledge_tool.py
    analyzers/
      interaction_analyzer.py
      mc_analyzer.py
      hds_analyzer.py
      sm_analyzer.py
    report/
      schema.py
      generator.py
      confidence.py
```

### 3.2 Graph State

LangGraph state 建议包含：

```python
class DiagnosisState(TypedDict):
    bug: BugContext
    log_context: list[LogEvidence]
    source_evidence: list[SourceEvidence]
    history_cases: list[HistoryCase]
    knowledge: list[KnowledgeItem]
    hypotheses: list[Hypothesis]
    report: DiagnosisReport | None
    confidence: float
    questions_for_human: list[str]
    errors: list[str]
```

### 3.3 Node 设计

建议节点：

```text
parse_bug_node
  解析 Bug 标题、描述、机器人类型、主模块、发生时间

fetch_log_context_node
  调 log-service 获取 occurred_time 前后日志

extract_interaction_evidence_node
  从 interaction.log 提取请求入口、Checker、TaskFactory、WorkerManager、Skill 证据

extract_mc_evidence_node
  从 mc.log 提取 action_id、运动状态、SetMcAction、速度指令反馈

source_search_node
  根据日志关键句检索 interaction 源码

history_case_node
  检索相似历史 Bug

generate_report_node
  生成结构化诊断报告

confidence_check_node
  判断证据是否足够，必要时转人工确认
```

### 3.4 ReAct Loop 在图里的落点

RobotOps AI 不建议直接套一个通用 `create_react_agent` 就结束。更合适的是把 ReAct 思想落到我们自己的 LangGraph 节点里：

```text
diagnosis_planner_node
  产生下一步取证计划

tool_executor_node
  执行 log_tool / source_tool / case_tool / knowledge_tool

observation_analyzer_node
  把工具返回结果转成 evidence 和 hypotheses

should_continue_node
  判断继续取证、生成报告、还是转人工确认
```

这样做的好处：

- 诊断步骤可观测。
- 证据链可保存。
- 每个工具调用可审计。
- 低置信度可以被明确路由到人工确认。
- 不会被一个通用 Agent loop 带偏成开放式聊天。

### 3.5 工具边界

工具只负责取数据，不负责最终结论：

```text
log_tool:
  输入 bug_id / package_id / occurred_time / module_name
  输出日志上下文

source_tool:
  输入 repo / branch / commit / keyword
  输出源码位置和片段

case_tool:
  输入 robot_type / main_module / symptoms / evidence keywords
  输出相似案例

knowledge_tool:
  输入故障码 / action_id / 模块名
  输出知识库条目
```

最终结论必须由 `generate_report_node + confidence_check_node` 汇总，并保留证据链。

## 4. 第一阶段实现建议

不要立即把现有 `rule-template-v1` 全部推翻。推荐迭代路径：

1. 保留 `/diagnose` API。
2. 新增 `tools/log_tool.py`，先用 HTTP 调 `log-service`。
3. 新增 `workflow/state.py` 和 `workflow/graph.py`，把现有规则包成第一个 LangGraph 节点。
4. 新增 `extract_interaction_evidence_node`。
5. 新增 `source_tool.py`，先用 `ripgrep` 检索本地 interaction 源码。
6. 新增 `diagnosis_planner_node`，把 ReAct 的 Reason 步骤变成可控计划。
7. 新增 `tool_executor_node`，把 ReAct 的 Act 步骤限制在白名单工具内。
8. 新增 `observation_analyzer_node`，把 ReAct 的 Observation 步骤转成证据。
9. 再引入 LLM 生成报告，但输出必须符合 `DiagnosisReport` schema。

## 5. 不建议做的事

- 不要一开始做复杂多 Agent supervisor。
- 不要把所有逻辑塞进一个超长 prompt。
- 不要让 LLM 直接查数据库或写数据库。
- 不要让 Agent 在没有日志证据时给高置信度结论。
- 不要脱离 interaction 真实代码链路泛化成普通 IT 运维 Agent。
- 不要无边界暴露工具给 ReAct Agent；工具必须有白名单、参数 schema 和超时。
- 不要把模型的中间 Thought 原样展示给测试或客户，应该展示可审计的证据和结论。

## 6. 下一步开发任务

下一阶段建议直接做：

```text
feat(agent): add log tool and langgraph diagnosis workflow skeleton
```

最小验收：

- `agent-service` 增加 LangGraph 依赖。
- 新增 `DiagnosisState`。
- 新增 `build_diagnosis_graph()`。
- 新增 `log_tool`，可以调用 `log-service.GetLogContext`。
- `/diagnose` 可以走 LangGraph workflow。
- workflow 中体现 ReAct 思想：plan -> tool action -> observation -> report。
- 当前 interaction 触摸拦截样例仍能输出同等报告。

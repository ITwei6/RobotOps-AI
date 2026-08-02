# agent-service 后续重点规划

从阶段 3 开始，RobotOps AI 后续开发重点转向 `agent-service`。

项目不是为了继续拆很多 C++ 服务，也不是做普通后台 CRUD。C++ 服务负责平台入口、日志、任务和报告保存；真正的产品核心是 Agent 能否复现开发工程师分析机器人多模块 Bug 的过程。interaction 是最常见的主入口，但不是唯一可分析模块。

## 1. Agent 核心目标

Agent 要模拟真实排障流程：

```text
飞书 Bug 描述 / 发生时间 / 机器人类型
  ↓
日志包中的全部模块
  ↓
发生时间前后上下文
  ↓
主模块源码命中函数上下文
  ↓
按证据关联其他模块日志和源码
  ↓
历史案例和知识库
  ↓
带证据的诊断报告
```

报告应根据本次证据回答：

- Bug 现象对应的请求、事件或状态变化首先出现在哪个模块。
- 主模块在哪个源码函数、分支或状态检查中产生了对应日志。
- 命中函数的前置条件、分支和返回路径是否能解释现象。
- 日志和源码是否明确引用其他模块，是否存在共享请求 ID 或同时间异常。
- 关联模块是否有证据证明请求到达、执行成功、拒绝或超时。
- 证据不足时还缺哪些日志、版本或现场信息。

对于 interaction Bug，上述问题通常具体表现为 self check、Checker、TaskFactory、TaskDescription、WorkerManager、Skill 以及 MC/HAL 状态，但这些是领域知识示例，不是工作流中的固定步骤。

## 2. Agent 模块规划

建议按模块建设：

```text
agent_service/
  app/
    main.py                 FastAPI 入口
    models.py               请求响应模型
    rules.py                历史规则和 deterministic fallback
    source_queries.py       从本次 Bug/日志生成通用源码查询
    workflow/               LangGraph 工作流
    tools/
      log_tool.py           调 log-service 获取日志上下文
      source_tool.py        按模块同步、检索并提取源码上下文
      case_tool.py          历史案例检索
      knowledge_tool.py     知识库 / RAG 检索
    llm/
      deepseek.py           结构化上下文分析和报告生成
```

## 3. 技术路线

当前阶段：

```text
FastAPI + LangGraph + LangChain StructuredTool + DeepSeek
```

使用边界：

- FastAPI 是服务入口。
- LangGraph 负责编排诊断流程。
- LangChain 负责工具封装，不要把所有逻辑塞进一个 prompt。
- RAG 用于知识库、源码片段、历史案例检索，不等同于 Agent。
- 规则模板负责已知经验和无模型 fallback，不负责指定本次源码路径。
- 大模型负责阅读工具返回的真实上下文，不允许绕过证据直接选择责任模块。

## 4. 通用流程与 interaction 优先知识

所有 Bug 使用同一条取证主流程：

```text
Bug + occurred_time + log_package_id
  ↓
获取时间窗口内全部模块日志
  ↓
优先分析 main_module
  ↓
从该模块日志动态提取稳定文本和代码标识符
  ↓
在该模块完整仓库中定位并提取函数/文件上下文
  ↓
根据模块引用、共享 correlation ID、异常时间近邻决定是否深入其他模块
  ↓
DeepSeek 结合上下文生成报告
  ↓
证据字段校验和置信度校准
```

禁止把 `CheckTouch`、T/Q Checker、某个固定文件或 interaction 专用目录作为源码检索入口。真实 Bug 经验可以进入规则、案例或知识库，但只能作为先验参考。

interaction 仍是第一阶段要优先吃透的领域链路：

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

以下源码位置适合沉淀为 interaction 知识和历史案例，不作为检索器硬编码：

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

已完成：

- 根据每轮真实源码中的被调函数、RPC/Topic 和接口类型生成后续查询。
- 使用 DeepSeek 结构化规划后续源码调查；模型不可用时使用通用符号提取 fallback。
- 对模型查询执行模块白名单、源码原文、证据引用和重复查询校验，并限制源码分析轮次。

下一阶段优先级：

1. 增加符号索引、文件摘要和调用关系索引，支持大仓库上下文扩展。
2. 将真实 interaction、mc、hal、hds、sm、agent Bug 诊断过程沉淀为可检索历史案例。
3. 将本地案例和知识文件扩展为 knowledge-service / RAG。
4. 增加 LangGraph checkpoint、诊断轨迹持久化和人工复核反馈。
5. 再考虑更多 C++ 服务拆分和持久化增强。

## 6. 约束

- 证据不足必须低置信度。
- 日志证据必须能追溯到模块、文件、行号和原始日志。
- 源码证据必须能追溯到仓库、文件、函数和匹配语句。
- 源码检索查询必须来自本次 Bug/日志或前一轮真实源码观察，不能来自固定 Bug 路径表。
- 模型生成的源码查询只是候选计划，必须能在本轮源码上下文中找到原文并引用对应证据后才能执行。
- 源码分析必须受独立轮次上限和全局工具次数上限约束。
- 模块关系必须带日志或源码证据引用；模型自由推测的关系不能进入最终报告。
- 不要让 Agent 直接修改源码。
- 不要让 Agent 直接写业务数据库。

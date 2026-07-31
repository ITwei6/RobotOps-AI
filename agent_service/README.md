# agent-service

`agent-service` 是 RobotOps AI 的 Python 诊断 Agent 服务。

当前阶段实现：

- FastAPI HTTP 服务。
- `GET /health` 健康检查。
- `POST /diagnose` 结构化诊断接口。
- `rule-template-v1` 规则模板诊断，优先覆盖 interaction 研发 Bug 常见链路。
- `langgraph-diagnosis-v1` 工作流骨架，内部按 `normalize_input -> rule_evidence -> planner -> report -> confidence_check -> finalize` 执行。

当前策略：

```text
Bug 描述 / 机器人类型 / 主模块
  + 日志证据
  + 源码证据
  ↓
规则模板匹配
  ↓
结构化诊断报告
```

第一版不直接接大模型，避免证据不足时编造结论。未命中规则时会输出低置信度报告和需要人工确认的问题。

后续演进：

- 继续完善 LangGraph 的 `planner -> tool action -> observation -> report` 循环。
- 用 LangChain 封装日志检索、源码检索、知识库/RAG、历史案例检索等工具。
- RAG 是 Agent 的工具，不等于 Agent 本身。

## 本地运行

```bash
python3 -m pip install -r agent_service/requirements.txt
uvicorn agent_service.app.main:app --host 0.0.0.0 --port 9601
```

## 测试

```bash
python3 -m unittest discover -s agent_service/tests
```

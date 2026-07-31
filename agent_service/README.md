# agent-service

`agent-service` 是 RobotOps AI 的 Python 诊断 Agent 服务。

当前阶段实现：

- FastAPI HTTP 服务。
- `GET /health` 健康检查。
- `POST /diagnose` 结构化诊断接口。
- `rule-template-v1` 规则模板诊断，优先覆盖 interaction 研发 Bug 常见链路。
- `langgraph-diagnosis-v1` 工作流骨架，内部按 `normalize_input -> rule_evidence -> planner -> tool_executor -> observation_analyzer -> report -> confidence_check -> finalize` 执行。
- `log_context` 工具初版，调用 `log-service.GetLogContext` 获取发生时间窗口日志。
- `source_search` 工具初版，优先用 `rg` 检索本地 interaction 源码，缺少 `rg` 时使用标准库递归文本搜索兜底。
- DeepSeek 结构化报告节点加固：LLM 报告必须通过 `DiagnosisReport` 校验，成功时合并规则证据，失败时 fallback 到规则报告。
- `case_search` 历史案例工具：读取配置目录下的 JSON/JSONL 案例，按 Bug 描述、T/Q 机型、模块和日志关键词匹配。
- `knowledge_search` 知识检索工具：读取配置目录下的 JSON/JSONL SOP、错误码和模块说明，返回带 `source` 的参考条目。

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
- 继续接入历史案例检索和知识库/RAG。
- RAG 是 Agent 的工具，不等于 Agent 本身。

## 配置

```bash
ROBOTOPS_LOG_SERVICE_URL=http://127.0.0.1:9501
ROBOTOPS_SOURCE_SEARCH_ROOTS=../interaction:../aimrt_agent/aimrt_agent/interaction
ROBOTOPS_CASE_SEARCH_ROOTS=knowledge/cases:docs/cases
ROBOTOPS_KNOWLEDGE_SEARCH_ROOTS=knowledge/articles:docs/knowledge
ROBOTOPS_AGENT_TOOL_TIMEOUT_SECONDS=5
ROBOTOPS_AGENT_MAX_TOOL_ITERATIONS=4
ROBOTOPS_LLM_ENABLED=true
ROBOTOPS_LLM_MODEL=deepseek-v4-flash
DEEPSEEK_API_KEY=<通过安全渠道注入，不写入仓库>
```

## 本地运行

```bash
python3 -m pip install -r agent_service/requirements.txt
uvicorn agent_service.app.main:app --host 0.0.0.0 --port 9601
```

## 测试

```bash
python3 -m unittest discover -s agent_service/tests
```

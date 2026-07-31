# agent-service

`agent-service` 是 RobotOps AI 的 Python 诊断 Agent 服务。

当前阶段实现：

- FastAPI HTTP 服务。
- `GET /health` 健康检查。
- `POST /diagnose` 结构化诊断接口。
- `rule-template-v1` 规则模板诊断，优先覆盖 interaction 研发 Bug 常见链路。
- `langgraph-diagnosis-v1` 工作流骨架，内部按 `normalize_input -> rule_evidence -> planner -> tool_executor -> observation_analyzer -> report -> confidence_check -> finalize` 执行。
- `log_context` 工具初版，调用 `log-service.GetLogContext` 获取发生时间窗口日志。
- 当请求包含 `log_package_id` 时，`log_context` 以日志包为主键查询，不强制附带可能不一致的 bug_id。
- `source_search` 工具初版，优先用 `rg` 检索本地 interaction 源码，缺少 `rg` 时使用标准库递归文本搜索兜底。
- DeepSeek 结构化报告节点加固：LLM 报告必须通过 `DiagnosisReport` 校验，成功时合并规则证据，失败时 fallback 到规则报告。
- `case_search` 历史案例工具：读取配置目录下的 JSON/JSONL 案例，按 Bug 描述、T/Q 机型、模块和日志关键词匹配。
- `knowledge_search` 知识检索工具：读取配置目录下的 JSON/JSONL SOP、错误码和模块说明，返回带 `source` 的参考条目。
- C++ `ticket-diagnosis-service.RunDiagnosis` 可通过 `log_package_id` 触发 Agent 自动调用 `log-service` 获取发生时间窗口日志。
- 平台源码仓库注册表：管理员通过 `GET /source-repositories` 查看，`PUT /source-repositories/{module_name}` 配置 `repo_url`、默认 `branch`、可选 `commit` 和 `local_path`；诊断时按 `main_module` 自动取用。
- `source_search` 支持源码工作区同步：远程 `source_repo` 未缓存时 clone，已有 Git 仓库先 `pull --ff-only`，可按 branch/commit 固定版本后再检索。
- 本地 interaction 目录可以通过源码仓库注册表的 `local_path` 使用；检索结果会保留配置的 branch/commit，未指定 commit 时使用本地 Git 工作区同步返回的 revision。
- `DiagnosisReport.execution_chain` 用于表达日志和规则支持的执行阶段；当前覆盖 `CheckTouch` 拦截链，不代表未观测到的后续阶段已被证明。

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
ROBOTOPS_SOURCE_WORKSPACE_ROOT=.robotops/source-cache
ROBOTOPS_SOURCE_REPOSITORY_FILE=.robotops/source-repositories.json
ROBOTOPS_CASE_SEARCH_ROOTS=knowledge/cases:docs/cases
ROBOTOPS_KNOWLEDGE_SEARCH_ROOTS=knowledge/articles:docs/knowledge
ROBOTOPS_AGENT_TOOL_TIMEOUT_SECONDS=5
ROBOTOPS_AGENT_MAX_TOOL_ITERATIONS=4
ROBOTOPS_AGENT_HTTP_TIMEOUT_MS=120000
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

# agent-service

`agent-service` 是 RobotOps AI 的 Python 诊断 Agent 服务。

当前阶段实现：

- FastAPI HTTP 服务。
- `GET /health` 健康检查。
- `POST /diagnose` 结构化诊断接口。
- `rule-template-v1` 规则模板诊断，优先覆盖 interaction 研发 Bug 常见链路。
- `langgraph-diagnosis-v3` 工作流，内部按 `normalize_input -> rule_evidence -> planner -> tool_executor -> observation_analyzer -> source_analysis -> report -> confidence_check -> finalize` 执行。
- `log_context` 工具初版，调用 `log-service.GetLogContext` 获取发生时间窗口日志。
- 当请求包含 `log_package_id` 时，`log_context` 以日志包为主键查询，不强制附带可能不一致的 bug_id。
- `source_search` 通用源码工具，按 `module_name` 使用平台注册仓库；符号、调用方和接口查询优先使用本地索引，索引未命中时使用 `rg`，缺少 `rg` 时使用标准库递归文本搜索兜底。
- 源码索引记录 C/C++ 与 Python 函数、函数调用、Topic/RPC 风格路径和文件结构摘要，不包含固定模块或业务函数规则。
- 索引绑定同步后的 Git revision。revision 更新时用 `git diff --name-only` 定位变更文件；revision 不变时比较文件 `mtime/size`，处理本地修改、新增和删除。
- 非 Git 目录生成 `workspace-*` 内容快照作为证据版本；索引刷新使用进程锁、文件锁和原子替换，失败时自动回退全文检索。
- `source_queries.py` 从本次 Bug 和模块日志动态提取稳定短语、限定函数名、代码标识符与 Topic/路径，过滤运行时 ID 和数值，不使用规则提供的固定文件或函数。
- 源码命中会提取 C/C++ 或 Python 所在函数上下文；函数过长时保留函数头、命中区和结尾，无法识别时返回小文件全文或大文件扩展窗口。
- `source_analysis` 会让 DeepSeek 根据本轮真实源码上下文输出结构化后续调查计划，查询只有通过模块白名单、源码原文、证据引用和去重校验后才会回到 `source_search` 执行。
- DeepSeek 规划不可用或候选查询未通过校验时，Agent 从当前源码片段通用提取被调符号作为 deterministic fallback；两种模式都不依赖固定业务函数或文件路径。
- 源码分析使用独立迭代上限，达到上限、没有新证据或模型确认信息充分时停止并进入报告阶段。
- DeepSeek 结构化报告节点加固：`deepseek-v4-flash` 使用 `json_mode`，prompt 显式携带 `DiagnosisReport` JSON schema，结果必须通过 Pydantic 校验；成功时合并规则证据，失败时 fallback 到规则报告。
- `case_search` 历史案例工具：读取配置目录下的 JSON/JSONL 案例，按 Bug 描述、T/Q 机型、模块和日志关键词匹配。
- `knowledge_search` 知识检索工具：读取配置目录下的 JSON/JSONL SOP、错误码和模块说明，返回带 `source` 的参考条目。
- C++ `ticket-diagnosis-service.RunDiagnosis` 可通过 `log_package_id` 触发 Agent 自动调用 `log-service` 获取发生时间窗口日志。
- 平台源码仓库注册表：管理员通过 `GET /source-repositories` 查看，`PUT /source-repositories/{module_name}` 配置 `repo_url`、默认 `branch`、可选 `commit` 和 `local_path`；诊断时按 `main_module` 自动取用。
- `source_search` 支持源码工作区同步：远程 `source_repo` 未缓存时 clone，已有 Git 仓库先 `pull --ff-only`，可按 branch/commit 固定版本后再检索。
- 任意模块本地目录都可以通过源码仓库注册表的 `local_path` 使用；检索结果会保留配置的 branch/commit，未指定 commit 时使用本地 Git 工作区同步返回的 revision。无效空 `.git` 标记不会触发错误的 `git pull`。
- `DiagnosisReport.execution_chain` 用于表达日志和规则支持的执行阶段；当前覆盖 `CheckTouch` 拦截链，不代表未观测到的后续阶段已被证明。
- `DiagnosisReport.module_relations` 记录主模块到关联模块的关系、触发原因、证据类型和证据引用；关系可由显式模块引用、共享 correlation ID 或异常时间近邻产生，只有确认关联后 workflow 才继续检索对应模块源码。
- `DiagnosisReport.generation_mode` 明确区分 `deepseek`、`llm_fallback` 和 `deterministic_fallback`；`generation_detail` 只记录非敏感运行说明。
- 如果双方日志存在有效 `log_time`，模块关系还会记录 `time_delta_ms`、`source_log_ref` 和 `target_log_ref`；源码证据会覆盖同一关系的早期日志提示，但保留时间线字段。

当前策略：

```text
Bug 描述 / 机器人类型 / 主模块
  + log_package_id
  ↓
按 occurred_time 获取多模块日志
  ↓
按模块动态生成源码查询
  ↓
提取命中函数 / 文件上下文
  ↓
分析本轮源码并生成经过证据校验的后续查询
  ↺ 在迭代上限内继续源码检索
  ↓
LangGraph 按证据关系继续检索关联模块
  ↓
DeepSeek 生成结构化报告
  ↓
证据校验 / 置信度校准 / fallback
```

DeepSeek 可用时负责阅读真实日志和源码上下文；规则模板只是补充先验及 deterministic fallback，不决定源码路径。DeepSeek 不可用、输出校验失败或证据不足时，工作流会降级并压低置信度。

后续演进：

- LangGraph 已编排 `planner -> tool_executor -> observation -> report` 循环；`tool_executor` 通过 `app/langchain_tools.py` 的 `StructuredTool` 执行日志、源码、案例和知识工具。
- LangChain Tool 的输入校验和运行时异常会转换为 observation error；source tool 的 `source_sync` 和 `source_index` 状态会随 observation 保留，便于追溯源码版本、索引更新和 fallback。
- 将源码调查轨迹、仓库 revision 和索引状态结构化透传到 C++ 报告及 Web 源码证据视图。
- 将本地历史案例和知识检索扩展为 knowledge-service / RAG 索引。
- RAG 是 Agent 的工具，不等于 Agent 本身。

## 配置

```bash
ROBOTOPS_LOG_SERVICE_URL=http://127.0.0.1:9501
ROBOTOPS_SOURCE_SEARCH_ROOTS=../interaction:../aimrt_agent/aimrt_agent/interaction
ROBOTOPS_SOURCE_WORKSPACE_ROOT=.robotops/source-cache
ROBOTOPS_SOURCE_INDEX_ROOT=.robotops/source-index
ROBOTOPS_SOURCE_REPOSITORY_FILE=.robotops/source-repositories.json
ROBOTOPS_CASE_SEARCH_ROOTS=knowledge/cases:docs/cases
ROBOTOPS_KNOWLEDGE_SEARCH_ROOTS=knowledge/articles:docs/knowledge
ROBOTOPS_AGENT_TOOL_TIMEOUT_SECONDS=5
ROBOTOPS_AGENT_MAX_TOOL_ITERATIONS=8
ROBOTOPS_AGENT_MAX_SOURCE_ANALYSIS_ITERATIONS=3
ROBOTOPS_AGENT_HTTP_TIMEOUT_MS=300000
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

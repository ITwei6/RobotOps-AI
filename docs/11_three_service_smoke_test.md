# 三服务诊断冒烟验证

本验证覆盖研发阶段最小闭环：

```text
样例日志目录
  -> log-service.ImportLogPackage
  -> ticket-diagnosis-service.RunDiagnosis
  -> agent-service /diagnose
  -> agent-service log_context
  -> log-service.GetLogContext
  -> 结构化诊断报告
```

## 容器内准备

在 `dev-env-service` 中执行：

```bash
cd /home/dev/workspace/RobotOps-AI
cmake --build build -j1 --target log_service ticket_diagnosis_service
```

启动三个服务：

```bash
ROBOTOPS_LOG_RPC_PORT=19501 ./build/backend/services/log_service/log_service
ROBOTOPS_LOG_SERVICE_URL=http://127.0.0.1:19501 \
  ROBOTOPS_LLM_ENABLED=false \
  uvicorn agent_service.app.main:app --host 127.0.0.1 --port 19601
ROBOTOPS_AGENT_SERVICE_URL=http://127.0.0.1:19601 \
  ROBOTOPS_AGENT_HTTP_TIMEOUT_MS=300000 \
  ROBOTOPS_TICKET_DIAGNOSIS_RPC_PORT=19502 \
  ./build/backend/services/ticket_diagnosis_service/ticket_diagnosis_service
```

## 导入日志

```bash
curl -sS -X POST http://127.0.0.1:19501/robotops.log.LogService/ImportLogPackage \
  -H 'Content-Type: application/json' \
  -d '{
    "bug_id":"bug-touch-001",
    "package_id":"pkg-20260730",
    "package_path":"samples/robot_20260730",
    "robot_type":"ROBOT_TYPE_T"
  }'
```

## 创建 Bug 并发起诊断

`CreateBugTicket` 返回的 `ticket.bug_id` 作为下一步请求的 `bug_id`。测试人员只需提交 Bug 现象、时间和日志包；`log_package_id` 在创建 Bug 时保存到 ticket，也可以在 `RunDiagnosisRequest` 中显式传入。源码仓库由平台管理员提前通过 `/source-repositories/{module_name}` 配置。

```bash
curl -sS -X POST http://127.0.0.1:19502/robotops.ticket_diagnosis.TicketDiagnosisService/CreateBugTicket \
  -H 'Content-Type: application/json' \
  -d '{
    "title":"触摸后机器人没有反应",
    "description":"T 型机器人拍触摸板没有站起",
    "robot_type":"ROBOT_TYPE_T",
    "main_module":"interaction",
    "occurred_time":1785396730000,
    "log_package_id":"pkg-20260730",
    "source_repo":"interaction"
  }'
```

```bash
curl -sS -X POST http://127.0.0.1:19502/robotops.ticket_diagnosis.TicketDiagnosisService/RunDiagnosis \
  -H 'Content-Type: application/json' \
  -d '{
    "bug_id":"<上一步返回的bug_id>",
    "log_package_id":"pkg-20260730"
  }'
```

预期结果：

- `RunDiagnosisResponse.response.code` 为 `0`。
- 报告 `suspected_module` 为 `interaction`。
- 报告包含 `Current action is DAMPING_DEFAULT...` 日志证据。
- 报告包含 `T1Checker::CheckTouch` 源码提示，或在没有本地 interaction 源码时至少保留日志证据并降低置信度。

本冒烟验证不注入 DeepSeek API key，使用 deterministic fallback，避免凭据进入命令行和测试日志。

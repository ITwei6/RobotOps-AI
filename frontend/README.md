# RobotOps AI Web Console

RobotOps AI 的 Web 诊断工作台 MVP。首屏面向研发测试排障，围绕 Bug 上下文、Agent 执行链、多模块日志证据、源码证据和模块状态展示信息。

## Development

```bash
npm install
npm run dev -- --host 0.0.0.0
```

默认地址：`http://127.0.0.1:4173`。

需要前端、C++ 服务和 Agent 全部联通时，在项目根目录执行：

```bash
./scripts/run_dev_stack.sh
```

## Views

- 总览：诊断摘要、模块信号、证据时间线和下一步动作。
- Bug 分析：提交现象、发生时间、机器人类型、主模块和日志包 ID。
- 日志时间线：查看主模块与关联模块的时间线及时间差。
- 模块状态：查看 interaction、mc、hds、sm、hal_touch、agent 的状态卡片。

## API

页面提交 Bug 分析时依次请求 `POST /api/CreateBugTicket` 和 `POST /api/RunDiagnosis`。Vite 开发代理默认将 `/api` 转发到 Docker 映射的 `http://127.0.0.1:9002/robotops.ticket_diagnosis.TicketDiagnosisService`，再由 C++ 服务调用 Agent，Agent 按需调用 log-service。前端不直接访问数据库或 Agent 内部服务。

## Design System

本阶段使用 `ui-ux-pro-max-skill` 生成并持久化设计基线，文件位于 `../design-system/robotops-ai/MASTER.md`。实际界面针对 RobotOps 运维场景调整为高密度、低装饰、可扫描的工程工作台，并使用 Lucide 图标和响应式布局。

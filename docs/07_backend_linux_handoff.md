# Linux 后端开发交接文档

本文档给 Linux / dev 容器中的 Codex 使用。当前目标是继续开发 RobotOps AI 后端，并且能在 Linux 环境中直接编译、运行、测试。

## 1. 当前仓库信息

仓库：

```text
https://github.com/ITwei6/RobotOps-AI.git
```

Linux 容器中的当前路径示例：

```text
/home/dev/workspace/RobotOps-AI
```

当前已完成提交：

```text
74eeeb0 docs(project): initialize robotops ai documentation
46bd8f0 feat(log): add robot module log service
```

## 2. 开发前必须阅读

请先按顺序阅读：

```text
AGENTS.md
README.md
CHANGES.md
docs/01_product_definition.md
docs/02_architecture.md
docs/03_data_model.md
docs/04_mvp_plan.md
docs/05_web_frontend_design.md
docs/06_development_guide.md
docs/07_backend_linux_handoff.md
```

如果需要参考旧项目：

```text
/home/dev/workspace/projects/DeviceOps
/home/dev/workspace/DeviceOps
```

如果需要参考脚手架：

```text
cpp-microservice-kit
```

先用 `find` 查实际路径，不要假设它一定在某个目录。

## 2.1 Docker 开发环境规范

项目后端开发环境不是 Ubuntu 宿主机。Ubuntu 虚拟机只是 Codex 和 Docker 的运行入口，所有 C++ 后端服务开发、编译、运行和测试都必须进入 Docker 开发容器。

容器名称：

```text
dev-env-service
```

Ubuntu 宿主机禁止直接执行：

```text
cmake
make
gcc/g++
运行 C++ 后端服务
```

推荐代码映射：

```text
Ubuntu 宿主机：
~/Desktop/projects/RobotOps-AI

Docker 容器：
/home/dev/workspace/projects/RobotOps-AI
```

如果实际项目路径不同，以容器内实际路径为准。

先确认容器：

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

正确编译方式：

```bash
docker exec dev-env-service bash -lc "
cd /home/dev/workspace/projects/RobotOps-AI &&
mkdir -p build &&
cd build &&
cmake .. &&
make -j\$(nproc)
"
```

如果 `cpp-microservice-kit` 路径未找到，进入容器查找：

```bash
docker exec -it dev-env-service bash
cd /home/dev/workspace
find . -maxdepth 5 -path '*cpp-microservice-kit/CMakeLists.txt'
```

如果后端 CMake 支持 `CPP_MICROSERVICE_KIT_DIR`，推荐显式传入：

```bash
cd /home/dev/workspace/projects/RobotOps-AI
cmake -S . -B build -DCPP_MICROSERVICE_KIT_DIR=<容器内实际cpp-microservice-kit路径>
cmake --build build -j1
```

虚拟机和开发环境容器的登录凭据通过安全渠道获取，不写入仓库文档。

## 3. 当前最先要修的问题

当前 Linux 下执行：

```bash
cmake -S . -B build
cmake --build build -j1
```

遇到过这个错误：

```text
CMake Error at CMakeLists.txt:15 (add_subdirectory):
  add_subdirectory given source "/home/dev/workspace/cpp-microservice-kit"
  which is not an existing directory.
```

原因：

当前顶层 `CMakeLists.txt` 写死了：

```cmake
${CMAKE_CURRENT_SOURCE_DIR}/../cpp-microservice-kit
```

但 Linux 容器中 `RobotOps-AI` 的位置是：

```text
/home/dev/workspace/RobotOps-AI
```

而 `cpp-microservice-kit` 不一定在：

```text
/home/dev/workspace/cpp-microservice-kit
```

## 4. 推荐修复方案

不要继续硬编码单一路径。请把顶层 `CMakeLists.txt` 改成可配置、可自动探测。

推荐逻辑：

```cmake
set(CPP_MICROSERVICE_KIT_DIR "" CACHE PATH "Path to cpp-microservice-kit")

if(NOT CPP_MICROSERVICE_KIT_DIR)
    set(CPP_MICROSERVICE_KIT_CANDIDATES
        "${CMAKE_CURRENT_SOURCE_DIR}/../cpp-microservice-kit"
        "${CMAKE_CURRENT_SOURCE_DIR}/../third_party/cpp-microservice-kit"
        "${CMAKE_CURRENT_SOURCE_DIR}/third_party/cpp-microservice-kit"
        "${CMAKE_CURRENT_SOURCE_DIR}/../DeviceOps/third_party/cpp-microservice-kit"
        "${CMAKE_CURRENT_SOURCE_DIR}/../projects/cpp-microservice-kit"
        "${CMAKE_CURRENT_SOURCE_DIR}/../../cpp-microservice-kit")

    foreach(CANDIDATE ${CPP_MICROSERVICE_KIT_CANDIDATES})
        if(EXISTS "${CANDIDATE}/CMakeLists.txt")
            set(CPP_MICROSERVICE_KIT_DIR "${CANDIDATE}")
            break()
        endif()
    endforeach()
endif()

if(NOT CPP_MICROSERVICE_KIT_DIR OR NOT EXISTS "${CPP_MICROSERVICE_KIT_DIR}/CMakeLists.txt")
    message(FATAL_ERROR
        "cpp-microservice-kit not found. "
        "Please configure with -DCPP_MICROSERVICE_KIT_DIR=/path/to/cpp-microservice-kit")
endif()

get_filename_component(CPP_MICROSERVICE_KIT_DIR "${CPP_MICROSERVICE_KIT_DIR}" ABSOLUTE)
message(STATUS "Using cpp-microservice-kit: ${CPP_MICROSERVICE_KIT_DIR}")
```

这样 Linux 下也可以手动指定：

```bash
cmake -S . -B build -DCPP_MICROSERVICE_KIT_DIR=/actual/path/to/cpp-microservice-kit
```

## 5. 如何查找脚手架路径

在 Linux 容器中执行：

```bash
cd /home/dev/workspace
find . -maxdepth 4 -type d -name cpp-microservice-kit
```

如果找不到，可以看旧项目是否有 third_party：

```bash
find . -maxdepth 5 -path '*cpp-microservice-kit/CMakeLists.txt'
```

找到后再执行：

```bash
cmake -S . -B build -DCPP_MICROSERVICE_KIT_DIR=<查到的路径>
cmake --build build -j1
```

## 6. 当前已实现的后端能力

当前只有第一个子服务：

```text
log-service
```

路径：

```text
backend/services/log_service/
```

proto：

```text
proto/common.proto
proto/log.proto
```

已实现接口：

```text
robotops.log.LogService.ImportLogPackage
robotops.log.LogService.QueryLogs
robotops.log.LogService.GetLogContext
robotops.log.LogService.ListLogFiles
```

当前 MVP 行为：

- 支持已解压日志目录。
- 识别第一级目录作为模块名，例如 `interaction`、`mc`、`agent`、`hds`。
- 解析常见日志行的时间、等级、消息和原始行。
- 使用内存索引保存导入结果。
- 暂未接入 Elasticsearch / MySQL / Redis / RabbitMQ。
- `log-service.ImportLogPackage` 已支持目录、`.zip`、`.tar`、`.tar.gz` 和 `.tgz`；压缩包会在临时目录安全解压并自动识别外层目录，完成解析后清理临时文件。

样例日志：

```text
samples/robot_20260730/
  interaction/interaction.log
  mc/mc.log
  agent/agent.log
  hds/hds.log
```

## 7. log-service 编译后测试方式

构建：

```bash
cmake -S . -B build -DCPP_MICROSERVICE_KIT_DIR=<实际路径>
cmake --build build -j1
```

启动：

```bash
ROBOTOPS_LOG_RPC_PORT=9501 ./build/backend/services/log_service/log_service
```

另开终端导入样例日志：

```bash
curl -sS -X POST http://127.0.0.1:9501/robotops.log.LogService/ImportLogPackage \
  -H "Content-Type: application/json" \
  -d '{
    "bug_id":"bug-touch-001",
    "package_id":"pkg-20260730",
    "package_path":"samples/robot_20260730",
    "robot_type":"ROBOT_TYPE_T"
  }'
```

查询 interaction 日志：

```bash
curl -sS -X POST http://127.0.0.1:9501/robotops.log.LogService/QueryLogs \
  -H "Content-Type: application/json" \
  -d '{
    "page":{"page":1,"page_size":10},
    "package_id":"pkg-20260730",
    "module_name":"interaction"
  }'
```

按关键词查询：

```bash
curl -sS -X POST http://127.0.0.1:9501/robotops.log.LogService/QueryLogs \
  -H "Content-Type: application/json" \
  -d '{
    "page":{"page":1,"page_size":10},
    "keyword":"PASSIVE_DEFAULT"
  }'
```

查询日志文件：

```bash
curl -sS -X POST http://127.0.0.1:9501/robotops.log.LogService/ListLogFiles \
  -H "Content-Type: application/json" \
  -d '{
    "package_id":"pkg-20260730"
  }'
```

## 8. 如果编译继续失败

优先检查：

1. `cpp-microservice-kit` 路径是否正确。
2. `protoc` 是否可用。
3. `brpc`、`protobuf`、`jsoncpp` 等脚手架依赖是否完整。
4. `log.pb.h` 是否生成到 `build/generated/proto/`。
5. `cc_generic_services = true` 是否保留。

常用命令：

```bash
which cmake
which protoc
protoc --version
cmake -S . -B build -DCPP_MICROSERVICE_KIT_DIR=<path> --trace-expand
cmake --build build -j1 VERBOSE=1
```

不要绕过 brpc/protobuf 改成普通 HTTP server。当前项目要求继续沿用 dev 环境和脚手架。

## 9. 每个子服务一个阶段

用户要求：

```text
每个子服务算一个阶段开发。
```

因此开发节奏如下：

### 阶段 1：log-service

状态：

```text
已提交初版，但 Linux 编译未验证，需要先修 CMake 路径并完成测试。
```

完成标准：

- Linux 下 CMake 配置成功。
- `log_service` 编译成功。
- 服务能启动。
- `ImportLogPackage` 能导入样例日志。
- `QueryLogs` 能查到 `PASSIVE_DEFAULT`。
- `CHANGES.md` 更新验证结果。
- Git commit + push。

### 阶段 2：ticket-diagnosis-service

目标：

- Bug 单创建。
- 诊断任务创建。
- 调用 agent-service 的接口预留。
- 保存诊断报告 MVP。

### 阶段 3：agent-service

目标：

- Python FastAPI。
- `/health`。
- `/diagnose`。
- 先用规则模板生成结构化诊断报告。
- 后续接 LangGraph。

### 阶段 4：robot-gateway

目标：

- 研发阶段接收日志包导入请求。
- 部署运维阶段预留心跳、状态、事件上报接口。

后续再扩展：

- robot-service
- event-service
- knowledge-service
- source-index-service

## 10. CHANGES 和 Git 要求

每完成一个阶段或修复一次关键构建问题，都必须：

1. 更新 `CHANGES.md`。
2. 说明改了什么、为什么、验证结果、下一步。
3. `git status` 检查。
4. 提交 commit。
5. push 到 GitHub。

commit 示例：

```bash
git add CMakeLists.txt CHANGES.md
git commit -m "fix(build): locate cpp microservice kit in linux"
git push
```

不要使用：

```text
update
misc
changes
```

## 11. 当前建议下一步

Linux Codex 进入后，第一件事不是继续写新服务，而是：

```text
修复 log-service 构建问题并完成阶段 1 验证。
```

推荐顺序：

1. `git pull`
2. 阅读本文件。
3. 查找 `cpp-microservice-kit` 实际路径。
4. 修改顶层 `CMakeLists.txt` 支持可配置脚手架路径。
5. 重新 CMake。
6. 修复编译错误。
7. 启动 `log_service`。
8. 用 curl 验证四个接口。
9. 更新 `CHANGES.md`。
10. commit + push。

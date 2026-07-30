# 数据模型设计

## 1. Bug 单

```sql
CREATE TABLE bug_ticket (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  title VARCHAR(255) NOT NULL,
  description TEXT NOT NULL,
  robot_type VARCHAR(32) NOT NULL,
  main_module VARCHAR(64) NOT NULL,
  occurred_time DATETIME NOT NULL,
  assigned_to VARCHAR(64),
  status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## 2. 日志包

```sql
CREATE TABLE log_package (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  bug_id BIGINT NOT NULL,
  package_name VARCHAR(255) NOT NULL,
  storage_path VARCHAR(512) NOT NULL,
  extract_path VARCHAR(512),
  parse_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (bug_id) REFERENCES bug_ticket(id)
);
```

## 3. 日志文件

```sql
CREATE TABLE log_file (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  package_id BIGINT NOT NULL,
  module_name VARCHAR(64) NOT NULL,
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(512) NOT NULL,
  line_count INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (package_id) REFERENCES log_package(id)
);
```

## 4. Elasticsearch 日志索引

索引名：

```text
robot-module-logs-YYYY.MM
```

字段：

```json
{
  "bug_id": "long",
  "package_id": "long",
  "module_name": "keyword",
  "file_name": "keyword",
  "line_no": "integer",
  "log_time": "date",
  "log_level": "keyword",
  "message": "text",
  "raw_line": "text",
  "trace_id": "keyword",
  "task_id": "keyword",
  "source_file": "keyword"
}
```

## 5. 诊断报告

```sql
CREATE TABLE diagnosis_report (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  bug_id BIGINT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
  suspected_module VARCHAR(64),
  summary TEXT,
  evidence_logs JSON,
  evidence_sources JSON,
  suggestion TEXT,
  confidence DECIMAL(5,2),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (bug_id) REFERENCES bug_ticket(id)
);
```


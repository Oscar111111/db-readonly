<p align="center">
  <img src="assets/logo.svg" width="96" alt="db-readonly logo">
</p>

<h1 align="center">db-readonly</h1>

<p align="center">
  达梦数据库只读 MCP 服务。
</p>

<p align="center">
  <a href="README.md">English</a> |
  <a href="README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/MCP-read--only-blue" alt="MCP read-only">
  <img src="https://img.shields.io/badge/Database-Dameng-orange" alt="Dameng">
  <img src="https://img.shields.io/badge/Python-3.11%2B-green" alt="Python 3.11+">
</p>

## 能做什么

`db-readonly` 用于让 Codex 等 MCP 客户端通过受控方式只读查询达梦数据库。

支持：

- 列出已配置的数据源。
- 根据 Java 风格实体名推断表名。
- 查看表字段和字段类型。
- 查询指定表的指定字段。
- 执行受限制的 `SELECT` 查询。

不支持：

- 执行 `INSERT`、`UPDATE`、`DELETE`、`CREATE`、`ALTER`、`DROP`。
- 执行 `SELECT *`。
- 查询未配置的 schema。
- 在 YAML 配置里保存数据库密码。

## 快速开始

### 1. 安装

```powershell
cd path\to\db-readonly
.\setup.ps1
```

### 2. 配置数据源

复制配置模板：

```powershell
Copy-Item config.example.yaml config.local.yaml
```

修改 `config.local.yaml`：

```yaml
datasources:
  dm-dev:
    project: "your-project"
    env: "dev"
    description: "Dev Dameng database"
    driver: "DM8 ODBC DRIVER"
    host: "127.0.0.1"
    port: 5236
    schema: "YOUR_SCHEMA"
    username: "READONLY_USER"
    passwordEnv: "DM_READONLY_PASSWORD"
    maxRows: 100
    queryTimeoutSeconds: 10
    allowTables: ["*"]
    denyTables: []
```

### 3. 配置密码

不要把密码写进 `config.local.yaml`。

```powershell
[Environment]::SetEnvironmentVariable("DM_READONLY_PASSWORD", "your_password", "User")
```

设置后重启终端或 MCP 客户端。

### 4. 启动

```powershell
.\run.ps1
```

### 5. 验证

```powershell
.\.venv\Scripts\python.exe scripts\verify.py
.\.venv\Scripts\python.exe scripts\check_db_connection.py
```

## Codex MCP 配置

在 Codex 配置中加入：

```toml
[mcp_servers.db-readonly]
command = "powershell.exe"
args = ["-ExecutionPolicy", "Bypass", "-File", "C:\\path\\to\\db-readonly\\run.ps1"]
```

修改后重启 Codex。

## MCP 工具

- `datasource_list`
- `entity_resolve`
- `entity_describe`
- `entity_query`
- `table_describe`
- `table_query`
- `sql_query`

## 安全限制

- 数据源必须显式配置。
- 查询范围限制在 datasource 对应的 schema。
- 返回行数由 `maxRows` 限制。
- SQL 执行前会做只读校验。
- 数据库密码只从环境变量读取。

建议数据库账号本身也只授只读权限。

<p align="center">
  <img src="assets/logo.svg" width="96" alt="db-readonly logo">
</p>

<h1 align="center">db-readonly</h1>

<p align="center">
  Read-only MCP server for Dameng databases.
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

## What It Does

`db-readonly` lets MCP clients such as Codex query Dameng databases through a controlled read-only interface.

It can:

- List configured datasources.
- Resolve Java-style entity names to table names.
- Describe table columns.
- Query selected columns from selected tables.
- Run guarded `SELECT` statements.

It cannot:

- Run `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, or `DROP`.
- Run `SELECT *`.
- Query schemas that are not configured.
- Store database passwords in the YAML config.

## Quick Start

### 1. Install

```powershell
cd path\to\db-readonly
.\setup.ps1
```

### 2. Configure A Datasource

Copy the example config:

```powershell
Copy-Item config.example.yaml config.local.yaml
```

Edit `config.local.yaml`:

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

### 3. Set The Password

Do not write passwords into `config.local.yaml`.

```powershell
[Environment]::SetEnvironmentVariable("DM_READONLY_PASSWORD", "your_password", "User")
```

Restart your terminal or MCP client after setting the environment variable.

### 4. Run

```powershell
.\run.ps1
```

### 5. Verify

```powershell
.\.venv\Scripts\python.exe scripts\verify.py
.\.venv\Scripts\python.exe scripts\check_db_connection.py
```

## Codex MCP Config

Add this to your Codex config:

```toml
[mcp_servers.db-readonly]
command = "powershell.exe"
args = ["-ExecutionPolicy", "Bypass", "-File", "C:\\path\\to\\db-readonly\\run.ps1"]
```

Restart Codex after changing the config.

## Available Tools

- `datasource_list`
- `entity_resolve`
- `entity_describe`
- `entity_query`
- `table_describe`
- `table_query`
- `sql_query`

## Safety Model

- Datasources must be configured explicitly.
- Queries are limited to the configured schema.
- Returned rows are capped by `maxRows`.
- SQL is guarded before execution.
- Database passwords are read from environment variables.

Use a database account with read-only permissions.

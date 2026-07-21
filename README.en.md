<p align="center">
  <img src="assets/logo.svg" width="96" alt="db-readonly logo">
</p>

<h1 align="center">db-readonly</h1>

<p align="center">
  Read-only MCP server for Dameng and MySQL databases.
</p>

<p align="center">
  <a href="README.md">简体中文</a> |
  <a href="README.en.md">English</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/MCP-read--only-blue" alt="MCP read-only">
  <img src="https://img.shields.io/badge/Database-Dameng%20%7C%20MySQL-orange" alt="Database">
  <img src="https://img.shields.io/badge/Python-3.11%2B-green" alt="Python 3.11+">
</p>

## What It Does

`db-readonly` lets MCP clients such as Codex query databases through a controlled read-only interface.

It can:

- List configured datasources.
- Describe table columns.
- Query selected columns from selected tables.
- Run guarded `SELECT` statements.
- Resolve Java-style entity names for Dameng datasources.

It cannot:

- Run `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `ALTER`, or `DROP`.
- Run `SELECT *`.
- Query schemas or databases that are not configured.
- Store database passwords in the YAML config.
- Resolve MySQL entity mappings in the first MySQL version.

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

Dameng example:

```yaml
datasources:
  dm-dev:
    dbType: "dm"
    project: "your-project"
    env: "dev"
    description: "Development Dameng database"
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

MySQL example:

```yaml
datasources:
  mysql-dev:
    dbType: "mysql"
    project: "your-project"
    env: "dev"
    description: "Development MySQL database"
    driver: "MySQL ODBC 8.0 Unicode Driver"
    host: "127.0.0.1"
    port: 3306
    schema: "your_database"
    username: "readonly_user"
    passwordEnv: "MYSQL_READONLY_PASSWORD"
    maxRows: 100
    queryTimeoutSeconds: 10
    allowTables: ["*"]
    denyTables: []
```

MySQL users must install MySQL Connector/ODBC first:

https://dev.mysql.com/downloads/connector/odbc/

Run this command to find the exact local driver name:

```powershell
.\setup.ps1 -Drivers
```

### 3. Set The Password

Do not write passwords into `config.local.yaml`.

```powershell
[Environment]::SetEnvironmentVariable("MYSQL_READONLY_PASSWORD", "your_password", "User")
```

Restart your terminal or MCP client after setting the environment variable.

### 4. Verify

```powershell
.\.venv\Scripts\python.exe scripts\verify.py
.\.venv\Scripts\python.exe scripts\check_db_connection.py
```

## Codex MCP Config

```toml
[mcp_servers.db-readonly]
command = "powershell.exe"
args = ["-ExecutionPolicy", "Bypass", "-File", "C:\\path\\to\\db-readonly\\run.ps1"]
```

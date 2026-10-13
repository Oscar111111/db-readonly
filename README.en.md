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

## Optional Model Package Mapping (Dameng)

Add `mappingDir` to the datasource that needs low-code model mappings; keep its existing connection settings:

```yaml
datasources:
  tfqd-dev:
    project: "km-mom-tfqd"
    mappingDir: "mapping_packages/km-mom-tfqd"
```

- Paths are relative to the YAML file. Keep exactly one current ZIP in each directory; no extraction or version-specific filename in the config is needed. Use separate directories when environments run different versions.
- The first entity-tool call reads `models/*.dm.json` and caches mappings in the MCP process. Restart MCP after replacing or adding a package, including when the directory was previously empty.
- JSON must contain a `DATA` array. Only the datasource's `mappingDir` selects the ZIP; its `APP` is not compared with `project`. `entity_resolve` reports the package name, version and `mappingApps` (application codes). A package placed in the wrong directory is not automatically detected.
- No configured directory, a missing directory, or no ZIP preserves legacy `entityOverrides` and `MOM_` inference. A valid package takes priority; invalid or multiple packages, unknown entities and ambiguous names fail explicitly.
- Entity codes and exact Chinese names resolve to `CTABLE_NAME`; property codes/names resolve to `CCOLUMN_NAME`. Inherited properties are included when the parent model is in the package. Virtual properties without physical columns cannot be queried.
- An illegal physical field affects only that property: it is recorded as an invalid mapping, other entities and properties remain usable, and requesting it fails explicitly instead of guessing a column.
- Properties with `CDATA_TYPE` `REFERENCE_OBJECT`, `USER`, or `BIZ_ORG` treat `CCOLUMN_NAME` as a prefix and expand it to `<prefix>_ID` and `<prefix>_ENTITY_TYPE`, removing an existing suffix first (for example, `creator` becomes `CCREATOR_ID` and `CCREATOR_ENTITY_TYPE`, while child-table `source` becomes `CSOURCE_ID` and `CSOURCE_ENTITY_TYPE`).
- `entity_resolve` checks that the table exists and reports property mappings: `column` preserves the package value, `columns` lists queryable physical columns, and `error` identifies an invalid field. `entity_describe` returns real DB columns with `PROPERTY_CODE` / `PROPERTY_NAME` metadata; both reference columns map to the same property.
- `entity_query.columns` accepts logical codes, exact property names or physical columns. Results keep physical DB column names. `where`, `table_query` and `sql_query` still use physical identifiers; arbitrary SQL is not rewritten.
- Only `entity_*` tools use logical model mappings. `table_describe`, `table_query` and `sql_query` always use real table and column names.
- Model versions do not prove DB deployment versions. Check actual tables and columns first. `mapping_packages/` is git-ignored; do not publish internal installation packages.

## Codex MCP Config

```toml
[mcp_servers.db-readonly]
command = "powershell.exe"
args = ["-ExecutionPolicy", "Bypass", "-File", "C:\\path\\to\\db-readonly\\run.ps1"]
```

from __future__ import annotations

import re
from fnmatch import fnmatchcase

import sqlparse

from dm_db_readonly.settings import DataSourceConfig


class SqlGuardError(ValueError):
    pass


def ensure_table_allowed(table: str, datasource: DataSourceConfig) -> str:
    table_name = validate_table_name(table)
    allow_rules = datasource.allow_tables or ["*"]
    deny_rules = datasource.deny_tables or []

    if not any(_match_table_rule(table_name, rule) for rule in allow_rules):
        raise SqlGuardError(f"表不在允许规则内：{table_name}")

    if any(_match_table_rule(table_name, rule) for rule in deny_rules):
        raise SqlGuardError(f"表命中禁查规则：{table_name}")

    return table_name


def ensure_safe_select(sql: str, datasource: DataSourceConfig) -> str:
    normalized = sql.strip().rstrip(";")
    statements = [statement for statement in sqlparse.parse(normalized) if statement.tokens]
    if len(statements) != 1:
        raise SqlGuardError("只允许执行单条 SQL")

    statement_type = statements[0].get_type().upper()
    if statement_type != "SELECT":
        raise SqlGuardError("只允许执行 SELECT 查询")

    upper_sql = normalized.upper()
    if re.search(r"\bSELECT\s+\*", upper_sql):
        raise SqlGuardError("禁止 SELECT *，请显式指定字段")

    if ";" in normalized:
        raise SqlGuardError("SQL 中不能包含分号")

    schema = re.escape(datasource.schema.upper())
    if not re.search(rf"\b{schema}\.", upper_sql):
        raise SqlGuardError(f"查询必须显式限定 schema：{datasource.schema}")

    forbidden_keywords = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "CREATE",
        "ALTER",
        "DROP",
        "TRUNCATE",
        "CALL",
        "EXEC",
    ]
    for keyword in forbidden_keywords:
        if re.search(rf"\b{keyword}\b", upper_sql):
            raise SqlGuardError(f"禁止使用关键字：{keyword}")

    return append_limit(normalized, datasource.max_rows)


def append_limit(sql: str, max_rows: int) -> str:
    upper_sql = sql.upper()
    if re.search(r"\bLIMIT\s+\d+\b", upper_sql) or re.search(r"\bFETCH\s+FIRST\s+\d+\s+ROWS\b", upper_sql):
        return sql
    return f"{sql} FETCH FIRST {max_rows} ROWS ONLY"


def validate_table_name(table: str) -> str:
    value = table.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
        raise SqlGuardError("表名只能包含大写字母、数字和下划线")
    return value


def _match_table_rule(table: str, rule: str) -> bool:
    return fnmatchcase(table.upper(), rule.strip().upper())


def validate_columns(columns: list[str]) -> list[str]:
    if not columns:
        raise SqlGuardError("必须指定查询字段，禁止隐式 SELECT *")
    result: list[str] = []
    for column in columns:
        value = column.strip().upper()
        if value == "*":
            raise SqlGuardError("禁止 SELECT *")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
            raise SqlGuardError(f"非法字段名：{column}")
        result.append(value)
    return result

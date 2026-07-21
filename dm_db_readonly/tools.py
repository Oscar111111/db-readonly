from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from dm_db_readonly.datasource import DataSource
from dm_db_readonly.entity_resolver import entity_type_to_table
from dm_db_readonly.settings import load_config
from dm_db_readonly.sql_guard import ensure_safe_select, ensure_table_allowed, validate_columns


mcp = FastMCP("dm-db-readonly")


def _config():
    return load_config()


def _datasource(name: str) -> DataSource:
    config = _config()
    if name not in config.datasources:
        raise ValueError(f"未知 datasource：{name}")
    return DataSource(config.datasources[name])


def _entity_table(datasource: str, entity_type: str) -> str:
    config = _config()
    return entity_type_to_table(entity_type, config.entity_overrides)


@mcp.tool()
def datasource_list() -> list[dict[str, object]]:
    """List configured datasources without exposing passwords."""
    config = _config()
    return [
        {
            "name": datasource.name,
            "project": datasource.project,
            "env": datasource.env,
            "schema": datasource.schema,
            "description": datasource.description,
        }
        for datasource in config.datasources.values()
    ]


@mcp.tool()
def entity_resolve(datasource: str, entityType: str) -> dict[str, object]:
    """Resolve an entityType to its inferred MOM table name."""
    ds = _datasource(datasource)
    _ensure_entity_supported(ds)
    table = _entity_table(datasource, entityType)
    table_name = ensure_table_allowed(table, ds.config)
    return {
        "datasource": datasource,
        "schema": ds.config.schema,
        "entityType": entityType,
        "table": table_name,
        "exists": ds.table_exists(table_name),
    }


@mcp.tool()
def entity_describe(datasource: str, entityType: str) -> list[dict[str, object]]:
    """Describe columns of the table inferred from an entityType."""
    ds = _datasource(datasource)
    _ensure_entity_supported(ds)
    table = _entity_table(datasource, entityType)
    table_name = ensure_table_allowed(table, ds.config)
    return ds.describe_table(table_name)


@mcp.tool()
def entity_query(datasource: str, entityType: str, columns: list[str], where: str = "", limit: int = 100) -> list[dict[str, object]]:
    """Query rows by entityType using explicit columns and optional where clause."""
    ds = _datasource(datasource)
    _ensure_entity_supported(ds)
    sql = build_entity_query_sql(ds, entityType, columns, where, limit, _config().entity_overrides)
    return ds.query(sql)


@mcp.tool()
def table_describe(datasource: str, table: str) -> list[dict[str, object]]:
    """Describe columns of a real table name."""
    ds = _datasource(datasource)
    table_name = ensure_table_allowed(table, ds.config)
    return ds.describe_table(table_name)


@mcp.tool()
def table_query(datasource: str, table: str, columns: list[str], where: str = "", limit: int = 100) -> list[dict[str, object]]:
    """Query a real table name using explicit columns and optional where clause."""
    ds = _datasource(datasource)
    sql = build_table_query_sql(ds, table, columns, where, limit)
    return ds.query(sql)


@mcp.tool()
def sql_query(datasource: str, sql: str) -> list[dict[str, object]]:
    """Run a guarded SELECT SQL query against a configured datasource."""
    ds = _datasource(datasource)
    safe_sql = ensure_safe_select(sql, ds.config)
    return ds.query(safe_sql)


def build_entity_query_sql(
    ds: DataSource,
    entityType: str,
    columns: list[str],
    where: str = "",
    limit: int = 100,
    entity_overrides: dict[str, str] | None = None,
) -> str:
    _ensure_entity_supported(ds)
    table = ensure_table_allowed(entity_type_to_table(entityType, entity_overrides), ds.config)
    selected_columns = validate_columns(columns, ds.config.db_type)
    row_limit = max(1, min(int(limit), ds.config.max_rows))
    sql = f"SELECT {', '.join(selected_columns)} FROM {ds.config.schema}.{table}"
    if where:
        sql += f" WHERE {where}"
    sql += f" FETCH FIRST {row_limit} ROWS ONLY"
    return ensure_safe_select(sql, ds.config)


def build_table_query_sql(ds: DataSource, table: str, columns: list[str], where: str = "", limit: int = 100) -> str:
    table_name = ensure_table_allowed(table, ds.config)
    selected_columns = validate_columns(columns, ds.config.db_type)
    row_limit = max(1, min(int(limit), ds.config.max_rows))
    if ds.config.db_type == "mysql":
        sql = f"SELECT {', '.join(_quote_mysql_identifier(column) for column in selected_columns)} FROM {_quote_mysql_identifier(ds.config.schema)}.{_quote_mysql_identifier(table_name)}"
    else:
        sql = f"SELECT {', '.join(selected_columns)} FROM {ds.config.schema}.{table_name}"
    if where:
        sql += f" WHERE {where}"
    sql += f" LIMIT {row_limit}" if ds.config.db_type == "mysql" else f" FETCH FIRST {row_limit} ROWS ONLY"
    return ensure_safe_select(sql, ds.config)


def _ensure_entity_supported(ds: DataSource) -> None:
    if ds.config.db_type == "mysql":
        raise ValueError("MySQL datasource 暂不支持 entity 映射，请使用 table_describe/table_query/sql_query")


def _quote_mysql_identifier(identifier: str) -> str:
    return f"`{identifier}`"


def main() -> None:
    mcp.run()

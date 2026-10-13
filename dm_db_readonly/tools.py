from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from dm_db_readonly.datasource import DataSource
from dm_db_readonly.entity_resolver import entity_type_to_table
from dm_db_readonly.model_mapping import load_model_mapping
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


def _resolve_entity(ds: DataSource, entity_type: str, overrides: dict[str, str] | None = None):
    _ensure_entity_supported(ds)
    mapping = load_model_mapping(ds.config.mapping_dir)
    if mapping is not None:
        entity = mapping.resolve(entity_type)
        return ensure_table_allowed(entity["CTABLE_NAME"], ds.config), mapping, entity
    return ensure_table_allowed(entity_type_to_table(entity_type, overrides), ds.config), None, None


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
    """Resolve an entity code or exact Chinese name using the datasource's model ZIP; otherwise use MOM rules."""
    ds = _datasource(datasource)
    table_name, mapping, entity = _resolve_entity(ds, entityType, _config().entity_overrides)
    result = {
        "datasource": datasource,
        "schema": ds.config.schema,
        "entityType": entityType,
        "table": table_name,
        "exists": ds.table_exists(table_name),
    }
    if mapping is not None:
        result.update({
            "entityType": entity["CCODE"],
            "entityName": entity.get("CNAME"),
            "mappingSource": "package",
            "mappingPackage": mapping.package.name,
            "mappingVersion": mapping.version,
            "mappingApps": mapping.apps,
            "properties": [
                {
                    "code": prop["CCODE"],
                    "name": prop.get("CNAME"),
                    "dataType": prop.get("CDATA_TYPE"),
                    "referenceType": prop.get("CREFERENCE_TYPE"),
                    "column": prop.get("CCOLUMN_NAME"),
                    "columns": _mapping_property_columns(mapping, entity, prop),
                    "error": mapping.property_errors(entity).get(prop["CCODE"]),
                }
                for prop in mapping.properties(entity)
            ],
        })
    return result


@mcp.tool()
def entity_describe(datasource: str, entityType: str) -> list[dict[str, object]]:
    """Describe real DB columns; include PROPERTY_CODE/PROPERTY_NAME when a model ZIP supplies mappings."""
    ds = _datasource(datasource)
    table_name, mapping, entity = _resolve_entity(ds, entityType, _config().entity_overrides)
    columns = ds.describe_table(table_name)
    if mapping is not None:
        props = {}
        for prop in mapping.properties(entity):
            for physical_column in _mapping_property_columns(mapping, entity, prop):
                props[physical_column.upper()] = prop
        for column in columns:
            prop = props.get(str(column.get("COLUMN_NAME", "")).upper())
            if prop:
                column.update({
                    "PROPERTY_CODE": prop["CCODE"],
                    "PROPERTY_NAME": prop.get("CNAME"),
                })
    return columns


@mcp.tool()
def entity_query(datasource: str, entityType: str, columns: list[str], where: str = "", limit: int = 100) -> list[dict[str, object]]:
    """Query explicit columns by entity code/name. ZIP reference properties expand to ID/type columns; where uses real DB columns."""
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
    table, mapping, entity = _resolve_entity(ds, entityType, entity_overrides)
    selected_columns = (
        [physical for column in columns for physical in mapping.columns(entity, column)]
        if mapping else columns
    )
    return build_table_query_sql(ds, table, selected_columns, where, limit)


def _mapping_property_columns(mapping, entity, prop) -> list[str]:
    if not prop.get("CCOLUMN_NAME") or prop["CCODE"] in mapping.property_errors(entity):
        return []
    return mapping.columns(entity, prop["CCODE"])


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

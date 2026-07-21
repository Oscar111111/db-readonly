from __future__ import annotations

from dm_db_readonly import tools as tools_module


class DummyDataSource:
    def __init__(self, max_rows: int = 100, db_type: str = "dm", schema: str = "MOM_INS"):
        self.config = type(
            "Config",
            (),
            {
                "schema": schema,
                "db_type": db_type,
                "max_rows": max_rows,
                "allow_tables": ["*"],
                "deny_tables": [],
            },
        )()
        self.queries: list[str] = []

    def describe_table(self, table: str) -> list[dict[str, object]]:
        return [{"TABLE": table}]

    def table_exists(self, table: str) -> bool:
        return True

    def query(self, sql: str) -> list[dict[str, object]]:
        self.queries.append(sql)
        return [{"SQL": sql}]


def test_datasource_list_returns_fixed_shape(monkeypatch):
    monkeypatch.setenv("MOM_INS_RO_PASSWORD", "dummy-password")
    items = tools_module.datasource_list()
    assert items
    first = items[0]
    assert set(first.keys()) == {"name", "project", "env", "schema", "description"}


def test_table_query_limit_is_at_least_one():
    datasource = DummyDataSource()
    sql = tools_module.build_table_query_sql(datasource, "MOM_INVENTORY", ["CID"], limit=0)
    assert sql.endswith("FETCH FIRST 1 ROWS ONLY")


def test_table_query_limit_is_capped_by_max_rows():
    datasource = DummyDataSource(max_rows=10)
    sql = tools_module.build_table_query_sql(datasource, "MOM_INVENTORY", ["CID"], limit=100)
    assert sql.endswith("FETCH FIRST 10 ROWS ONLY")


def test_mysql_table_query_uses_backticks_and_limit():
    datasource = DummyDataSource(max_rows=10, db_type="mysql", schema="app_db")
    sql = tools_module.build_table_query_sql(datasource, "orders", ["id", "order_no"], limit=100)
    assert sql == "SELECT `id`, `order_no` FROM `app_db`.`orders` LIMIT 10"


def test_mysql_entity_query_is_not_supported():
    datasource = DummyDataSource(db_type="mysql", schema="app_db")
    try:
        tools_module.build_entity_query_sql(datasource, "Order", ["id"])
    except ValueError as error:
        assert "MySQL datasource 暂不支持 entity 映射" in str(error)
    else:
        raise AssertionError("Expected MySQL entity query to be rejected")

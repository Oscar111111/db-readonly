from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dm_db_readonly.entity_resolver import entity_type_to_table
from dm_db_readonly.settings import DataSourceConfig
from dm_db_readonly.sql_guard import SqlGuardError, ensure_safe_select, ensure_table_allowed, validate_columns


def datasource() -> DataSourceConfig:
    return DataSourceConfig(
        name="test",
        project="km-mom-next",
        env="test",
        description="test datasource",
        driver="DM8 ODBC DRIVER",
        host="127.0.0.1",
        port=5236,
        schema="MOM_INS",
        username="MOM_INS_RO",
        password_env="MOM_INS_RO_PASSWORD",
        max_rows=100,
        query_timeout_seconds=10,
        allow_tables=["*"],
        deny_tables=[],
    )


def mysql_datasource() -> DataSourceConfig:
    return DataSourceConfig(
        name="mysql-dev",
        project="other-project",
        env="dev",
        description="mysql datasource",
        driver="MySQL ODBC 8.0 Unicode Driver",
        host="127.0.0.1",
        port=3306,
        schema="app_db",
        username="readonly_user",
        password_env="MYSQL_READONLY_PASSWORD",
        max_rows=50,
        query_timeout_seconds=10,
        allow_tables=["*"],
        deny_tables=[],
        db_type="mysql",
    )


def assert_raises(error_type, func, *args):
    try:
        func(*args)
    except error_type:
        return
    raise AssertionError(f"Expected {error_type.__name__}")


def main() -> None:
    assert entity_type_to_table("Inventory") == "MOM_INVENTORY"
    assert entity_type_to_table("InventoryBatchAttribute") == "MOM_INVENTORY_BATCH_ATTRIBUTE"
    assert entity_type_to_table("SpecialEntity", {"SpecialEntity": "MOM_CUSTOM"}) == "MOM_CUSTOM"

    ds = datasource()
    safe_sql = ensure_safe_select("SELECT CID FROM MOM_INS.MOM_INVENTORY", ds)
    assert safe_sql.endswith("FETCH FIRST 100 ROWS ONLY")

    assert_raises(SqlGuardError, ensure_safe_select, "UPDATE MOM_INS.MOM_INVENTORY SET CQTY = 1", ds)
    assert_raises(SqlGuardError, ensure_safe_select, "SELECT * FROM MOM_INS.MOM_INVENTORY", ds)
    assert_raises(SqlGuardError, ensure_safe_select, "SELECT CID FROM OTHER.MOM_INVENTORY", ds)
    assert_raises(SqlGuardError, validate_columns, ["*"])

    assert ensure_table_allowed("MOM_INVENTORY", ds) == "MOM_INVENTORY"
    mysql_ds = mysql_datasource()
    mysql_sql = ensure_safe_select("SELECT id, order_no FROM app_db.orders", mysql_ds)
    assert mysql_sql == "SELECT id, order_no FROM app_db.orders LIMIT 50"
    assert ensure_table_allowed("orders", mysql_ds) == "orders"
    assert validate_columns(["id", "order_no"], "mysql") == ["id", "order_no"]

    denied_ds = DataSourceConfig(
        name="test",
        project="km-mom-next",
        env="test",
        description="test datasource",
        driver="DM8 ODBC DRIVER",
        host="127.0.0.1",
        port=5236,
        schema="MOM_INS",
        username="MOM_INS_RO",
        password_env="MOM_INS_RO_PASSWORD",
        max_rows=100,
        query_timeout_seconds=10,
        allow_tables=["*"],
        deny_tables=["MOM_SECRET_*"],
    )
    assert_raises(SqlGuardError, ensure_table_allowed, "MOM_SECRET_TOKEN", denied_ds)

    print("verify passed")


if __name__ == "__main__":
    main()

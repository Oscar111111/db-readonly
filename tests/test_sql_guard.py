import pytest

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


def test_guard_allows_schema_select_and_adds_limit():
    sql = ensure_safe_select("SELECT CID FROM MOM_INS.MOM_INVENTORY", datasource())
    assert sql.endswith("FETCH FIRST 100 ROWS ONLY")


def test_guard_rejects_update():
    with pytest.raises(SqlGuardError):
        ensure_safe_select("UPDATE MOM_INS.MOM_INVENTORY SET CQTY = 1", datasource())


def test_guard_rejects_select_star():
    with pytest.raises(SqlGuardError):
        ensure_safe_select("SELECT * FROM MOM_INS.MOM_INVENTORY", datasource())


def test_guard_rejects_other_schema():
    with pytest.raises(SqlGuardError):
        ensure_safe_select("SELECT CID FROM OTHER.MOM_INVENTORY", datasource())


def test_validate_columns_rejects_star():
    with pytest.raises(SqlGuardError):
        validate_columns(["*"])


def test_table_rules_allow_star():
    assert ensure_table_allowed("MOM_INVENTORY", datasource()) == "MOM_INVENTORY"


def test_table_rules_deny_takes_priority():
    config = datasource()
    config = DataSourceConfig(
        name=config.name,
        project=config.project,
        env=config.env,
        description=config.description,
        driver=config.driver,
        host=config.host,
        port=config.port,
        schema=config.schema,
        username=config.username,
        password_env=config.password_env,
        max_rows=config.max_rows,
        query_timeout_seconds=config.query_timeout_seconds,
        allow_tables=["*"],
        deny_tables=["MOM_SECRET_*"],
    )
    with pytest.raises(SqlGuardError):
        ensure_table_allowed("MOM_SECRET_TOKEN", config)

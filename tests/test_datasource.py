from dm_db_readonly.datasource import DataSource
from dm_db_readonly.settings import DataSourceConfig


def config(db_type: str = "dm") -> DataSourceConfig:
    return DataSourceConfig(
        name="test",
        project="project",
        env="dev",
        description="test datasource",
        driver="DM8 ODBC DRIVER" if db_type == "dm" else "MySQL ODBC 8.0 Unicode Driver",
        host="127.0.0.1",
        port=5236 if db_type == "dm" else 3306,
        schema="MOM_INS" if db_type == "dm" else "app_db",
        username="readonly_user",
        password_env="TEST_DB_PASSWORD",
        max_rows=100,
        query_timeout_seconds=10,
        allow_tables=["*"],
        deny_tables=[],
        db_type=db_type,
    )


def test_dm_connection_string_uses_tcp_port(monkeypatch):
    monkeypatch.setenv("TEST_DB_PASSWORD", "secret")
    connection_string = DataSource(config())._connection_string()
    assert "TCP_PORT=5236;" in connection_string
    assert ";PORT=5236;" not in connection_string


def test_mysql_connection_string_uses_database_and_port(monkeypatch):
    monkeypatch.setenv("TEST_DB_PASSWORD", "secret")
    connection_string = DataSource(config("mysql"))._connection_string()
    assert "PORT=3306;" in connection_string
    assert "DATABASE=app_db;" in connection_string

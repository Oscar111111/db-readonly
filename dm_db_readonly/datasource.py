from __future__ import annotations

import pyodbc

from dm_db_readonly.settings import DataSourceConfig


class DataSource:
    def __init__(self, config: DataSourceConfig):
        self.config = config

    def connect(self) -> pyodbc.Connection:
        connection_string = (
            f"DRIVER={{{self.config.driver}}};"
            f"SERVER={self.config.host};"
            f"TCP_PORT={self.config.port};"
            f"UID={self.config.username};"
            f"PWD={self.config.password};"
        )
        connection = pyodbc.connect(connection_string, timeout=self.config.query_timeout_seconds)
        connection.timeout = self.config.query_timeout_seconds
        return connection

    def query(self, sql: str) -> list[dict[str, object]]:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(sql)
            columns = [column[0] for column in cursor.description or []]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def describe_table(self, table: str) -> list[dict[str, object]]:
        sql = (
            "SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE "
            "FROM ALL_TAB_COLUMNS "
            f"WHERE OWNER = '{self.config.schema}' AND TABLE_NAME = '{table}' "
            "ORDER BY COLUMN_ID"
        )
        return self.query(sql)

    def table_exists(self, table: str) -> bool:
        sql = (
            "SELECT TABLE_NAME "
            "FROM ALL_TABLES "
            f"WHERE OWNER = '{self.config.schema}' AND TABLE_NAME = '{table}' "
            "FETCH FIRST 1 ROWS ONLY"
        )
        return bool(self.query(sql))

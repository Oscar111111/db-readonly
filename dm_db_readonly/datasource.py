from __future__ import annotations

import pyodbc

from dm_db_readonly.settings import DataSourceConfig


class DataSource:
    def __init__(self, config: DataSourceConfig):
        self.config = config

    def connect(self) -> pyodbc.Connection:
        connection_string = self._connection_string()
        connection = pyodbc.connect(connection_string, timeout=self.config.query_timeout_seconds)
        connection.timeout = self.config.query_timeout_seconds
        return connection

    def _connection_string(self) -> str:
        if self.config.db_type == "mysql":
            return (
                f"DRIVER={{{self.config.driver}}};"
                f"SERVER={self.config.host};"
                f"PORT={self.config.port};"
                f"DATABASE={self.config.schema};"
                f"UID={self.config.username};"
                f"PWD={self.config.password};"
            )
        return (
            f"DRIVER={{{self.config.driver}}};"
            f"SERVER={self.config.host};"
            f"TCP_PORT={self.config.port};"
            f"UID={self.config.username};"
            f"PWD={self.config.password};"
        )

    def query(self, sql: str) -> list[dict[str, object]]:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(sql)
            columns = [column[0] for column in cursor.description or []]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def describe_table(self, table: str) -> list[dict[str, object]]:
        if self.config.db_type == "mysql":
            sql = (
                "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH AS DATA_LENGTH, IS_NULLABLE AS NULLABLE "
                "FROM information_schema.columns "
                f"WHERE TABLE_SCHEMA = '{_escape_sql_literal(self.config.schema)}' AND TABLE_NAME = '{_escape_sql_literal(table)}' "
                "ORDER BY ORDINAL_POSITION"
            )
            return self.query(sql)
        sql = (
            "SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE "
            "FROM ALL_TAB_COLUMNS "
            f"WHERE OWNER = '{self.config.schema}' AND TABLE_NAME = '{table}' "
            "ORDER BY COLUMN_ID"
        )
        return self.query(sql)

    def table_exists(self, table: str) -> bool:
        if self.config.db_type == "mysql":
            sql = (
                "SELECT TABLE_NAME "
                "FROM information_schema.tables "
                f"WHERE TABLE_SCHEMA = '{_escape_sql_literal(self.config.schema)}' AND TABLE_NAME = '{_escape_sql_literal(table)}' "
                "LIMIT 1"
            )
            return bool(self.query(sql))
        sql = (
            "SELECT TABLE_NAME "
            "FROM ALL_TABLES "
            f"WHERE OWNER = '{self.config.schema}' AND TABLE_NAME = '{table}' "
            "FETCH FIRST 1 ROWS ONLY"
        )
        return bool(self.query(sql))


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")

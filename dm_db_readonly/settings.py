from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows fallback
    winreg = None


@dataclass(frozen=True)
class DataSourceConfig:
    name: str
    project: str
    env: str
    description: str
    driver: str
    host: str
    port: int
    schema: str
    username: str
    password_env: str
    max_rows: int
    query_timeout_seconds: int
    allow_tables: list[str]
    deny_tables: list[str]
    db_type: str = "dm"

    @property
    def password(self) -> str:
        value = os.getenv(self.password_env)
        if value:
            return value

        value = _read_windows_environment(self.password_env, "User")
        if value:
            return value

        value = _read_windows_environment(self.password_env, "Machine")
        if not value:
            raise ValueError(f"环境变量 {self.password_env} 未设置")
        return value


@dataclass(frozen=True)
class AppConfig:
    datasources: dict[str, DataSourceConfig]
    entity_overrides: dict[str, str]


def load_config(path: str | Path = "config.local.yaml") -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        config_path = Path("config.example.yaml")

    with config_path.open("r", encoding="utf-8") as file:
        raw: dict[str, Any] = yaml.safe_load(file) or {}

    datasources: dict[str, DataSourceConfig] = {}
    for name, item in (raw.get("datasources") or {}).items():
        db_type = str(item.get("dbType", "dm")).lower()
        if db_type not in {"dm", "mysql"}:
            raise ValueError(f"不支持的 dbType：{db_type}")
        schema = str(item["schema"])
        datasources[name] = DataSourceConfig(
            name=name,
            project=str(item["project"]),
            env=str(item["env"]),
            description=str(item.get("description", name)),
            driver=item["driver"],
            host=item["host"],
            port=int(item.get("port", 5236)),
            schema=schema.upper() if db_type == "dm" else schema,
            username=item["username"],
            password_env=item["passwordEnv"],
            max_rows=int(item.get("maxRows", 100)),
            query_timeout_seconds=int(item.get("queryTimeoutSeconds", 10)),
            allow_tables=_normalize_table_rules(item.get("allowTables", ["*"]), db_type),
            deny_tables=_normalize_table_rules(item.get("denyTables", []), db_type),
            db_type=db_type,
        )

    return AppConfig(
        datasources=datasources,
        entity_overrides={key: value for key, value in (raw.get("entityOverrides") or {}).items()},
    )


def _read_windows_environment(name: str, scope: str) -> str | None:
    if winreg is None:
        return None

    key_path = r"Environment" if scope == "User" else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    root = winreg.HKEY_CURRENT_USER if scope == "User" else winreg.HKEY_LOCAL_MACHINE
    try:
        with winreg.OpenKey(root, key_path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except OSError:
        return None


def _normalize_table_rules(values: list[object], db_type: str) -> list[str]:
    rules = [str(value) for value in values]
    if db_type == "dm":
        return [rule.upper() for rule in rules]
    return rules

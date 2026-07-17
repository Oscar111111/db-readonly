from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dm_db_readonly.datasource import DataSource
from dm_db_readonly.settings import AppConfig, DataSourceConfig, load_config


def check_datasource(config: DataSourceConfig) -> bool:
    print(f"[{config.name}] {config.description}")
    print(f"  host={config.host} port={config.port} schema={config.schema} user={config.username}")
    try:
        # Accessing password validates the configured environment variable early.
        _ = config.password
        datasource = DataSource(config)
        sql = (
            "SELECT COUNT(*) AS TABLE_COUNT "
            "FROM ALL_TABLES "
            f"WHERE OWNER = '{config.schema}'"
        )
        result = datasource.query(sql)
        table_count = result[0].get("TABLE_COUNT") if result else None
        print(f"  OK: connected, table_count={table_count}")
        return True
    except Exception as error:
        print(f"  ERROR: {type(error).__name__}: {error}")
        return False


def select_datasources(app_config: AppConfig, args: list[str]) -> list[DataSourceConfig]:
    if not args:
        return list(app_config.datasources.values())

    selected: list[DataSourceConfig] = []
    for name in args:
        if name not in app_config.datasources:
            known = ", ".join(app_config.datasources.keys())
            raise SystemExit(f"Unknown datasource: {name}. Known datasources: {known}")
        selected.append(app_config.datasources[name])
    return selected


def main() -> int:
    app_config = load_config()
    datasources = select_datasources(app_config, sys.argv[1:])
    if not datasources:
        print("No datasource configured.")
        return 1

    ok = True
    for datasource in datasources:
        ok = check_datasource(datasource) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

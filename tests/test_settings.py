from pathlib import Path

import pytest

from dm_db_readonly.settings import load_config


def test_load_config_rejects_unknown_db_type(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
datasources:
  bad:
    dbType: "oracle"
    project: "project"
    env: "dev"
    description: "bad datasource"
    driver: "driver"
    host: "127.0.0.1"
    port: 1521
    schema: "APP"
    username: "readonly"
    passwordEnv: "PASSWORD"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="不支持的 dbType"):
        load_config(config)

from dm_db_readonly.entity_resolver import entity_type_to_table
from dm_db_readonly.settings import load_config
from dm_db_readonly.tools import datasource_list


def test_entity_type_to_table_simple_name():
    assert entity_type_to_table("Inventory") == "MOM_INVENTORY"


def test_entity_type_to_table_pascal_case_name():
    assert entity_type_to_table("InventoryBatchAttribute") == "MOM_INVENTORY_BATCH_ATTRIBUTE"


def test_entity_type_override():
    assert entity_type_to_table("SpecialEntity", {"SpecialEntity": "MOM_CUSTOM"}) == "MOM_CUSTOM"


def test_datasource_list_uses_fixed_structure(monkeypatch):
    monkeypatch.setenv("MOM_INS_RO_PASSWORD", "dummy-password")
    config = load_config()
    items = datasource_list()
    assert items
    first = items[0]
    first_config = config.datasources[first["name"]]
    assert set(first.keys()) == {"name", "project", "env", "schema", "description"}
    assert first["project"] == first_config.project
    assert first["env"] == first_config.env
    assert first["schema"] == first_config.schema

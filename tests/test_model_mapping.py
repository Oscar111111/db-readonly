import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZIP_DEFLATED, ZipFile

from dm_db_readonly import model_mapping, tools
from dm_db_readonly.datasource import DataSource
from dm_db_readonly.model_mapping import load_model_mapping
from dm_db_readonly.settings import AppConfig, DataSourceConfig, load_config
from dm_db_readonly.sql_guard import SqlGuardError


MODEL = {
    "APP": "KMMOM-TFQD",
    "VERSION": "2.7.7",
    "DATA": [
        {
            "CCODE": "BaseObject",
            "CNAME": "基础对象",
            "CTABLE_NAME": None,
            "PROPS": [{"CCODE": "id", "CNAME": "标识", "CCOLUMN_NAME": "CID"}],
        },
        {
            "CCODE": "ConstructionOutsource",
            "CNAME": "施工单外委需求",
            "CTABLE_NAME": "MOM_QD_CONSTRUCTION_OUTSOURCE",
            "CPARENT": "BaseObject",
            "PROPS": [
                {"CCODE": "requiredDeliveryDate", "CNAME": "要求交付时间", "CCOLUMN_NAME": "FREQUIRED_DELIVERY_DATE"},
                {"CCODE": "bizStatus", "CNAME": "业务状态", "CCOLUMN_NAME": "FBIZ_STATUS"},
                {"CCODE": "source", "CNAME": "来源对象", "CCOLUMN_NAME": "CSOURCE", "CDATA_TYPE": "REFERENCE_OBJECT", "CREFERENCE_TYPE": "Source"},
                {"CCODE": "calculated", "CNAME": "计算属性", "CCOLUMN_NAME": None},
            ],
        },
    ],
}


class ModelMappingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        load_model_mapping.cache_clear()
        self.addCleanup(load_model_mapping.cache_clear)
        self.config = DataSourceConfig(
            name="tfqd-dev",
            project="km-mom-tfqd",
            env="dev",
            description="test datasource",
            driver="driver",
            host="127.0.0.1",
            port=5236,
            schema="TEST",
            username="readonly",
            password_env="PASSWORD",
            max_rows=10,
            query_timeout_seconds=10,
            allow_tables=["*"],
            deny_tables=[],
            mapping_dir=self.directory,
        )

    def write_package(self, model=None, filename="app_KMMOM-TFQD_v2.7.7.zip", entry="models/test.dm.json"):
        path = self.directory / filename
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            archive.writestr(entry, json.dumps(MODEL if model is None else model, ensure_ascii=False))
        return path

    def test_code_name_table_and_inherited_columns(self):
        self.write_package()
        mapping = load_model_mapping(self.directory)
        entity = mapping.resolve("ConstructionOutsource")
        self.assertIs(mapping.resolve("施工单外委需求"), entity)
        self.assertIs(mapping.resolve("MOM_QD_CONSTRUCTION_OUTSOURCE"), entity)
        self.assertEqual(mapping.columns(entity, "requiredDeliveryDate"), ["FREQUIRED_DELIVERY_DATE"])
        self.assertEqual(mapping.columns(entity, "要求交付时间"), ["FREQUIRED_DELIVERY_DATE"])
        self.assertEqual(mapping.columns(entity, "id"), ["CID"])
        self.assertEqual(mapping.columns(entity, "CID"), ["CID"])
        self.assertEqual(mapping.columns(entity, "source"), ["CSOURCE_ID", "CSOURCE_ENTITY_TYPE"])
        self.assertEqual(mapping.columns(entity, "CSOURCE_ID"), ["CSOURCE_ID"])
        self.assertEqual(mapping.version, "2.7.7")

    def test_package_priority_and_datasource_isolation(self):
        self.write_package()
        ds = DataSource(self.config)
        sql = tools.build_entity_query_sql(
            ds, "施工单外委需求", ["id", "requiredDeliveryDate", "业务状态"],
            "FBIZ_STATUS = 'NORMAL'", limit=100,
            entity_overrides={"ConstructionOutsource": "MOM_WRONG"},
        )
        self.assertEqual(sql, "SELECT CID, FREQUIRED_DELIVERY_DATE, FBIZ_STATUS FROM TEST.MOM_QD_CONSTRUCTION_OUTSOURCE WHERE FBIZ_STATUS = 'NORMAL' FETCH FIRST 10 ROWS ONLY")
        product = DataSource(replace(self.config, project="km-mom-next", schema="MOM_INS", mapping_dir=None))
        fallback = tools.build_entity_query_sql(product, "ConstructionOutsource", ["CID"])
        self.assertIn("MOM_INS.MOM_CONSTRUCTION_OUTSOURCE", fallback)
        legacy = tools.build_entity_query_sql(product, "Special", ["CID"], entity_overrides={"Special": "MOM_CUSTOM"})
        self.assertIn("MOM_INS.MOM_CUSTOM", legacy)

    def test_empty_and_missing_directory_use_legacy_rules(self):
        for directory in (None, self.directory, self.directory / "missing"):
            with self.subTest(directory=directory):
                self.assertIsNone(load_model_mapping(directory))
                sql = tools.build_entity_query_sql(DataSource(replace(self.config, mapping_dir=directory)), "Inventory", ["CID"])
                self.assertIn("TEST.MOM_INVENTORY", sql)

    def test_mapping_dir_is_relative_to_yaml(self):
        config_file = self.directory / "config.yaml"
        config_file.write_text("""datasources:
  example:
    project: km-mom-tfqd
    env: dev
    driver: driver
    host: 127.0.0.1
    schema: TEST
    username: readonly
    passwordEnv: PASSWORD
    mappingDir: packages/tfqd
""", encoding="utf-8")
        config = load_config(config_file).datasources["example"]
        self.assertEqual(config.mapping_dir, (self.directory / "packages/tfqd").resolve())

    def test_multiple_packages_fail(self):
        self.write_package()
        self.write_package(filename="other.zip")
        with self.assertRaisesRegex(ValueError, "只保留一个 ZIP"):
            load_model_mapping(self.directory)

    def test_same_project_with_different_environment_packages_is_isolated(self):
        self.write_package()
        first = load_model_mapping(self.directory)
        other_dir = self.directory / "other-env"
        other_dir.mkdir()
        model = copy.deepcopy(MODEL)
        model["DATA"][1]["CTABLE_NAME"] = "MOM_OTHER_ENV"
        with ZipFile(other_dir / "other.zip", "w") as archive:
            archive.writestr("models/test.dm.json", json.dumps(model))
        other = load_model_mapping(other_dir)
        self.assertEqual(first.resolve("ConstructionOutsource")["CTABLE_NAME"], "MOM_QD_CONSTRUCTION_OUTSOURCE")
        self.assertEqual(other.resolve("ConstructionOutsource")["CTABLE_NAME"], "MOM_OTHER_ENV")

    def test_model_size_and_conflicting_definitions_are_rejected(self):
        self.write_package()
        with patch.object(model_mapping, "MAX_MODEL_BYTES", 1), self.assertRaisesRegex(ValueError, "总大小"):
            load_model_mapping(self.directory)
        model = copy.deepcopy(MODEL)
        model["DATA"].append(dict(model["DATA"][1], CTABLE_NAME="MOM_CONFLICT"))
        self.write_package(model)
        with self.assertRaisesRegex(ValueError, "实体编码重复"):
            load_model_mapping(self.directory)

    def test_invalid_property_structure_and_mapping_dir_type_fail(self):
        for props in ({}, "", [{"CCODE": "id", "CCOLUMN_NAME": []}]):
            model = copy.deepcopy(MODEL)
            model["DATA"][1]["PROPS"] = props
            self.write_package(model)
            with self.subTest(props=props), self.assertRaises(ValueError):
                load_model_mapping(self.directory)
        config = self.directory / "config.yaml"
        config.write_text("""datasources:
  bad:
    project: km-mom-tfqd
    schema: TEST
    mappingDir: []
""", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "mappingDir"):
            load_config(config)

    def test_invalid_package_is_not_silently_ignored(self):
        (self.directory / "broken.zip").write_bytes(b"not a ZIP")
        with self.assertRaisesRegex(ValueError, "无法加载映射包"):
            tools.build_entity_query_sql(DataSource(self.config), "ConstructionOutsource", ["CID"])

    def test_app_is_metadata_and_invalid_json_structure_fails(self):
        self.write_package(dict(MODEL, APP="OTHER"))
        mapping = load_model_mapping(self.directory)
        self.assertEqual(mapping.apps, ["OTHER"])
        ds = DataSource(replace(self.config, project="km-mom-next"))
        sql = tools.build_entity_query_sql(ds, "ConstructionOutsource", ["id"])
        self.assertIn("TEST.MOM_QD_CONSTRUCTION_OUTSOURCE", sql)
        for data in ({}, []):
            with self.subTest(data=data):
                load_model_mapping.cache_clear()
                self.write_package(dict(MODEL, DATA=data))
                with self.assertRaises(ValueError):
                    load_model_mapping(self.directory)

    def test_missing_or_invalid_model_json_fails(self):
        self.write_package(entry="modules/test.dm.json")
        with self.assertRaisesRegex(ValueError, "没有 models"):
            load_model_mapping(self.directory)
        with ZipFile(self.directory / "app_KMMOM-TFQD_v2.7.7.zip", "w") as archive:
            archive.writestr("models/test.dm.json", "{")
        with self.assertRaisesRegex(ValueError, "无法加载映射包"):
            load_model_mapping(self.directory)

    def test_cache_survives_package_replacement_until_restart(self):
        self.write_package()
        initial = load_model_mapping(self.directory)
        updated = copy.deepcopy(MODEL)
        updated["VERSION"] = "2.8.0"
        updated["DATA"][1]["CTABLE_NAME"] = "MOM_NEW_TABLE"
        self.write_package(updated)
        with patch.object(model_mapping, "ZipFile", side_effect=AssertionError("ZIP reopened")):
            self.assertIs(load_model_mapping(self.directory), initial)
        load_model_mapping.cache_clear()
        self.assertEqual(load_model_mapping(self.directory).resolve("ConstructionOutsource")["CTABLE_NAME"], "MOM_NEW_TABLE")

    def test_unknown_ambiguous_and_virtual_entities_fail(self):
        model = copy.deepcopy(MODEL)
        model["DATA"].append(dict(model["DATA"][1], CCODE="Other", CTABLE_NAME="MOM_OTHER"))
        self.write_package(model)
        mapping = load_model_mapping(self.directory)
        for name in ("Unknown", "施工单外委需求", "BaseObject"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                mapping.resolve(name)

    def test_virtual_ambiguous_and_inherited_properties(self):
        model = copy.deepcopy(MODEL)
        model["DATA"][1]["PROPS"].append({"CCODE": "otherStatus", "CNAME": "业务状态", "CCOLUMN_NAME": "FOTHER_STATUS"})
        self.write_package(model)
        mapping = load_model_mapping(self.directory)
        entity = mapping.resolve("ConstructionOutsource")
        for name in ("calculated", "业务状态"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                mapping.columns(entity, name)

    def test_inheritance_cycle_fails(self):
        model = copy.deepcopy(MODEL)
        model["DATA"][0]["CPARENT"] = "ConstructionOutsource"
        self.write_package(model)
        mapping = load_model_mapping(self.directory)
        with self.assertRaisesRegex(ValueError, "循环"):
            mapping.properties(mapping.resolve("ConstructionOutsource"))

    def test_guards_still_apply_after_mapping(self):
        self.write_package()
        ds = DataSource(replace(self.config, deny_tables=["MOM_QD_*"]))
        with self.assertRaises(SqlGuardError):
            tools.build_entity_query_sql(ds, "ConstructionOutsource", ["id"])
        ds = DataSource(self.config)
        for columns, where in ((["*"], ""), ([], ""), (["CID; DROP TABLE X"], ""), (["id"], "CID = 1; DELETE FROM TEST.MOM_X")):
            with self.subTest(columns=columns), self.assertRaises(SqlGuardError):
                tools.build_entity_query_sql(ds, "ConstructionOutsource", columns, where)

    def test_unsafe_entity_identifiers_fail_but_property_mapping_is_local(self):
        for key, value in (("CTABLE_NAME", "OTHER.MOM_QD_TABLE"), ("CTABLE_NAME", "MOM_X; DROP TABLE Y")):
            model = copy.deepcopy(MODEL)
            model["DATA"][1][key] = value
            load_model_mapping.cache_clear()
            self.write_package(model)
            with self.assertRaises(ValueError):
                load_model_mapping(self.directory)
        model = copy.deepcopy(MODEL)
        model["DATA"][1]["PROPS"][0]["CCOLUMN_NAME"] = "FHANDLING_RESULT_OWNER`用户"
        load_model_mapping.cache_clear()
        self.write_package(model)
        mapping = load_model_mapping(self.directory)
        entity = mapping.resolve("ConstructionOutsource")
        self.assertIn("requiredDeliveryDate", mapping.property_errors(entity))
        self.assertEqual(mapping.columns(entity, "bizStatus"), ["FBIZ_STATUS"])
        with self.assertRaisesRegex(ValueError, "字段映射无效"):
            mapping.columns(entity, "requiredDeliveryDate")

    def test_resolve_describe_and_query_share_mapping(self):
        self.write_package()
        ds = Mock(spec=DataSource)
        ds.config = self.config
        ds.table_exists.return_value = False
        ds.describe_table.return_value = [{"COLUMN_NAME": "FREQUIRED_DELIVERY_DATE", "DATA_TYPE": "DATETIME"}]
        ds.query.return_value = []
        with patch.object(tools, "_datasource", return_value=ds), patch.object(tools, "_config", return_value=AppConfig({"tfqd-dev": self.config}, {})):
            resolved = tools.entity_resolve("tfqd-dev", "施工单外委需求")
            self.assertEqual(resolved["table"], "MOM_QD_CONSTRUCTION_OUTSOURCE")
            self.assertEqual(resolved["entityType"], "ConstructionOutsource")
            self.assertEqual(resolved["mappingVersion"], "2.7.7")
            self.assertEqual(resolved["mappingApps"], ["KMMOM-TFQD"])
            self.assertFalse(resolved["exists"])
            described = tools.entity_describe("tfqd-dev", "ConstructionOutsource")
            self.assertEqual(described[0]["PROPERTY_CODE"], "requiredDeliveryDate")
            self.assertEqual(described[0]["DATA_TYPE"], "DATETIME")
            tools.entity_query("tfqd-dev", "ConstructionOutsource", ["requiredDeliveryDate"])
            self.assertIn("FREQUIRED_DELIVERY_DATE FROM TEST.MOM_QD_CONSTRUCTION_OUTSOURCE", ds.query.call_args.args[0])

    def test_entity_tools_expand_reference_properties(self):
        self.write_package()
        ds = Mock(spec=DataSource)
        ds.config = self.config
        ds.table_exists.return_value = True
        ds.describe_table.return_value = [
            {"COLUMN_NAME": "CSOURCE_ID", "DATA_TYPE": "BIGINT"},
            {"COLUMN_NAME": "CSOURCE_ENTITY_TYPE", "DATA_TYPE": "VARCHAR"},
        ]
        ds.query.return_value = []
        with patch.object(tools, "_datasource", return_value=ds), patch.object(tools, "_config", return_value=AppConfig({"tfqd-dev": self.config}, {})):
            described = tools.entity_describe("tfqd-dev", "ConstructionOutsource")
            self.assertEqual({row["PROPERTY_CODE"] for row in described}, {"source"})
            tools.entity_query("tfqd-dev", "ConstructionOutsource", ["source"])
            sql = ds.query.call_args.args[0]
            self.assertIn("CSOURCE_ID, CSOURCE_ENTITY_TYPE", sql)

    def test_reference_suffixes_names_and_physical_columns(self):
        for base in ("CSOURCE", "CSOURCE_ID", "CSOURCE_ENTITY_TYPE"):
            with self.subTest(base=base):
                load_model_mapping.cache_clear()
                model = copy.deepcopy(MODEL)
                model["DATA"][1]["PROPS"][2]["CCOLUMN_NAME"] = base
                self.write_package(model)
                mapping = load_model_mapping(self.directory)
                entity = mapping.resolve("ConstructionOutsource")
                self.assertEqual(mapping.columns(entity, "来源对象"), ["CSOURCE_ID", "CSOURCE_ENTITY_TYPE"])
                sql = tools.build_entity_query_sql(DataSource(self.config), "ConstructionOutsource", ["source", "bizStatus"], "CSOURCE_ID = 1")
                self.assertEqual(sql, "SELECT CSOURCE_ID, CSOURCE_ENTITY_TYPE, FBIZ_STATUS FROM TEST.MOM_QD_CONSTRUCTION_OUTSOURCE WHERE CSOURCE_ID = 1 FETCH FIRST 10 ROWS ONLY")
                physical_sql = tools.build_entity_query_sql(DataSource(self.config), "ConstructionOutsource", ["CSOURCE_ID"])
                self.assertIn("SELECT CSOURCE_ID FROM", physical_sql)

    def test_non_reference_property_never_expands_by_name(self):
        model = copy.deepcopy(MODEL)
        model["DATA"][1]["PROPS"][2]["CDATA_TYPE"] = "STRING"
        self.write_package(model)
        mapping = load_model_mapping(self.directory)
        self.assertEqual(mapping.columns(mapping.resolve("ConstructionOutsource"), "source"), ["CSOURCE"])

    def test_user_and_business_org_properties_expand(self):
        model = copy.deepcopy(MODEL)
        model["DATA"][1]["PROPS"].extend([
            {"CCODE": "creator", "CNAME": "创建者", "CCOLUMN_NAME": "CCREATOR", "CDATA_TYPE": "USER", "CREFERENCE_TYPE": "User"},
            {"CCODE": "bizOrg", "CNAME": "业务组织", "CCOLUMN_NAME": "CBIZ_ORG", "CDATA_TYPE": "BIZ_ORG", "CREFERENCE_TYPE": "BizOrg"},
        ])
        self.write_package(model)
        mapping = load_model_mapping(self.directory)
        entity = mapping.resolve("ConstructionOutsource")
        self.assertEqual(mapping.columns(entity, "creator"), ["CCREATOR_ID", "CCREATOR_ENTITY_TYPE"])
        self.assertEqual(mapping.columns(entity, "bizOrg"), ["CBIZ_ORG_ID", "CBIZ_ORG_ENTITY_TYPE"])

    def test_invalid_property_is_visible_and_never_executed(self):
        model = copy.deepcopy(MODEL)
        model["DATA"][1]["PROPS"].append({"CCODE": "badOwner", "CNAME": "责任人", "CCOLUMN_NAME": "FOWNER`用户", "CDATA_TYPE": "REFERENCE_OBJECT"})
        self.write_package(model)
        ds = Mock(spec=DataSource)
        ds.config = self.config
        ds.table_exists.return_value = True
        ds.describe_table.return_value = [{"COLUMN_NAME": "FBIZ_STATUS"}]
        ds.query.return_value = []
        with patch.object(tools, "_datasource", return_value=ds), patch.object(tools, "_config", return_value=AppConfig({"tfqd-dev": self.config}, {})):
            resolved = tools.entity_resolve("tfqd-dev", "ConstructionOutsource")
            bad = next(prop for prop in resolved["properties"] if prop["code"] == "badOwner")
            self.assertEqual(bad["columns"], [])
            self.assertIn("非法字段名", bad["error"])
            self.assertEqual(tools.entity_describe("tfqd-dev", "ConstructionOutsource")[0]["PROPERTY_CODE"], "bizStatus")
            for name in ("badOwner", "责任人"):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "字段映射无效"):
                    tools.entity_query("tfqd-dev", "ConstructionOutsource", [name])
            ds.query.assert_not_called()
            tools.entity_query("tfqd-dev", "ConstructionOutsource", ["bizStatus"])
            ds.query.assert_called_once()

    def test_child_override_replaces_parent_mapping_error(self):
        model = copy.deepcopy(MODEL)
        model["DATA"][0]["PROPS"][0]["CCOLUMN_NAME"] = "BAD`COLUMN"
        model["DATA"][1]["PROPS"].append({"CCODE": "id", "CCOLUMN_NAME": "CID"})
        self.write_package(model)
        mapping = load_model_mapping(self.directory)
        entity = mapping.resolve("ConstructionOutsource")
        self.assertEqual(mapping.columns(entity, "id"), ["CID"])
        self.assertNotIn("id", mapping.property_errors(entity))

    def test_bad_reference_prefix_is_local_and_invalid_types_fail(self):
        model = copy.deepcopy(MODEL)
        model["DATA"][1]["PROPS"][2]["CCOLUMN_NAME"] = "_ID"
        self.write_package(model)
        mapping = load_model_mapping(self.directory)
        entity = mapping.resolve("ConstructionOutsource")
        self.assertIn("source", mapping.property_errors(entity))
        with self.assertRaisesRegex(ValueError, "字段映射无效"):
            mapping.columns(entity, "source")
        for key in ("CDATA_TYPE", "CREFERENCE_TYPE"):
            with self.subTest(key=key):
                load_model_mapping.cache_clear()
                model = copy.deepcopy(MODEL)
                model["DATA"][1]["PROPS"][2][key] = []
                self.write_package(model)
                with self.assertRaisesRegex(ValueError, key):
                    load_model_mapping(self.directory)

    def test_dm_table_sql_and_datasource_tools_never_load_mapping(self):
        ds = Mock(spec=DataSource)
        ds.config = self.config
        ds.describe_table.return_value = [{"COLUMN_NAME": "CSOURCE_ID"}]
        ds.query.return_value = []
        with patch.object(tools, "_datasource", return_value=ds), patch.object(tools, "_config", return_value=AppConfig({"tfqd-dev": self.config}, {})), patch.object(tools, "load_model_mapping", side_effect=AssertionError("mapping loaded")):
            self.assertEqual(set(tools.datasource_list()[0]), {"name", "project", "env", "schema", "description"})
            tools.table_describe("tfqd-dev", "MOM_QD_CONSTRUCTION_OUTSOURCE")
            tools.table_query("tfqd-dev", "MOM_QD_CONSTRUCTION_OUTSOURCE", ["CSOURCE_ID"], limit=1)
            self.assertEqual(ds.query.call_args.args[0], "SELECT CSOURCE_ID FROM TEST.MOM_QD_CONSTRUCTION_OUTSOURCE FETCH FIRST 1 ROWS ONLY")
            tools.sql_query("tfqd-dev", "SELECT CID FROM TEST.MOM_QD_CONSTRUCTION_OUTSOURCE")
            self.assertIn("SELECT CID FROM TEST.MOM_QD_CONSTRUCTION_OUTSOURCE", ds.query.call_args.args[0])

    def test_mysql_and_table_tools_do_not_load_packages(self):
        self.write_package()
        ds = DataSource(replace(self.config, db_type="mysql", schema="app_db"))
        with patch.object(tools, "load_model_mapping", side_effect=AssertionError("mapping loaded")):
            with self.assertRaisesRegex(ValueError, "MySQL datasource"):
                tools.build_entity_query_sql(ds, "Order", ["id"])
            self.assertEqual(tools.build_table_query_sql(ds, "orders", ["id"], limit=2), "SELECT `id` FROM `app_db`.`orders` LIMIT 2")


if __name__ == "__main__":
    unittest.main()

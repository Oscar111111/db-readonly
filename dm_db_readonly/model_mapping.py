from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from dm_db_readonly.sql_guard import validate_columns, validate_table_name


MAX_MODEL_BYTES = 32 * 1024 * 1024


@dataclass
class ModelMapping:
    package: Path
    version: str
    apps: list[str]
    entities: dict[str, dict]
    aliases: dict[str, set[str]]
    invalid_properties: dict[str, dict[str, str]]

    def resolve(self, name: str) -> dict:
        codes = {name} if name in self.entities else self.aliases.get(name, set())
        if not codes:
            raise ValueError(f"模型包中没有实体：{name}，请确认版本或使用真实表名的 table_* 工具")
        if len(codes) != 1:
            raise ValueError(f"实体名称有歧义：{name}，候选编码：{', '.join(sorted(codes))}")
        entity = self.entities[next(iter(codes))]
        if not entity.get("CTABLE_NAME"):
            raise ValueError(f"实体没有物理表：{entity['CCODE']}")
        return entity

    def properties(self, entity: dict) -> list[dict]:
        lineage = self._lineage(entity)
        props = {}
        for model in reversed(lineage):
            for prop in model.get("PROPS") or []:
                props[prop["CCODE"]] = prop
        return list(props.values())

    def property_errors(self, entity: dict) -> dict[str, str]:
        errors = {}
        for model in reversed(self._lineage(entity)):
            for prop in model.get("PROPS") or []:
                errors.pop(prop["CCODE"], None)
            errors.update(self.invalid_properties.get(model["CCODE"], {}))
        return errors

    def columns(self, entity: dict, name: str) -> list[str]:
        props = self.properties(entity)
        matches = [prop for prop in props if prop["CCODE"] == name]
        if not matches:
            matches = [prop for prop in props if prop.get("CNAME") == name]
        if len(matches) > 1:
            raise ValueError(f"字段名称有歧义：{name}，请指定字段编码")
        if not matches:
            return [name]

        prop = matches[0]
        code = prop["CCODE"]
        error = self.property_errors(entity).get(code)
        if error:
            raise ValueError(f"字段映射无效：{name}；{error}")
        column = prop.get("CCOLUMN_NAME")
        if not column:
            raise ValueError(f"字段没有物理列：{name}，不能直接查询")
        return _property_columns(prop)

    def _lineage(self, entity: dict) -> list[dict]:
        lineage = []
        seen = set()
        current = entity
        while current:
            code = current["CCODE"]
            if code in seen:
                raise ValueError(f"模型继承关系存在循环：{code}")
            seen.add(code)
            lineage.append(current)
            current = self.entities.get(current.get("CPARENT"))
        return lineage


@cache
def load_model_mapping(mapping_dir: Path | None) -> ModelMapping | None:
    # shortcut: mappings stay fixed for this process; restart MCP after replacing a package.
    if mapping_dir is None or not mapping_dir.exists():
        return None
    if not mapping_dir.is_dir():
        raise ValueError(f"mappingDir 不是目录：{mapping_dir}")
    packages = [path for path in mapping_dir.iterdir() if path.is_file() and path.suffix.lower() == ".zip"]
    if not packages:
        return None
    if len(packages) != 1:
        raise ValueError(f"mappingDir 必须只保留一个 ZIP：{mapping_dir}")
    package = packages[0]
    entities = {}
    aliases: dict[str, set[str]] = {}
    invalid_properties: dict[str, dict[str, str]] = {}
    versions = set()
    apps = set()
    try:
        with ZipFile(package) as archive:
            entries = [entry for entry in archive.infolist()
                       if entry.filename.startswith("models/") and entry.filename.endswith(".dm.json")]
            if not entries:
                raise ValueError("ZIP 中没有 models/*.dm.json")
            if sum(entry.file_size for entry in entries) > MAX_MODEL_BYTES:
                raise ValueError("模型 JSON 总大小不能超过 32 MiB")
            for entry in entries:
                model = json.loads(archive.read(entry).decode("utf-8-sig"))
                if not isinstance(model, dict) or not isinstance(model.get("DATA"), list):
                    raise ValueError(f"{entry.filename} 必须包含 DATA 数组")
                app = model.get("APP")
                if app is not None:
                    if not isinstance(app, str):
                        raise ValueError(f"{entry.filename} 的 APP 必须是字符串")
                    if app:
                        apps.add(app)
                version = model.get("VERSION")
                if version is not None:
                    versions.add(str(version))
                for entity in model["DATA"]:
                    invalid = _validate_entity(entity)
                    code = entity["CCODE"]
                    if code in entities and entities[code] != entity:
                        raise ValueError(f"模型包内实体编码重复且定义不同：{code}")
                    entities[code] = entity
                    if invalid:
                        invalid_properties[code] = invalid
                    for alias in (code, entity.get("CNAME"), entity.get("CTABLE_NAME")):
                        if alias:
                            aliases.setdefault(alias, set()).add(code)
    except (BadZipFile, OSError, UnicodeError, ValueError, RuntimeError, NotImplementedError) as error:
        raise ValueError(f"无法加载映射包 {package.name}：{error}") from error
    if not entities:
        raise ValueError(f"映射包没有实体定义：{package.name}")
    if len(versions) > 1:
        raise ValueError(f"映射包包含不同模型版本：{package.name}")
    return ModelMapping(package, next(iter(versions), ""), sorted(apps), entities, aliases, invalid_properties)


def _validate_entity(entity: object) -> dict[str, str]:
    if not isinstance(entity, dict) or not isinstance(entity.get("CCODE"), str) or not entity["CCODE"]:
        raise ValueError("实体必须包含非空 CCODE")
    for key in ("CNAME", "CTABLE_NAME", "CPARENT"):
        if entity.get(key) is not None and not isinstance(entity[key], str):
            raise ValueError(f"实体 {entity['CCODE']} 的 {key} 必须是字符串")
    if entity.get("CTABLE_NAME"):
        validate_table_name(entity["CTABLE_NAME"])
    props = entity.get("PROPS")
    if props is None:
        props = []
    if not isinstance(props, list):
        raise ValueError(f"实体 {entity['CCODE']} 的 PROPS 必须是数组")
    codes = set()
    invalid: dict[str, str] = {}
    for prop in props:
        if not isinstance(prop, dict) or not isinstance(prop.get("CCODE"), str) or not prop["CCODE"]:
            raise ValueError("属性必须包含非空 CCODE")
        if prop["CCODE"] in codes:
            raise ValueError(f"实体 {entity['CCODE']} 的属性编码重复：{prop['CCODE']}")
        codes.add(prop["CCODE"])
        for key in ("CNAME", "CCOLUMN_NAME", "CDATA_TYPE", "CREFERENCE_TYPE"):
            if prop.get(key) is not None and not isinstance(prop[key], str):
                raise ValueError(f"属性 {prop['CCODE']} 的 {key} 必须是字符串")
        if prop.get("CCOLUMN_NAME"):
            try:
                _property_columns(prop)
            except ValueError as error:
                # Keep a bad physical field local; never repair it by guessing.
                invalid[prop["CCODE"]] = str(error)
    return invalid


def _property_columns(prop: dict) -> list[str]:
    column = validate_columns([prop["CCOLUMN_NAME"]])[0]
    if prop.get("CDATA_TYPE") not in {"REFERENCE_OBJECT", "USER", "BIZ_ORG"}:
        return [column]
    # Object, user, and business-organization properties store ID and entity type.
    for suffix in ("_ENTITY_TYPE", "_ID"):
        if column.endswith(suffix):
            column = column[:-len(suffix)]
            break
    validate_columns([column])
    return validate_columns([f"{column}_ID", f"{column}_ENTITY_TYPE"])

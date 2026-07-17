import re


def to_upper_snake(name: str) -> str:
    value = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return value.replace("-", "_").upper()


def entity_type_to_table(entity_type: str, overrides: dict[str, str] | None = None) -> str:
    overrides = overrides or {}
    if entity_type in overrides:
        return overrides[entity_type].upper()
    return f"MOM_{to_upper_snake(entity_type)}"


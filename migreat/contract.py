import json
import re
from importlib.resources import files
from pathlib import Path

import jsonschema
import yaml

from .migration import Column, DesiredTable, MigrationError, TableName

IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,62}")
LOGICAL_TYPES = {"bigint": "integer", "integer": "integer", "text": "string", "boolean": "boolean"}


def load_contract(path: Path) -> DesiredTable:
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    schema = json.loads(files(__package__).joinpath("odcs-3.2.0.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(contract, schema)
    except jsonschema.ValidationError as error:
        location = ".".join(map(str, error.absolute_path)) or "document"
        raise MigrationError(f"Invalid ODCS contract at {location}: {error.message}") from error
    if contract["apiVersion"] != "v3.2.0":
        raise MigrationError("Use apiVersion v3.2.0.")
    tables = contract.get("schema", [])
    if len(tables) != 1 or tables[0].get("physicalType") != "table":
        raise MigrationError("Declare exactly one ODCS table with physicalType: table.")
    table = tables[0]
    parts = table.get("physicalName", "").split(".")
    if len(parts) != 2 or any(not IDENTIFIER.fullmatch(part) for part in parts):
        raise MigrationError("Set the table physicalName to schema.table with simple PostgreSQL identifiers.")

    columns = []
    names = set()
    for field in table.get("properties", []):
        name = field.get("physicalName", field["name"])
        data_type = field.get("physicalType", "").lower()
        if not IDENTIFIER.fullmatch(name) or name in names:
            raise MigrationError(f"Invalid or duplicate physical column name {name!r}.")
        if data_type not in LOGICAL_TYPES or field.get("logicalType") != LOGICAL_TYPES[data_type]:
            raise MigrationError(f"Unsupported logical and physical type mapping for {name!r}.")
        if "required" not in field:
            raise MigrationError(f"Set required explicitly for {name!r}.")
        names.add(name)
        columns.append(Column(name, data_type, not field["required"]))
    if not columns:
        raise MigrationError("Declare at least one column.")
    return DesiredTable(TableName(*parts), tuple(columns))

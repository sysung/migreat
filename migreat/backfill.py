import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
from pathlib import Path

import yaml
from psycopg import sql


MAX_KEYS = 1_000
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,62}")


class BackfillError(ValueError):
    pass


class DeclarationLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        keys = [key.value for key, _ in node.value if isinstance(key, yaml.ScalarNode)]
        if len(keys) != len(node.value) or len(keys) != len(set(keys)):
            raise BackfillError("Use unique scalar declaration keys.")
        return super().construct_mapping(node, deep=deep)


@dataclass(frozen=True, order=True)
class Table:
    schema: str
    name: str

    @classmethod
    def parse(cls, value):
        parts = value.split(".") if isinstance(value, str) else []
        if len(parts) != 2 or not all(IDENTIFIER.fullmatch(part) for part in parts):
            raise BackfillError("Use schema-qualified source and target table names.")
        return cls(*parts)

    def identifier(self):
        return sql.Identifier(self.schema, self.name)

    def __str__(self):
        return f"{self.schema}.{self.name}"


@dataclass(frozen=True)
class Declaration:
    database: str
    source: Table
    target: Table
    key: str
    column: str
    start: int
    end: int


@dataclass(frozen=True)
class ColumnAddition:
    database: str
    target: Table
    key: str
    column: str
    start: int
    end: int
    source: Table | None
    source_column: str | None
    multiplier: Decimal | None

    @property
    def column_type(self):
        return "timestamp with time zone" if self.multiplier is None else "numeric"


@dataclass(frozen=True)
class Snapshot:
    oid: int
    columns: tuple
    constraints: tuple
    values: tuple[tuple[int, int | Decimal | datetime | None], ...]


@dataclass(frozen=True)
class Preview:
    source: Snapshot | None
    target: Snapshot
    pending: int
    correct: int
    blocked: tuple[str, ...]
    expected: tuple[tuple[int, Decimal], ...] = ()


def load_declaration(path: Path) -> Declaration | ColumnAddition:
    return parse_declaration(yaml.load(path.read_text(), Loader=DeclarationLoader))


def parse_declaration(data) -> Declaration | ColumnAddition:
    fields = {"database", "target", "key", "column", "start", "end"}
    if not isinstance(data, dict) or data.keys() not in (fields | {"source"}, fields | {"fill"}):
        raise BackfillError("Declare only the fields database, target, key, column, start, and end with either source or fill.")
    validate_scope(data["database"], data["key"], data["column"], data["start"], data["end"])
    target = Table.parse(data["target"])
    start, end = data["start"], data["end"]
    if "fill" not in data:
        source = Table.parse(data["source"])
        if source == target:
            raise BackfillError("Use distinct source and target tables.")
        return Declaration(data["database"], source, target, data["key"], data["column"], start, end)

    fill = data["fill"]
    scope = (data["database"], target, data["key"], data["column"], start, end)
    if fill == {"policy": "transaction_timestamp"}:
        return ColumnAddition(*scope, None, None, None)
    if not isinstance(fill, dict) or fill.keys() != {"policy", "source", "column", "multiplier"} or fill["policy"] != "scale":
        raise BackfillError("Declare a transaction_timestamp or scale fill policy.")
    source = Table.parse(fill["source"])
    if source == target:
        raise BackfillError("Use distinct source and target tables.")
    source_column = fill["column"]
    multiplier = fill["multiplier"]
    if not isinstance(source_column, str) or not IDENTIFIER.fullmatch(source_column):
        raise BackfillError("Use a simple PostgreSQL identifier for the source column.")
    if not isinstance(multiplier, str) or not re.fullmatch(r"[+-]?[0-9]{1,100}(\.[0-9]{1,100})?", multiplier):
        raise BackfillError("Use a quoted decimal multiplier with at most 100 digits on either side of the point.")
    return ColumnAddition(*scope, source, source_column, Decimal(multiplier))


def validate_scope(database, key, column, start, end):
    for field, value in (("database", database), ("key", key), ("column", column)):
        if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
            raise BackfillError(f"Use a simple PostgreSQL identifier for {field}.")
    if key == column:
        raise BackfillError("Use distinct key and value columns.")
    if not (type(start) is int and type(end) is int and -(2**63) <= start <= end < 2**63):
        raise BackfillError("Use ordered bigint bounds for start and end.")
    if end - start + 1 > MAX_KEYS:
        raise BackfillError(f"Limit the range to {MAX_KEYS} possible keys.")


def inspect_relation(connection, table):
    rows = connection.execute(
        """
        SELECT c.oid, c.relkind, c.relrowsecurity, c.relhasrules,
               EXISTS (SELECT 1 FROM pg_catalog.pg_inherits i
                       WHERE c.oid IN (i.inhrelid, i.inhparent)),
               EXISTS (SELECT 1 FROM pg_catalog.pg_trigger t
                       WHERE t.tgrelid = c.oid AND NOT t.tgisinternal),
               a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod),
               a.attnotnull, a.attgenerated, a.attidentity,
               pg_catalog.pg_get_expr(d.adbin, d.adrelid)
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_catalog.pg_attribute a
          ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
        LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = c.oid AND d.adnum = a.attnum
        WHERE n.nspname = %s AND c.relname = %s
        ORDER BY a.attnum
        """,
        (table.schema, table.name),
    ).fetchall()
    if not rows:
        raise BackfillError(f"Table {table} does not exist.")
    oid, kind, rls, rules, inherits, triggers, *_ = rows[0]
    columns = tuple(row[6:] for row in rows)
    if kind != "r" or any((rls, rules, inherits, triggers)):
        raise BackfillError(f"Unsupported relation {table}. Use an ordinary table without inheritance, policies, rules, or user triggers.")
    constraints = tuple(connection.execute(
        """
        SELECT oid, contype, confupdtype, confrelid, pg_catalog.pg_get_constraintdef(oid)
        FROM pg_catalog.pg_constraint
        WHERE conrelid = %s OR (contype = 'f' AND confrelid = %s)
        ORDER BY oid
        """,
        (oid, oid),
    ).fetchall())
    return Snapshot(oid, columns, constraints, ())


def check_target_constraints(table, relation):
    if any(kind == "f" and referenced == relation.oid and action in ("c", "n", "d")
           for _, kind, action, referenced, _ in relation.constraints):
        raise BackfillError(f"Unsupported cascading foreign key on {table}.")


def _snapshot(connection, table, declaration, *, target, after_addition=False):
    relation = inspect_relation(connection, table)
    columns = relation.columns
    attributes = {name: (data_type, required, generated, identity)
                  for name, data_type, required, generated, identity, _ in columns}
    addition = isinstance(declaration, ColumnAddition)
    column = declaration.column if target or not addition else declaration.source_column
    absent = addition and target and not after_addition
    if absent and column in attributes:
        raise BackfillError(f"Column {table}.{column} already exists.")
    required_columns = {declaration.key: "bigint"}
    if not absent:
        required_columns[column] = declaration.column_type if addition and target else "bigint"
    for name, expected_type in required_columns.items():
        if name not in attributes:
            raise BackfillError(f"Missing column {table}.{name}. Prepare the destination schema before backfill.")
        if attributes[name][0] != expected_type:
            raise BackfillError(f"Column {table}.{name} must be {expected_type}.")
    if target and ((not absent and any(attributes[column][1:])) or any(col[3] for col in columns)):
        raise BackfillError(f"Use a nullable writable destination column and no generated target columns on {table}.")
    if target:
        check_target_constraints(table, relation)
    key = sql.Identifier(declaration.key)
    values = connection.execute(
        sql.SQL("SELECT {key}, {value} FROM ONLY {table} WHERE {key} BETWEEN %s AND %s ORDER BY {key}, {value} LIMIT %s").format(
            key=key, value=sql.SQL("NULL::bigint") if absent else sql.Identifier(column), table=table.identifier(),
        ),
        (declaration.start, declaration.end, MAX_KEYS + 1),
    ).fetchall()
    if len(values) > MAX_KEYS:
        raise BackfillError(f"Too many scoped rows in {table}.")
    return Snapshot(relation.oid, columns, relation.constraints, tuple(values))


def _inspect(connection, declaration):
    database = connection.execute("SELECT pg_catalog.current_database()").fetchone()[0]
    if database != declaration.database:
        raise BackfillError(f"Connected to database {database}, expected {declaration.database}.")
    source = (_snapshot(connection, declaration.source, declaration, target=False)
              if declaration.source else None)
    target = _snapshot(connection, declaration.target, declaration, target=True)
    addition = isinstance(declaration, ColumnAddition)
    if not target.values and not addition:
        raise BackfillError("The historical target range is empty.")
    matches = {}
    duplicate_sources = set()
    if source:
        for key, value in source.values:
            if key in matches:
                duplicate_sources.add(key)
            matches[key] = value
    seen = set()
    pending = correct = 0
    blocked = []
    expected = []
    for key, value in target.values:
        if key in seen:
            blocked.append(f"Duplicate target key {key}.")
        elif source is None:
            pending += 1
        elif key in duplicate_sources:
            blocked.append(f"Duplicate source key {key}.")
        elif key not in matches:
            blocked.append(f"Missing source match for key {key}.")
        elif matches[key] is None:
            blocked.append(f"NULL source value for key {key}.")
        elif value is None:
            pending += 1
            if addition:
                with localcontext() as context:
                    context.prec = len(declaration.multiplier.as_tuple().digits) + 19
                    expected.append((key, matches[key] * declaration.multiplier))
        elif value == matches[key]:
            correct += 1
        else:
            blocked.append(f"Conflicting populated target value for key {key}.")
        seen.add(key)
    return Preview(source, target, pending, correct, tuple(blocked), tuple(expected))

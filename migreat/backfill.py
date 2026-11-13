import re
from dataclasses import dataclass
from pathlib import Path

import psycopg
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
class Snapshot:
    oid: int
    columns: tuple
    constraints: tuple
    values: tuple[tuple[int, int | None], ...]


@dataclass(frozen=True)
class Preview:
    source: Snapshot
    target: Snapshot
    pending: int
    correct: int
    blocked: tuple[str, ...]


def load_declaration(path: Path) -> Declaration:
    data = yaml.load(path.read_text(), Loader=DeclarationLoader)
    fields = {"database", "source", "target", "key", "column", "start", "end"}
    if not isinstance(data, dict) or data.keys() != fields:
        raise BackfillError("Declare exactly database, source, target, key, column, start, and end.")
    for field in ("database", "key", "column"):
        if not isinstance(data[field], str) or not IDENTIFIER.fullmatch(data[field]):
            raise BackfillError(f"Use a simple PostgreSQL identifier for {field}.")
    source, target = Table.parse(data["source"]), Table.parse(data["target"])
    if source == target or data["key"] == data["column"]:
        raise BackfillError("Use distinct source and target tables and distinct key and value columns.")
    start, end = data["start"], data["end"]
    if not (type(start) is int and type(end) is int and -(2**63) <= start <= end < 2**63):
        raise BackfillError("Use ordered bigint bounds for start and end.")
    if end - start + 1 > MAX_KEYS:
        raise BackfillError(f"Limit the range to {MAX_KEYS} possible keys.")
    return Declaration(data["database"], source, target, data["key"], data["column"], start, end)


def _snapshot(connection, table, declaration, *, target):
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
    attributes = {name: (data_type, required, generated, identity)
                  for name, data_type, required, generated, identity, _ in columns}
    for name in (declaration.key, declaration.column):
        if name not in attributes:
            raise BackfillError(f"Missing column {table}.{name}. Prepare the destination schema before backfill.")
        if attributes[name][0] != "bigint":
            raise BackfillError(f"Column {table}.{name} must be bigint.")
    if target and (any(attributes[declaration.column][1:]) or any(col[3] for col in columns)):
        raise BackfillError(f"Use a nullable writable destination column and no generated target columns on {table}.")
    constraints = tuple(connection.execute(
        """
        SELECT oid, contype, confupdtype, confrelid, pg_catalog.pg_get_constraintdef(oid)
        FROM pg_catalog.pg_constraint
        WHERE conrelid = %s OR (contype = 'f' AND confrelid = %s)
        ORDER BY oid
        """,
        (oid, oid),
    ).fetchall())
    if target and any(kind == "f" and referenced == oid and action in ("c", "n", "d")
                      for _, kind, action, referenced, _ in constraints):
        raise BackfillError(f"Unsupported cascading foreign key on {table}.")
    key = sql.Identifier(declaration.key)
    values = connection.execute(
        sql.SQL("SELECT {key}, {value} FROM ONLY {table} WHERE {key} BETWEEN %s AND %s ORDER BY {key}, {value} LIMIT %s").format(
            key=key, value=sql.Identifier(declaration.column), table=table.identifier(),
        ),
        (declaration.start, declaration.end, MAX_KEYS + 1),
    ).fetchall()
    if len(values) > MAX_KEYS:
        raise BackfillError(f"Too many scoped rows in {table}.")
    return Snapshot(oid, columns, constraints, tuple(values))


def _inspect(connection, declaration):
    database = connection.execute("SELECT pg_catalog.current_database()").fetchone()[0]
    if database != declaration.database:
        raise BackfillError(f"Connected to database {database}, expected {declaration.database}.")
    source = _snapshot(connection, declaration.source, declaration, target=False)
    target = _snapshot(connection, declaration.target, declaration, target=True)
    if not target.values:
        raise BackfillError("The historical target range is empty.")
    matches = {}
    duplicate_sources = set()
    for key, value in source.values:
        if key in matches:
            duplicate_sources.add(key)
        matches[key] = value
    seen = set()
    pending = correct = 0
    blocked = []
    for key, value in target.values:
        if key in seen:
            blocked.append(f"Duplicate target key {key}.")
        elif key in duplicate_sources:
            blocked.append(f"Duplicate source key {key}.")
        elif key not in matches:
            blocked.append(f"Missing source match for key {key}.")
        elif matches[key] is None:
            blocked.append(f"NULL source value for key {key}.")
        elif value is None:
            pending += 1
        elif value == matches[key]:
            correct += 1
        else:
            blocked.append(f"Conflicting populated target value for key {key}.")
        seen.add(key)
    return Preview(source, target, pending, correct, tuple(blocked))


def preview(connection, declaration):
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        connection.execute("SET LOCAL lock_timeout = '2s'")
        connection.execute("SET LOCAL statement_timeout = '10s'")
        return _inspect(connection, declaration)


def apply(connection, declaration, reviewed):
    with connection.transaction():
        connection.execute("SET LOCAL lock_timeout = '2s'")
        connection.execute("SET LOCAL statement_timeout = '10s'")
        for table in sorted((declaration.source, declaration.target)):
            mode = "SHARE" if table == declaration.source else "SHARE ROW EXCLUSIVE"
            connection.execute(sql.SQL("LOCK TABLE ONLY {} IN " + mode + " MODE").format(table.identifier()))
        if _inspect(connection, declaration) != reviewed:
            raise BackfillError("Preview is stale. Run apply again to review the current data.")
        if reviewed.blocked:
            raise BackfillError("Resolve blocked rows before applying.")
        key, column = map(sql.Identifier, (declaration.key, declaration.column))
        result = connection.execute(
            sql.SQL(
                "UPDATE ONLY {target} AS dst SET {column} = src.{column} "
                "FROM ONLY {source} AS src "
                "WHERE dst.{key} = src.{key} AND dst.{key} BETWEEN %s AND %s "
                "AND dst.{column} IS NULL"
            ).format(target=declaration.target.identifier(), source=declaration.source.identifier(),
                     key=key, column=column),
            (declaration.start, declaration.end),
        )
        actual = _inspect(connection, declaration)
        expected_keys = tuple(key for key, _ in reviewed.target.values)
        if (result.rowcount != reviewed.pending or actual.pending or actual.blocked
                or actual.source != reviewed.source
                or actual.target.oid != reviewed.target.oid
                or actual.target.columns != reviewed.target.columns
                or actual.target.constraints != reviewed.target.constraints
                or tuple(key for key, _ in actual.target.values) != expected_keys):
            raise BackfillError("Post-update verification failed. The transaction was rolled back.")
        return result.rowcount

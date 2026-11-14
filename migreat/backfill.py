import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, localcontext
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
    data = yaml.load(path.read_text(), Loader=DeclarationLoader)
    fields = {"database", "target", "key", "column", "start", "end"}
    if not isinstance(data, dict) or data.keys() not in (fields | {"source"}, fields | {"fill"}):
        raise BackfillError("Declare only the fields database, target, key, column, start, and end with either source or fill.")
    for field in ("database", "key", "column"):
        if not isinstance(data[field], str) or not IDENTIFIER.fullmatch(data[field]):
            raise BackfillError(f"Use a simple PostgreSQL identifier for {field}.")
    target = Table.parse(data["target"])
    if data["key"] == data["column"]:
        raise BackfillError("Use distinct key and value columns.")
    start, end = data["start"], data["end"]
    if not (type(start) is int and type(end) is int and -(2**63) <= start <= end < 2**63):
        raise BackfillError("Use ordered bigint bounds for start and end.")
    if end - start + 1 > MAX_KEYS:
        raise BackfillError(f"Limit the range to {MAX_KEYS} possible keys.")
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


def _snapshot(connection, table, declaration, *, target, after_addition=False):
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
            key=key, value=sql.SQL("NULL::bigint") if absent else sql.Identifier(column), table=table.identifier(),
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
    source = _snapshot(connection, declaration.source, declaration, target=False) if declaration.source else None
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


def column_addition_sql(declaration):
    target = declaration.target.identifier()
    column = sql.Identifier(declaration.column)
    key = sql.Identifier(declaration.key)
    add = sql.SQL("ALTER TABLE ONLY {} ADD COLUMN {} {}").format(
        target, column, sql.SQL(declaration.column_type),
    )
    bounds = (declaration.start, declaration.end)
    if declaration.source is None:
        fill = sql.SQL("UPDATE ONLY {} AS dst SET {} = CURRENT_TIMESTAMP").format(target, column)
        match = sql.SQL("")
        params = bounds
    else:
        fill = sql.SQL("UPDATE ONLY {} AS dst SET {} = src.{}::numeric * %s::numeric FROM ONLY {} AS src").format(
            target, column, sql.Identifier(declaration.source_column), declaration.source.identifier(),
        )
        match = sql.SQL(" AND dst.{key} = src.{key}").format(key=key)
        params = (declaration.multiplier, *bounds)
    fill += sql.SQL(" WHERE dst.{key} BETWEEN %s AND %s AND dst.{column} IS NULL").format(key=key, column=column)
    return ((add, ()), (fill + match, params))


def preview(connection, declaration):
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        connection.execute("SET LOCAL lock_timeout = '2s'")
        connection.execute("SET LOCAL statement_timeout = '10s'")
        return _inspect(connection, declaration)


def apply(connection, declaration, reviewed):
    if isinstance(declaration, ColumnAddition):
        return _apply_column_addition(connection, declaration, reviewed)
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


def _apply_column_addition(connection, declaration, reviewed):
    with connection.transaction():
        connection.execute("SET LOCAL lock_timeout = '2s'")
        connection.execute("SET LOCAL statement_timeout = '10s'")
        tables = [declaration.target]
        if declaration.source is not None:
            tables.append(declaration.source)
        for table in sorted(tables):
            mode = "ACCESS EXCLUSIVE" if table == declaration.target else "SHARE"
            connection.execute(sql.SQL("LOCK TABLE ONLY {} IN " + mode + " MODE").format(table.identifier()))
        if _inspect(connection, declaration) != reviewed:
            raise BackfillError("Preview is stale. Run apply again to review the current data.")
        if reviewed.blocked:
            raise BackfillError("Resolve blocked rows before applying.")
        expected = reviewed.expected
        if declaration.source is None:
            timestamp = connection.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0]
            expected = tuple((key, timestamp) for key, _ in reviewed.target.values)
        (add, add_params), (fill, fill_params) = column_addition_sql(declaration)
        connection.execute(add, add_params)
        result = connection.execute(fill, fill_params)
        target = _snapshot(connection, declaration.target, declaration, target=True, after_addition=True)
        added = (declaration.column, declaration.column_type, False, "", "", None)
        if (result.rowcount != reviewed.pending
                or target != Snapshot(reviewed.target.oid, (*reviewed.target.columns, added),
                                      reviewed.target.constraints, expected)):
            raise BackfillError("Post-update verification failed. The transaction was rolled back.")
        return result.rowcount

from collections import Counter
from dataclasses import dataclass, field

from psycopg import sql

from .backfill import BackfillError, MAX_KEYS, Snapshot, check_target_constraints, inspect_relation
from .expression import SCALAR_TYPES


@dataclass(frozen=True)
class Calculation:
    source: Snapshot | None
    target: Snapshot
    blocked: tuple[str, ...]
    column_type: str
    expected: tuple
    example: tuple | None = field(compare=False)
    transaction_time: bool = False
    correct: int = 0

    @property
    def pending(self):
        return len(self.target.values)


def configure(connection):
    connection.execute("SET LOCAL search_path = pg_catalog, pg_temp")
    connection.execute("SET LOCAL standard_conforming_strings = on")


def _target_range(operation):
    key = sql.Identifier("dst", operation.key)
    return sql.SQL("{} BETWEEN %s AND %s").format(key)


def _relation_columns(connection, table, relation, operation):
    types = dict(connection.execute(
        "SELECT attname, atttypid FROM pg_catalog.pg_attribute "
        "WHERE attrelid = %s AND attnum > 0 AND NOT attisdropped", (relation.oid,),
    ).fetchall())
    if types.get(operation.key) != 20:
        raise BackfillError(f"Column {table}.{operation.key} must be bigint.")
    return types


def _target_snapshot(connection, operation, column_type=None):
    target = inspect_relation(connection, operation.target)
    check_target_constraints(operation.target, target)
    types = _relation_columns(connection, operation.target, target, operation)
    if column_type is None and operation.column in types:
        raise BackfillError(f"Column {operation.target}.{operation.column} already exists.")
    if any(column[3] for column in target.columns):
        raise BackfillError(f"Use a target without generated columns: {operation.target}.")

    value = sql.SQL("NULL::bytea")
    if column_type is not None:
        actual_column = next((column for column in target.columns if column[0] == operation.column), None)
        if actual_column != (operation.column, column_type, False, "", "", None):
            raise BackfillError("Added column does not match the reviewed type and schema.")
        value = sql.SQL("pg_catalog.record_send(ROW({}))").format(sql.Identifier("dst", operation.column))
    statement = sql.SQL(
        "SELECT {key}, {value} FROM ONLY {target} AS dst WHERE {scope} ORDER BY {key} LIMIT %s"
    ).format(key=sql.Identifier("dst", operation.key), value=value,
             target=operation.target.identifier(), scope=_target_range(operation))
    rows = connection.execute(statement, (operation.start, operation.end, MAX_KEYS + 1)).fetchall()
    if len(rows) > MAX_KEYS:
        raise BackfillError(f"Too many scoped rows in {operation.target}.")
    return Snapshot(target.oid, target.columns, target.constraints, tuple(rows))


def inspect(connection, operation):
    database = connection.execute("SELECT pg_catalog.current_database()").fetchone()[0]
    if database != operation.database:
        raise BackfillError(f"Connected to database {database}, expected {operation.database}.")
    target = _target_snapshot(connection, operation)
    keys = [key for key, _ in target.values]
    blocked = [f"Duplicate target key {key}." for key, count in Counter(keys).items() if count > 1]
    expression = operation.expression.parameterized(connection)
    source = None
    inputs = sql.SQL("NULL::bytea")
    base = sql.SQL("FROM ONLY {} AS dst").format(operation.target.identifier())
    row_key = sql.Identifier("dst", operation.key)
    if operation.source is not None:
        source = inspect_relation(connection, operation.source)
        types = _relation_columns(connection, operation.source, source, operation)
        for field_name in operation.expression.columns:
            if field_name.startswith("pg_") and field_name not in types:
                raise BackfillError(f"Use a retained source column: {field_name}.")
            if field_name in {"ctid", "xmin", "xmax", "cmin", "cmax", "tableoid"}:
                raise BackfillError(f"Use a retained source column: {field_name}.")
            if field_name in types and types[field_name] not in SCALAR_TYPES:
                raise BackfillError(f"Unsupported source type for {operation.source}.{field_name}.")
        base = sql.SQL("FROM ONLY {} AS src").format(operation.source.identifier())
        row_key = sql.Identifier("src", operation.key)
        fields = sql.SQL(", ").join(sql.Identifier("src", name) for name in operation.expression.columns)
        inputs = sql.SQL("pg_catalog.record_send(ROW({}))").format(fields)

    # A SELECT output resolves unknown constants to text, just as the dbt projection does.
    projection = sql.SQL("SELECT {key} AS migreat_key, {inputs} AS migreat_inputs, ({expr}) AS migreat_value {base}").format(
        key=row_key, inputs=inputs, expr=expression, base=base,
    )
    shape = connection.execute(projection + sql.SQL(" LIMIT 0"), ()).pgresult
    oid, modifier = shape.ftype(2), shape.fmod(2)
    if oid not in SCALAR_TYPES:
        raise BackfillError("The added expression has an unsupported PostgreSQL result type.")
    column_type = connection.execute("SELECT pg_catalog.format_type(%s, %s)", (oid, modifier)).fetchone()[0]

    if source is not None:
        scoped_source = connection.execute(
            sql.SQL("SELECT {} {} WHERE {} = ANY(%s) ORDER BY 1 LIMIT %s").format(row_key, base, row_key),
            (keys, MAX_KEYS + 1),
        ).fetchall()
        if len(scoped_source) > MAX_KEYS:
            raise BackfillError(f"Too many matching rows in {operation.source}.")
        counts = Counter(key for key, in scoped_source)
        for key in sorted(set(keys)):
            if counts[key] != 1:
                label = "Missing source match for" if counts[key] == 0 else "Duplicate source"
                blocked.append(f"{label} key {key}.")

    expected = ()
    example = None
    if not blocked:
        rows = connection.execute(
            sql.SQL(
                "SELECT migreat_key, migreat_inputs, pg_catalog.record_send(ROW(migreat_value)), "
                "migreat_value::text FROM ({} WHERE {} = ANY(%s)) AS scoped ORDER BY 1"
            ).format(projection, row_key),
            (keys,),
        ).fetchall()
        if source is not None:
            source = Snapshot(source.oid, source.columns, source.constraints,
                              tuple((key, raw) for key, raw, _, _ in rows))
        expected = tuple((key, value) for key, _, value, _ in rows)
        if rows:
            example = (rows[0][0], rows[0][3])
    return Calculation(source, target, tuple(blocked), column_type, expected, example,
                       operation.expression.transaction_time)


def statements(connection, operation, column_type):
    column = sql.Identifier(operation.column)
    target = operation.target.identifier()
    add = sql.SQL("ALTER TABLE ONLY {} ADD COLUMN {} {}").format(target, column, sql.SQL(column_type))
    expression = operation.expression.parameterized(connection)
    source = sql.SQL("")
    match = sql.SQL("")
    if operation.source is not None:
        source = sql.SQL(" FROM ONLY {} AS src").format(operation.source.identifier())
        match = sql.SQL(" AND {} = {}").format(sql.Identifier("dst", operation.key), sql.Identifier("src", operation.key))
    fill = sql.SQL("UPDATE ONLY {} AS dst SET {} = CAST({} AS {}){} WHERE {}{}").format(
        target, column, expression, sql.SQL(column_type), source, _target_range(operation), match,
    )
    return ((add, ()), (fill, (operation.start, operation.end)))


def verified(connection, operation, checked):
    actual = _target_snapshot(connection, operation, checked.column_type)
    added = (operation.column, checked.column_type, False, "", "", None)
    original = checked.target
    return actual == Snapshot(original.oid, (*original.columns, added), original.constraints, checked.expected)

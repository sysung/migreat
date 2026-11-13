from dataclasses import dataclass

import psycopg
from psycopg import sql


class MigrationError(ValueError):
    pass


@dataclass(frozen=True)
class TableName:
    schema: str
    name: str

    def identifier(self) -> sql.Identifier:
        return sql.Identifier(self.schema, self.name)


@dataclass(frozen=True)
class Column:
    name: str
    data_type: str
    nullable: bool
    has_default: bool = False


@dataclass(frozen=True)
class DesiredTable:
    table: TableName
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class TableSnapshot:
    table: TableName
    oid: int
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class AddColumnPlan:
    starting: TableSnapshot
    column: Column

    def statement(self) -> sql.Composed:
        return sql.SQL("ALTER TABLE {} ADD COLUMN {} bigint;").format(
            self.starting.table.identifier(), sql.Identifier(self.column.name)
        )


@dataclass(frozen=True)
class NoChange:
    pass


def inspect(connection: psycopg.Connection, table: TableName) -> TableSnapshot:
    rows = connection.execute(
        """
        SELECT c.oid, c.relkind,
               EXISTS (SELECT 1 FROM pg_catalog.pg_inherits i
                       WHERE c.oid IN (i.inhrelid, i.inhparent)),
               a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod),
               NOT a.attnotnull, a.atthasdef
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_catalog.pg_attribute a
          ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
        WHERE n.nspname = %s AND c.relname = %s
        ORDER BY a.attnum
        """,
        (table.schema, table.name),
    ).fetchall()
    if not rows:
        raise MigrationError(f"Table {table.schema}.{table.name} does not exist.")
    oid, kind, inherits, *_ = rows[0]
    if kind != "r" or inherits:
        raise MigrationError("Use an ordinary table without partitions or inheritance.")
    columns = tuple(Column(*row[3:]) for row in rows if row[3] is not None)
    return TableSnapshot(table, oid, columns)


def build_plan(desired: DesiredTable, live: TableSnapshot) -> AddColumnPlan | NoChange:
    if desired.table != live.table:
        raise MigrationError("The contract and live snapshot refer to different tables.")
    expected = {column.name: column for column in desired.columns}
    actual = {column.name: column for column in live.columns}
    for name, column in actual.items():
        if name not in expected:
            raise MigrationError(f"Unexpected live column {name!r}. Reconcile the contract and table.")
        target = expected[name]
        if (column.data_type, column.nullable) != (target.data_type, target.nullable):
            raise MigrationError(f"Live type or nullability for {name!r} differs from the contract.")
    missing = [column for name, column in expected.items() if name not in actual]
    if not missing:
        return NoChange()
    if len(missing) != 1 or missing[0].data_type != "bigint" or not missing[0].nullable:
        raise MigrationError("The PoC supports exactly one missing nullable bigint column.")
    return AddColumnPlan(live, missing[0])


def apply(connection: psycopg.Connection, plan: AddColumnPlan) -> None:
    table = plan.starting.table
    with connection.transaction():
        connection.execute("SET LOCAL lock_timeout = '2s'")
        try:
            connection.execute(
                sql.SQL("LOCK TABLE ONLY {} IN ACCESS EXCLUSIVE MODE").format(table.identifier())
            )
            current = inspect(connection, table)
        except (psycopg.errors.UndefinedTable, MigrationError) as error:
            raise MigrationError("Plan is stale. Rerun apply to review the current schema.") from error
        except psycopg.errors.LockNotAvailable as error:
            raise MigrationError("Table lock timed out after two seconds. Rerun apply.") from error

        if current != plan.starting:
            raise MigrationError("Plan is stale. Rerun apply to review the current schema.")
        connection.execute(plan.statement())
        expected = TableSnapshot(table, current.oid, (*current.columns, plan.column))
        if inspect(connection, table) != expected:
            raise MigrationError("Post-apply schema differs from the reviewed plan. Transaction rolled back.")

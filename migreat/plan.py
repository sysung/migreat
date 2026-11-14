from dataclasses import dataclass

from psycopg import sql

from . import backfill, dbt_plan
from .backfill import ColumnAddition, Declaration, Preview
from .dbt import DbtAddition


@dataclass(frozen=True)
class Plan:
    operation: Declaration | ColumnAddition | DbtAddition
    inspection: Preview | dbt_plan.Calculation
    statements: tuple[tuple[sql.Composable, tuple], ...]


def _column_addition_sql(declaration):
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
        fill = sql.SQL("UPDATE ONLY {} AS dst SET {} = src.{}::pg_catalog.numeric OPERATOR(pg_catalog.*) %s::pg_catalog.numeric FROM ONLY {} AS src").format(
            target, column, sql.Identifier(declaration.source_column), declaration.source.identifier(),
        )
        match = sql.SQL(" AND dst.{key} = src.{key}").format(key=key)
        params = (declaration.multiplier, *bounds)
    fill += sql.SQL(" WHERE dst.{key} BETWEEN %s AND %s AND dst.{column} IS NULL").format(key=key, column=column)
    return ((add, ()), (fill + match, params))


def _existing_column_sql(declaration):
    key, column = map(sql.Identifier, (declaration.key, declaration.column))
    return ((
        sql.SQL(
            "UPDATE ONLY {target} AS dst SET {column} = src.{column} "
            "FROM ONLY {source} AS src "
            "WHERE dst.{key} = src.{key} AND dst.{key} BETWEEN %s AND %s "
            "AND dst.{column} IS NULL"
        ).format(target=declaration.target.identifier(), source=declaration.source.identifier(),
                 key=key, column=column),
        (declaration.start, declaration.end),
    ),)


def preview(connection, declaration):
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        connection.execute("SET LOCAL lock_timeout = '2s'")
        connection.execute("SET LOCAL statement_timeout = '10s'")
        if isinstance(declaration, DbtAddition):
            dbt_plan.configure(connection)
            calculation = dbt_plan.inspect(connection, declaration)
            statements = () if calculation.blocked else dbt_plan.statements(connection, declaration, calculation.column_type)
            return Plan(declaration, calculation, statements)
        inspection = backfill._inspect(connection, declaration)
        statements = ()
        if not inspection.blocked:
            statements = (_column_addition_sql(declaration) if isinstance(declaration, ColumnAddition)
                          else _existing_column_sql(declaration))
        return Plan(declaration, inspection, statements)

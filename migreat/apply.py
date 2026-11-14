from dataclasses import replace

from psycopg import sql

from . import backfill, dbt_plan
from .backfill import BackfillError, ColumnAddition, Snapshot
from .dbt import DbtAddition
from .plan import Plan


def apply(connection, plan: Plan):
    declaration = plan.operation
    reviewed = plan.inspection
    if reviewed.blocked:
        raise BackfillError("Resolve blocked rows before applying.")
    dbt = isinstance(declaration, DbtAddition)
    addition = isinstance(declaration, (ColumnAddition, DbtAddition))
    if not addition and not reviewed.pending:
        return 0

    with connection.transaction():
        connection.execute("SET LOCAL lock_timeout = '2s'")
        connection.execute("SET LOCAL statement_timeout = '10s'")
        if dbt:
            dbt_plan.configure(connection)
        target_mode = "ACCESS EXCLUSIVE" if addition else "SHARE ROW EXCLUSIVE"
        locks = [(declaration.target, target_mode)]
        if declaration.source is not None:
            locks.append((declaration.source, "SHARE"))
        for table, mode in sorted(locks):
            connection.execute(sql.SQL("LOCK TABLE ONLY {} IN {} MODE").format(
                table.identifier(), sql.SQL(mode),
            ))
        current = dbt_plan.inspect(connection, declaration) if dbt else backfill._inspect(connection, declaration)
        comparable = replace(current, expected=reviewed.expected) if dbt and current.transaction_time else current
        if comparable != reviewed:
            raise BackfillError("Preview is stale. Run apply again to review the current data.")

        expected = reviewed.expected
        if not dbt and declaration.source is None:
            timestamp = connection.execute("SELECT CURRENT_TIMESTAMP").fetchone()[0]
            expected = tuple((key, timestamp) for key, _ in reviewed.target.values)

        for statement, parameters in plan.statements:
            result = connection.execute(statement, parameters)

        if dbt:
            verified = dbt_plan.verified(connection, declaration, current)
        elif addition:
            actual = backfill._snapshot(connection, declaration.target, declaration, target=True, after_addition=True)
            added = (declaration.column, declaration.column_type, False, "", "", None)
            verified = actual == Snapshot(
                reviewed.target.oid, (*reviewed.target.columns, added), reviewed.target.constraints, expected,
            )
        else:
            actual = backfill._inspect(connection, declaration)
            verified = (
                not actual.pending and not actual.blocked
                and actual.source == reviewed.source
                and actual.target.oid == reviewed.target.oid
                and actual.target.columns == reviewed.target.columns
                and actual.target.constraints == reviewed.target.constraints
                and tuple(key for key, _ in actual.target.values) == tuple(key for key, _ in reviewed.target.values)
            )
        if result.rowcount != reviewed.pending or not verified:
            raise BackfillError("Post-update verification failed. The transaction was rolled back.")
        return result.rowcount

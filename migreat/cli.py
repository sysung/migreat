import argparse
import os
import sys
from pathlib import Path

import psycopg
import yaml

from .backfill import BackfillError, ColumnAddition, apply, column_addition_sql, load_declaration, preview
from .cutover import plan as plan_cutover


def main() -> int:
    parser = argparse.ArgumentParser(prog="migreat", description="Plan PostgreSQL table cutovers and run scoped backfills.")
    commands = parser.add_subparsers(dest="command", required=True)
    backfill = commands.add_parser("backfill", help="Fill historical values in a PostgreSQL column.")
    actions = backfill.add_subparsers(dest="action", required=True)
    for action, description in (("plan", "Preview the fill without writes."), ("apply", "Review and apply the fill.")):
        command = actions.add_parser(action, help=description, description=description)
        command.add_argument("declaration", type=Path)
    cutover = commands.add_parser("cutover", help="Review a replacement table cutover.")
    cutover_actions = cutover.add_subparsers(dest="action", required=True)
    cutover_plan = cutover_actions.add_parser("plan", help="Review SQL and assess supplied evidence.")
    cutover_plan.add_argument("declaration", type=Path)
    cutover_plan.add_argument("--evidence", type=Path)
    args = parser.parse_args()

    try:
        if args.command == "cutover":
            return plan_cutover(args.declaration, args.evidence)
        declaration = load_declaration(args.declaration)
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise BackfillError("Set DATABASE_URL to the target PostgreSQL database.")
        with psycopg.connect(dsn, autocommit=True) as connection:
            reviewed = preview(connection, declaration)
            addition = isinstance(declaration, ColumnAddition)
            print(f"Database: {declaration.database}")
            if declaration.source is not None:
                print(f"Source: {declaration.source}")
            print(f"Target: {declaration.target}.{declaration.column}")
            print(f"Range: {declaration.key} {declaration.start}-{declaration.end} (inclusive)")
            print(f"Pending: {reviewed.pending}, already correct: {reviewed.correct}, blocked: {len(reviewed.blocked)}")
            if addition:
                if declaration.source is None:
                    print("Historical fill: apply transaction start time")
                else:
                    print(f"Historical fill: {declaration.source_column} × {declaration.multiplier}")
                    if reviewed.expected:
                        key, value = reviewed.expected[0]
                        print(f"Example: {declaration.key} {key} → {value}")
                for statement, parameters in column_addition_sql(declaration):
                    print(statement.as_string(connection))
                    if parameters:
                        print("Parameters:", ", ".join(map(str, parameters)))
            if reviewed.blocked:
                raise BackfillError(f"Resolve blocked rows. {reviewed.blocked[0]}")
            if args.action == "plan" or (not addition and not reviewed.pending):
                return 0
            print("Confirm the daily writer is paused and drained and the updated job has yet to run.")
            try:
                confirmed = input("Type yes to apply: ").strip() == "yes"
            except (EOFError, KeyboardInterrupt):
                confirmed = False
            if not confirmed:
                print("\nCancelled.")
                return 0
            updated = apply(connection, declaration, reviewed)
            print(f"Updated and verified {updated} rows.")
    except psycopg.errors.LockNotAvailable:
        print("Error: Table lock timed out. Check that writers are paused and rerun.", file=sys.stderr)
        return 1
    except psycopg.OperationalError:
        print("Error: Database connection failed. Check DATABASE_URL and rerun plan to determine what remains.", file=sys.stderr)
        return 1
    except (BackfillError, OSError, psycopg.Error, yaml.YAMLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0

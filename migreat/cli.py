import argparse
import os
import sys
from pathlib import Path

import psycopg
import yaml

from .apply import apply
from .backfill import BackfillError, ColumnAddition, load_declaration
from .dbt import DbtAddition, DbtInput, UnsupportedAddition, load_operation
from .plan import preview


def main() -> int:
    parser = argparse.ArgumentParser(prog="migreat", description="Plan and apply scoped PostgreSQL migrations.")
    commands = parser.add_subparsers(dest="action", required=True)
    for action, description in (("plan", "Preview the change without writes."), ("apply", "Review and apply the change.")):
        command = commands.add_parser(action, help=description, description=description)
        command.add_argument("declaration", nargs="?", type=Path, help="YAML declaration")
        command.add_argument("--baseline", type=Path, help="Deployed compiled dbt manifest")
        command.add_argument("--candidate", type=Path, help="Proposed compiled dbt manifest")
        command.add_argument("--model", help="Exact dbt model ID")
        command.add_argument("--key", help="Historical match key")
        command.add_argument("--start", type=int, help="Inclusive first key")
        command.add_argument("--end", type=int, help="Inclusive last key")
    args = parser.parse_args()

    dbt_options = (args.baseline, args.candidate, args.model, args.key, args.start, args.end)
    uses_dbt = args.declaration is None
    if ((uses_dbt and any(value is None for value in dbt_options))
            or (not uses_dbt and any(value is not None for value in dbt_options))):
        parser.error("Use a YAML declaration or all six dbt options.")

    try:
        declaration = load_operation(DbtInput(*dbt_options)) if uses_dbt else load_declaration(args.declaration)
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise BackfillError("Set DATABASE_URL to the target PostgreSQL database.")
        with psycopg.connect(dsn, autocommit=True) as connection:
            try:
                plan = preview(connection, declaration)
            except (BackfillError, psycopg.Error):
                if uses_dbt:
                    print(f"+ {declaration.column}")
                raise
            reviewed = plan.inspection
            addition = isinstance(declaration, (ColumnAddition, DbtAddition))
            if uses_dbt:
                print(f"+ {declaration.column} {reviewed.column_type}")
            print(f"Database: {declaration.database}")
            if declaration.source is not None:
                print(f"Source: {declaration.source}")
            print(f"Target: {declaration.target}.{declaration.column}")
            print(f"Range: {declaration.key} {declaration.start}-{declaration.end} (inclusive)")
            print(f"Pending: {reviewed.pending}, already correct: {reviewed.correct}, blocked: {len(reviewed.blocked)}")
            if addition:
                if uses_dbt:
                    if declaration.expression.transaction_time:
                        print("Historical fill: evaluated at apply transaction start")
                    elif declaration.source is None:
                        print("Historical fill: same calculated value for every scoped row")
                    if reviewed.example is not None:
                        key, value = reviewed.example
                        label = "Illustrative example" if reviewed.transaction_time else "Example"
                        print(f"{label}: {declaration.key} {key} → {value if value is not None else 'NULL'}")
                elif declaration.source is None:
                    print("Historical fill: apply transaction start time")
                else:
                    print(f"Historical fill: {declaration.source_column} × {declaration.multiplier}")
                    if reviewed.expected:
                        key, value = reviewed.expected[0]
                        print(f"Example: {declaration.key} {key} → {value}")
                for statement, parameters in plan.statements:
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
            updated = apply(connection, plan)
            print(f"Updated and verified {updated} rows.")
    except UnsupportedAddition as error:
        print(f"+ {error.column}")
        print(f"Error: {error}", file=sys.stderr)
        return 1
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

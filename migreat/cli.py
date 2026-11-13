import argparse
import os
import sys
from pathlib import Path

import psycopg
import yaml

from .contract import load_contract
from .migration import MigrationError, NoChange, apply, build_plan, inspect


def main() -> int:
    parser = argparse.ArgumentParser(prog="migreat")
    parser.add_argument("command", choices=("plan", "apply"))
    parser.add_argument("contract", type=Path)
    args = parser.parse_args()

    try:
        desired = load_contract(args.contract)
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise MigrationError("Set DATABASE_URL to the target PostgreSQL database.")
        with psycopg.connect(dsn, autocommit=True) as connection:
            plan = build_plan(desired, inspect(connection, desired.table))
            if isinstance(plan, NoChange):
                print("No changes.")
                return 0
            print(f"Target: {desired.table.identifier().as_string(connection)}")
            print(plan.statement().as_string(connection))
            print("Existing rows will read NULL in the new column.")
            if args.command == "plan":
                return 0
            try:
                confirmed = input("Type yes to apply: ").strip() == "yes"
            except (EOFError, KeyboardInterrupt):
                confirmed = False
            if not confirmed:
                print("\nCancelled.")
                return 0
            apply(connection, plan)
            print("Applied and verified.")
    except (MigrationError, OSError, psycopg.Error, yaml.YAMLError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0

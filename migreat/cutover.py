import hashlib
import json
from datetime import UTC, datetime, timedelta

import yaml
from psycopg import sql

from .backfill import IDENTIFIER, BackfillError, DeclarationLoader, Table

COLUMN_TYPES = {"bigint", "numeric", "text", "date", "timestamptz", "boolean"}
DIFFERENCES = ("missing_keys", "extra_keys", "duplicate_keys", "value_mismatches")


def _read_mapping(path):
    data = yaml.load(path.read_text(), Loader=DeclarationLoader)
    if not isinstance(data, dict):
        raise BackfillError(f"Expected a mapping in {path}.")
    return data


def _identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise BackfillError("Use simple PostgreSQL column identifiers.")
    return sql.Identifier(value).as_string()


def _fresh_timestamp(value, now, limit):
    if not isinstance(value, str):
        return None
    try:
        observed = datetime.fromisoformat(value)
        if observed.utcoffset() == timedelta(0) and 0 <= (now - observed).total_seconds() <= limit:
            return observed
    except (ValueError, OverflowError):
        pass
    return None


def _assess(evidence, fingerprint, snapshot, limit):
    now = datetime.now(UTC)
    blockers = []
    if evidence.get("plan_sha256") != fingerprint:
        blockers.append("Evidence belongs to a different plan.")
    if any(evidence.get(field) != snapshot for field in
           ("old_build_snapshot", "replacement_build_snapshot", "comparison_snapshot")):
        blockers.append("Both builds and the keyed comparison must use the declared snapshot.")
    snapshot_at = _fresh_timestamp(evidence.get("snapshot_at"), now, limit)
    compared_at = _fresh_timestamp(evidence.get("compared_at"), now, limit)
    if snapshot_at is None or compared_at is None:
        blockers.append("Provide fresh UTC snapshot and comparison times.")
    elif compared_at < snapshot_at:
        blockers.append("The comparison was recorded before the snapshot was captured.")
    if any(type(evidence.get(field)) is not int or evidence[field] != 0 for field in DIFFERENCES):
        blockers.append("The comparison must report zero missing, extra, duplicate, and mismatched keys or values.")
    if evidence.get("rollback_ready") is not True:
        blockers.append("Confirm that the old table can serve readers if routing is reversed.")
    return blockers


def plan(declaration_path, evidence_path):
    declaration = _read_mapping(declaration_path)
    if set(declaration) - {
        "mode", "database", "snapshot", "reader_owner", "old_table",
        "replacement_table", "freshness_seconds", "columns", "key",
    }:
        raise BackfillError("Unknown cutover declaration fields.")
    mode = declaration.get("mode")
    if mode != "full_refresh":
        raise BackfillError("Unsupported cutover mode. Use full_refresh.")
    for field in ("database", "snapshot", "reader_owner"):
        value = declaration.get(field)
        if not isinstance(value, str) or not value.strip() or not value.isprintable():
            raise BackfillError(f"Declare a nonempty {field}.")
    old = Table.parse(declaration.get("old_table"))
    replacement = Table.parse(declaration.get("replacement_table"))
    limit = declaration.get("freshness_seconds")
    if old == replacement or type(limit) is not int or limit <= 0:
        raise BackfillError("Use distinct tables and a positive integer freshness_seconds.")
    columns = declaration.get("columns")
    if not isinstance(columns, dict) or not columns:
        raise BackfillError("Declare at least one output column.")
    key = declaration.get("key")
    if not isinstance(key, str) or key not in columns:
        raise BackfillError("Declare a key from the output columns.")

    definitions = []
    projections = []
    blockers = []
    for name, column in columns.items():
        output = _identifier(name)
        if not isinstance(column, dict) or set(column) - {"type", "source", "divide_by"}:
            raise BackfillError(f"Invalid declaration for column {name}.")
        kind = column.get("type")
        if not isinstance(kind, str) or kind not in COLUMN_TYPES:
            raise BackfillError(f"Unsupported PostgreSQL type for {name}.")
        source = column.get("source")
        divisor = column.get("divide_by")
        definitions.append(f"{output} {kind}" + (" PRIMARY KEY" if name == key else ""))
        if divisor is not None and (type(divisor) is not int or divisor <= 0 or kind != "numeric" or name == key):
            raise BackfillError("Use a positive integer divisor on a numeric non-key column.")
        if source is None:
            blockers.append(f"{name} requires a retained source field.")
            projections.append(f"{output} <- unavailable")
            continue
        quoted = _identifier(source)
        expression = f"{quoted}::numeric / {divisor}" if divisor is not None else quoted
        projections.append(f"{expression} AS {output}")

    ordered_plan = {**declaration, "columns": list(columns.items())}
    fingerprint = hashlib.sha256(json.dumps(ordered_plan, sort_keys=True).encode()).hexdigest()
    if evidence_path is None:
        blockers.append("Supply a cutover evidence file.")
    else:
        blockers.extend(_assess(_read_mapping(evidence_path), fingerprint, declaration["snapshot"], limit))

    print(f"Database: {declaration['database']}")
    print(f"Old table: {old}")
    print(f"Input snapshot: {declaration['snapshot']}")
    print(f"Plan SHA-256: {fingerprint}")
    print(f"1. Review replacement DDL: CREATE TABLE {replacement.identifier().as_string()} ({', '.join(definitions)});")
    print(f"2. Build from the declared snapshot using these projections: {', '.join(projections)}")
    print(f"3. Compare keys ({key}) and expected values through the same input snapshot.")
    print(f"4. Have {declaration['reader_owner']} recheck freshness and switch readers after review.")
    print("5. Keep the old table available and current for rollback. Verify before routing back.")
    if blockers:
        print("Readiness: blocked")
        for blocker in blockers:
            print(f"- {blocker}")
        return 1
    print("Readiness: supplied evidence supports the reader switch.")
    return 0

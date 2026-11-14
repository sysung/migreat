import json
from dataclasses import dataclass
from pathlib import Path

from pglast import ast, parse_sql
from pglast.parser import ParseError

from .backfill import IDENTIFIER, BackfillError, Table, validate_scope
from .expression import Expression, compile_expression


@dataclass(frozen=True)
class DbtInput:
    baseline: Path
    candidate: Path
    model: str
    key: str
    start: int
    end: int


class UnsupportedAddition(BackfillError):
    def __init__(self, column, reason):
        super().__init__(reason)
        self.column = column


def _compiled_model(path, model_id):
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        raise BackfillError(f"Invalid dbt manifest {path}: {error}") from error
    metadata = manifest.get("metadata") if isinstance(manifest, dict) else None
    if not isinstance(metadata, dict) or metadata.get("adapter_type") != "postgres":
        raise BackfillError(f"Use a compiled PostgreSQL dbt manifest: {path}.")
    nodes = manifest.get("nodes")
    model = nodes.get(model_id) if isinstance(nodes, dict) else None
    if (not isinstance(model, dict) or model.get("resource_type") != "model"
            or model.get("unique_id") != model_id):
        raise BackfillError(f"Model {model_id} was not found in {path}.")
    relation = model.get("relation_name")
    code = model.get("compiled_code")
    if not isinstance(code, str) or not code.strip():
        raise BackfillError(f"Model {model_id} has no compiled SQL in {path}.")
    if not isinstance(relation, str) or not relation:
        raise BackfillError(f"Model {model_id} has no target relation in {path}.")
    target_query = _direct_select(f"SELECT id FROM {relation}")
    target = target_query.fromClause[0]
    if target.alias or len(target_query.targetList) != 1:
        raise BackfillError(f"Model {model_id} has an invalid target relation in {path}.")
    database = model.get("database")
    if target.catalogname not in (None, database):
        raise BackfillError(f"Model {model_id} has inconsistent target database metadata in {path}.")
    return database, Table(target.schemaname, target.relname), _direct_select(code)


def _direct_select(code):
    try:
        statements = parse_sql(code)
    except ParseError as error:
        raise BackfillError(f"Invalid compiled PostgreSQL SQL: {error}") from error
    if len(statements) != 1 or not isinstance(statements[0].stmt, ast.SelectStmt):
        raise BackfillError("Use a single compiled SELECT for each dbt model.")
    query = statements[0].stmt
    if (not query.targetList or not query.fromClause or len(query.fromClause) != 1
            or not isinstance(query.fromClause[0], ast.RangeVar)
            or query != ast.SelectStmt(
                targetList=query.targetList, fromClause=query.fromClause,
                op=0, limitOption=0, all=False, groupDistinct=False,
            )):
        raise BackfillError("Use an unfiltered direct table read with explicit projections.")
    source = query.fromClause[0]
    if (not source.schemaname or not IDENTIFIER.fullmatch(source.schemaname)
            or not IDENTIFIER.fullmatch(source.relname) or (source.alias and source.alias.colnames)):
        raise BackfillError("Use simple, schema-qualified table names with no column aliases on the relation.")
    return query


def _field(expression, source):
    if not isinstance(expression, ast.ColumnRef):
        return None
    fields = _names(expression.fields)
    if not fields:
        return None
    qualifier = (source.alias.aliasname,) if source.alias else (source.relname,)
    qualified = (qualifier,) if source.alias else (qualifier, (source.schemaname, source.relname))
    if fields[:-1] in ((), *qualified):
        return fields[-1]
    return None


def _names(nodes):
    return tuple(node.sval for node in nodes) if all(isinstance(node, ast.String) for node in nodes) else ()


def _projection_names(query):
    source = query.fromClause[0]
    names = tuple(item.name or _field(item.val, source) for item in query.targetList)
    if (any(name is None for name in names) or len(set(names)) != len(names)
            or any(item.indirection for item in query.targetList)):
        raise BackfillError("Use explicit projections with distinct output names.")
    return names


@dataclass(frozen=True)
class DbtAddition:
    database: str
    target: Table
    source: Table | None
    key: str
    column: str
    start: int
    end: int
    expression: Expression


def load_operation(inputs: DbtInput) -> DbtAddition:
    baseline_db, baseline_target, baseline = _compiled_model(inputs.baseline, inputs.model)
    database, target, candidate = _compiled_model(inputs.candidate, inputs.model)
    if (baseline_db, baseline_target) != (database, target):
        raise BackfillError("The baseline and candidate must target the same PostgreSQL table.")
    source = candidate.fromClause[0]
    if candidate.fromClause != baseline.fromClause or source.catalogname not in (None, database):
        raise BackfillError("Both models must read the same direct source in the target database.")

    existing = _projection_names(baseline)
    names = _projection_names(candidate)
    added = set(names) - set(existing)
    if len(added) != 1 or tuple(name for name in names if name not in added) != existing:
        raise BackfillError("The candidate must add exactly one column and preserve existing outputs.")
    column = added.pop()
    position = names.index(column)
    if candidate.targetList[:position] + candidate.targetList[position + 1:] != baseline.targetList:
        raise BackfillError("The candidate changed an existing projection.")
    existing_fields = tuple(_field(item.val, source) for item in baseline.targetList)
    if None in existing_fields:
        raise UnsupportedAddition(column, "Existing outputs must be direct fields from the source table.")
    if inputs.key not in existing or existing_fields[existing.index(inputs.key)] != inputs.key:
        raise UnsupportedAddition(column, "The model must project the historical key directly under the same name.")

    try:
        validate_scope(database, inputs.key, column, inputs.start, inputs.end)
        expression = compile_expression(candidate.targetList[position].val, lambda field: _field(field, source))
    except (BackfillError, RecursionError) as error:
        raise UnsupportedAddition(column, str(error)) from error
    # TODO: Warn when a row-independent value may misrepresent historical rows.
    retained_source = Table(source.schemaname, source.relname) if expression.columns else None
    if retained_source == target:
        raise UnsupportedAddition(column, "Use distinct source and target tables for a keyed calculation.")
    return DbtAddition(database, target, retained_source, inputs.key, column,
                       inputs.start, inputs.end, expression)

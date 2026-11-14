from dataclasses import dataclass
from typing import Callable

from pglast import ast
from psycopg import sql

from .backfill import BackfillError

# Only built-in scalar types can participate in operator and cast resolution.
SCALAR_TYPES = {
    16: "bool", 20: "int8", 21: "int2", 23: "int4", 25: "text",
    700: "float4", 701: "float8", 1042: "bpchar", 1043: "varchar",
    1082: "date", 1083: "time", 1114: "timestamp", 1184: "timestamptz",
    1186: "interval", 1266: "timetz", 1700: "numeric",
}
OPERATORS = {"+", "-", "*", "/", "%", "^", "=", "<>", "!=", "<", "<=", ">", ">=", "||"}


@dataclass(frozen=True)
class Expression:
    sql: sql.Composable
    columns: tuple[str, ...]
    transaction_time: bool

    def parameterized(self, connection):
        # Literal text can contain percent signs, independent of the bound key range.
        return sql.SQL(self.sql.as_string(connection).replace("%", "%%"))


def compile_expression(node, resolve_field: Callable[[ast.ColumnRef], str | None]) -> Expression:
    columns = {}
    transaction_time = False

    def render(value):
        nonlocal transaction_time
        if isinstance(value, ast.ColumnRef):
            field = resolve_field(value)
            if field is not None:
                columns[field] = None
                return sql.Identifier("src", field)
        elif isinstance(value, ast.A_Const):
            if value.isnull:
                return sql.SQL("NULL")
            if isinstance(value.val, ast.String):
                return sql.Literal(value.val.sval)
            if isinstance(value.val, ast.Integer):
                return sql.SQL(str(value.val.ival))
            if isinstance(value.val, ast.Float):
                return sql.SQL(value.val.fval)  # Original numeric token from the PostgreSQL parser.
            if isinstance(value.val, ast.Boolean):
                return sql.SQL("TRUE" if value.val.boolval else "FALSE")
        elif isinstance(value, ast.A_Expr) and value.kind == 0:
            names = tuple(part.sval for part in value.name or ())
            if len(names) == 1 and names[0] in OPERATORS:
                operator = sql.SQL("OPERATOR(pg_catalog.{})").format(sql.SQL(names[0]))
                left = render(value.lexpr) if value.lexpr is not None else sql.SQL("")
                if value.lexpr is not None or names[0] in {"+", "-"}:
                    return sql.SQL("({} {} {})").format(left, operator, render(value.rexpr))
        elif isinstance(value, ast.TypeCast):
            cast = value.typeName
            names = tuple(part.sval for part in cast.names or ())
            if (names and names[:-1] in ((), ("pg_catalog",))
                    and names[-1] in SCALAR_TYPES.values()
                    and not (cast.arrayBounds or cast.setof or cast.pct_type) and cast.typemod == -1):
                modifiers = tuple(cast.typmods or ())
                if all(isinstance(item, ast.A_Const) and isinstance(item.val, ast.Integer)
                       for item in modifiers):
                    name = sql.Identifier("pg_catalog", names[-1])
                    if modifiers:
                        name += sql.SQL("({})").format(sql.SQL(", ").join(map(render, modifiers)))
                    return sql.SQL("CAST({} AS {})").format(render(value.arg), name)
        elif isinstance(value, ast.CoalesceExpr):
            return sql.SQL("COALESCE({})").format(sql.SQL(", ").join(map(render, value.args)))
        elif isinstance(value, ast.CaseExpr):
            subject = sql.SQL("") if value.arg is None else render(value.arg)
            cases = sql.SQL(" ").join(
                sql.SQL("WHEN {} THEN {}").format(render(item.expr), render(item.result))
                for item in value.args
            )
            default = sql.SQL("NULL") if value.defresult is None else render(value.defresult)
            return sql.SQL("CASE {} {} ELSE {} END").format(subject, cases, default)
        elif isinstance(value, ast.BoolExpr):
            if value.boolop.name == "NOT_EXPR":
                return sql.SQL("(NOT {})").format(render(value.args[0]))
            operator = sql.SQL(" AND " if value.boolop.name == "AND_EXPR" else " OR ")
            return sql.SQL("({})").format(operator.join(map(render, value.args)))
        elif isinstance(value, ast.NullTest) and not value.argisrow:
            predicate = sql.SQL("IS NULL" if value.nulltesttype.name == "IS_NULL" else "IS NOT NULL")
            return sql.SQL("({} {})").format(render(value.arg), predicate)
        elif isinstance(value, ast.SQLValueFunction):
            clock = value.op.name
            if clock == "SVFOP_CURRENT_TIMESTAMP":
                transaction_time = True
                return sql.SQL("CURRENT_TIMESTAMP")
            if clock == "SVFOP_CURRENT_TIMESTAMP_N":
                transaction_time = True
                return sql.SQL("CURRENT_TIMESTAMP({})").format(sql.SQL(str(value.typmod)))
        raise BackfillError(f"Unsupported historical calculation: {type(value).__name__}.")

    rendered = render(node)
    return Expression(rendered, tuple(columns), transaction_time)

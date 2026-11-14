# Design

## Context

The installed entry point is `migreat.cli:main`. Backfill already has live snapshot inspection, two write paths, and a shared column-addition SQL builder. The CLI interprets the preview and runs confirmation. Offline table cutover is dispatched separately. The existing integration suite invokes the nested command and includes a rollback test that calls the old Python functions directly.

## Goals / Non-Goals

**Goals.** Give plan and apply explicit owners and drive both from one reviewed result. Reuse the existing PostgreSQL protections for YAML and the first dbt-derived column addition.

**Non-goals.** Arbitrary compiled SQL execution, offline mode, persisted plans, dbt execution, and orchestration of table replacement are outside this design.

## Decisions

- `cli.py` owns arguments, rendering, confirmation, and exit status. Both commands accept either a positional YAML path or a mutually exclusive dbt input group. Use `--baseline`, `--candidate`, `--model`, `--key`, `--start`, and `--end` as the proposed flag spellings. Select by exact manifest model ID for the first version. Use `DATABASE_URL` and validate the connected database against the input relation or YAML declaration.
- `plan.py` owns the read-only transaction and reviewed result. Build ordered SQL and bound parameters once. Carry the normalized operation, blockers, review details, and the snapshot needed for apply. Keep snapshot and row checks in `backfill.py`. Keep dbt-specific input parsing and SQL comparison together so YAML planning has no dbt handling.
- Compare compiled SQL with a PostgreSQL-aware parser. Require a supported direct-source SELECT with explicit projections. Compare the old query to the candidate after removing the one addition, including source, filters, and other row-selection clauses. Compare resolved relation identities and preserve identifier folding and quoting. For the first version require an unfiltered direct table read. Block wildcards, joins, CTEs, filters, grouping, deduplication, limits, and other row-shaping clauses. An unchanged filter could still make the candidate's source selection differ from the backfill's historical key range. Use the baseline chosen by the operator as evidence of the deployed model.
- Represent a dbt column addition by its parsed calculation, retained input columns, and PostgreSQL result type. Compose supported scalar operations recursively so arithmetic, casts, comparisons, CASE, and COALESCE can be combined. Render admitted AST nodes with fixed SQL syntax, quoted identifiers and PostgreSQL-compatible literal typing. Limit operators, casts and operand types to approved PostgreSQL built-ins and control name resolution with an explicit PostgreSQL search path that places temporary objects last. Preserve unknown literal resolution and account for psycopg percent placeholders. Use the same resolved calculation for read-only evaluation and the reviewed backfill SQL. Legacy YAML policies enter the same planning and apply flow through their existing inputs.
- Resolve result type and applicable type modifiers from PostgreSQL result metadata, even for an empty target range. Check source match cardinality separately from result values so a matched row can legitimately yield NULL. Use PostgreSQL for result typing and expected values. Propagate native PostgreSQL diagnostics for admitted expressions. Report a blocker for SQL whose dependencies, type, or execution cannot be safely established.
- Classify expressions without column dependencies separately from keyed fills. Report whether the value is constant or evaluated at the write transaction's start. Track transaction-time dependence independently of column dependence so a calculation can use both. Show time-dependent previews as illustrative. Exclude the changing clock value from drift comparison and derive the final expected value inside the confirmed transaction. Add an inline TODO at classification to warn when historical values may differ from what the operator expects.
- `apply.py` owns the write transaction. After literal confirmation, apply sets timeouts, acquires locks in sorted table order, rechecks full scoped state, executes the plan's statements and parameters, and verifies the outcome before commit. Both modes use SHARE for a distinct source. The target uses SHARE ROW EXCLUSIVE for an existing fill and ACCESS EXCLUSIVE for an addition. Preserve operation-specific postconditions, compute expected timestamp values in the write transaction, and preserve the distinction between a completed fill and an empty-scope addition.
- Keep the existing YAML backfill models and loader in `backfill.py`. Removing `cutover.py` leaves one consumer for their declaration rules. Keep `__init__.py` as the package marker.

## Risks / Trade-offs

- A SQL text diff can misread formatting, aliases, or a changed query. Use a structured comparison and fail closed when the selected query cannot be matched.
- Read-only mode alone does not make arbitrary SQL safe to run. Generate the probe from a narrow set of parsed identifiers and expressions. Qualify built-in type and operator resolution where needed and use the existing timeouts and scoped row limits.
- The command names change for existing operators and CI fixtures. Update documented invocations and release notes. Mechanically migrate existing test call sites and keep their scenarios and assertions intact. The open `publish-tagged-python-releases` change modifies the same installation requirement and still names the old command. Reconcile that delta before whichever change is archived second.
- A plan can stale while the prompt is open. Compare table identity, metadata, and all participating input values under locks before executing the reviewed statements. A compensating input change can leave the calculation unchanged. Verify keyed results using null-safe PostgreSQL equality or an equivalent representation. Evaluate transaction-time expectations inside the confirmed transaction.

## Migration Plan

Move YAML users to the new command names with the same declaration files. Document the dbt manifest flags with a one-column example. Keep historical OpenSpec archives intact. Full replacement remains the deployment owner's workflow. Apply failures roll back the write transaction. A successfully committed schema change requires a separate database change to reverse it.

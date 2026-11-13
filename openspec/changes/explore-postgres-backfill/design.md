# Design

## Context

db-test's old dbt projection returns only `id`. Its enriched projection returns `id` and `amount_cents`, and its append strategy reads IDs above the live maximum. With `on_schema_change: fail`, the old job can fail after the column is added. The current ODCS CLI performs schema changes and has no data fill.

## Goals / Non-Goals

**Goals**

- Prove one bounded, in-place fill in a paused daily batch workflow, then run the existing enriched dbt command.
- Keep preview and confirmation in the CLI and make retry safe after an ambiguous result.

**Deferred scope**

- Deploy-first workflows, streaming, and full-refresh models. A rebuild computes history from its revised SQL and can replace values written by an in-place fill.
- SQL expression inputs, table rewrites, resumable multi-transaction batches, and scheduler integration.

## Decisions

### One release order

1. Pause the old schedule and wait for active jobs to finish. Freeze changes to retained input during the fill.
2. Prepare the nullable destination column via the existing database deployment process. Use reviewed fixture SQL in the rehearsal. Keeping DDL outside the fill avoids holding an exclusive DDL lock during data validation and gives the CLI one behavior for both new and existing columns.
3. Preview the bounded backfill, then apply and verify it.
4. Deploy the enriched daily job and resume scheduling after its first successful run. If the fill fails, keep the schedule paused and fix or retry it. If the enriched build fails, keep the verified fill and retry the build. The old projection may fail on the expanded schema.

```sh
migreat backfill plan backfills/orders-amount-cents.yaml
migreat backfill apply backfills/orders-amount-cents.yaml
# Review the summary, then type yes.
dbt build --select orders --vars '{enriched: true}'
```

Apply shows the expected database, tables, range, and row counts, and asks the operator to confirm the writer is paused and drained and the updated job has yet to run. The CLI can validate the live database and prerequisites. Apply builds its own live preview, so a previous plan invocation is never treated as approval. Release order is an operator assertion because PostgreSQL cannot establish which dbt revision ran. In the demo, withhold the enriched invocation until verification succeeds. A full refresh needs its own SQL to recreate the historical values. [dbt incremental models](https://docs.getdbt.com/docs/build/incremental-models)

### Keep the runtime small

Use `cli.py` for argparse, environment, output, and confirmation. Put declaration parsing, planning, and the PostgreSQL transaction in `backfill.py`. Retain `__init__.py`. Reuse the useful catalog and identifier validation patterns from `migration.py` and `contract.py` in the new path, then remove the old modules, bundled ODCS JSON, package-data rule, and jsonschema dependency. The existing psycopg and PyYAML dependencies suffice. The alternative of retaining both CLI paths would preserve compatibility and carry two distinct operations in this PoC. The replacement is a breaking change and needs a clean-install check.

### Bound and verify the data change

Require a strict YAML mapping with expected database name, schema-qualified source and target, shared bigint key, shared value column with a nullable bigint destination, and inclusive integer bounds. Reject identical source and target tables and a value column equal to the key. The source value type is bigint and every scoped source value must be non-NULL. Limit the interval to 1,000 possible keys and cap each scoped read at 1,001 rows so excess matches fail explicitly. Require a nonempty target scope. Define scope as existing target rows within the range and require exactly one matching source row per target key. Allow sparse IDs. In the fixture, assert all ten expected IDs explicitly to demonstrate preservation.

Use a consistent read-only preview of target identity, schema, scoped key/value pairs and source matches. End the preview transaction before prompting. Report pending, already-correct, and blocked rows. Refuse duplicate scoped keys, missing matches, mismatched populated values, unsupported relation features such as triggers or rules, and invalid or wrong-target input. Compose identifiers safely and bind bounds as values.

After confirmation, use a short lock timeout and statement timeout. Acquire write-excluding table locks in consistent order and recheck the preview, including scoped values, before the update. Update only NULL values on the selected rows and verify key and value coverage before committing. Exclude generated target columns and policies or other relation features that can hide or change rows from this slice. Keep the input source intact. [PostgreSQL UPDATE](https://www.postgresql.org/docs/17/sql-update.html) · [PostgreSQL locking](https://www.postgresql.org/docs/17/explicit-locking.html)

## Risks / Trade-offs

- Locks block concurrent writes. The small fixed bound, short timeouts, and quiet batch window keep this a bounded experiment.
- A single transaction rolls back on error. If the CLI loses the result after commit, a new preview reports zero pending rows when the desired values are present.
- The expected database name catches common configuration errors. The connection settings still identify the server, and the operator verifies the intended environment before confirming.

## Migration Plan

Replace the ODCS quickstart, fixture, and integration tests with the backfill equivalents. Check wheel and Docker CLI entry points and ensure stale local build outputs do not repackage deleted files. Run the dbt rehearsal using a fresh disposable Compose project and PostgreSQL volume. The sibling db-test Compose file and README are the only current callers of its ODCS fixture. In the sibling update, switch the read-only mount to the backfill declaration, replace the old commands with reviewed fixture DDL and the new CLI, then delete the obsolete contracts directory.

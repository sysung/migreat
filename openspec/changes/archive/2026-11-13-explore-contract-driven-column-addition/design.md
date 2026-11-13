# Design

## Context

See [proposal.md](proposal.md) for the scope. The project began as a universal declarative SQL migration tool with dbt as a possible first audience. Discovery broadened to portable data contracts, then narrowed the first experiment to a single additive change on a free, local, open-source engine. PostgreSQL is the working candidate. It led database usage among respondents to the [2026 Stack Overflow Developer Survey](https://survey.stackoverflow.co/2026/technology/data/databases), and a populated local table can exercise DDL locks, transactions, and backfill retries.

## Goals / Non-Goals

**Goals**

- Validate whether a contract and a small amount of explicit intent produce a better review and rollout than hand-written SQL.
- Keep ordinary changes simple. A nullable addition with no historical fill should produce one schema step. A data update should appear only when the requested outcome requires it.
- Show which guarantees PostgreSQL enforces and which depend on a point-in-time validation query.

**Deferred scope**

Multi-engine execution, dbt and Terraform integration, rename, drop, recalculation of existing columns, and production-scale performance claims.

## PoC implementation decision

The first implementation covers the nullable add only. The CLI validates a single ODCS 3.2.0 document and compares it with the live catalog. It holds the reviewed plan in memory across the confirmation prompt. A two-second lock timeout bounds the wait to recheck table identity and schema, apply the change, and verify the result in one transaction. The constant-default and backfill variants below describe follow-up research.

## Decisions

### Evaluate ODCS before adding a contract format

Use one existing table and two revisions of an ODCS document. Pin the ODCS schema version during the experiment. Validate each document against its published JSON Schema. Evaluate how `schema` and `properties`, `logicalType`, optional `physicalType`, and `required` map to the PostgreSQL catalog. Also test whether a quality assertion can be surfaced as a deployment check without implying ongoing enforcement. Reject unsupported or ambiguous mappings for the managed field.

ODCS describes the intended state. Propose keeping operation-specific choices in a companion migration declaration keyed to the contract and target revision. Compare this with an ODCS custom-property extension. A companion declaration keeps normal contract readers interoperable and makes the temporary rollout choices easy to review. Those choices include whether to fill history, the SQL expression, eligible rows, and the validation condition. Avoid requiring users to write dialect-specific DDL for routine changes. [ODCS schema reference](https://bitol-io.github.io/open-data-contract-standard/latest/schema/) · [ODCS repository and license](https://github.com/bitol-io/open-data-contract-standard)

### Plan from the live schema

```text
ODCS desired state + explicit fill intent + live catalog
                          |
                          v
         Review SQL, target, preconditions and effects
                          |
                          v
       Recheck live state --> add column --> optional fill
                                                |
                                                v
                                     Verify contract and data
```

Resolve the table, normalize supported types, compare relevant live and desired fields, and produce a deterministic plan. Show the target, expected starting schema, SQL, lock implications, historical scope, and validation queries. An exact match yields no DDL. An incompatible same-name column or unexpected change to managed fields blocks apply. For a data fill, show the planned key range and an estimated row count when available, with estimates labeled separately from execution results.

Tie execution to the reviewed plan and check its preconditions again inside the transaction that protects the schema change. Keep the DDL transaction short with a bounded lock wait. Commit schema and data work separately so a long backfill does not hold the DDL lock. Re-read the catalog and check the data postconditions before reporting success. [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)

### Exercise three versions of the same addition

1. **Nullable, no historical fill.** Add `orders.amount_cents` as a nullable `bigint` in a fixture with existing rows. Existing rows read NULL. The plan contains no UPDATE.
2. **Same value for history and new inserts.** In a separate fixture run, use a constant default when that is the intended meaning. PostgreSQL can expose a nonvolatile default to existing rows without a table rewrite. A default added later affects future writes and does not fill history. [PostgreSQL modifying tables](https://www.postgresql.org/docs/current/ddl-alter.html)
3. **Derived historical values.** Add the column nullable, then populate it using explicit SQL derived from an existing source column. Assume a stable primary key, a deterministic expression, and a non-null source for the fixture. Capture a bounded historical key range after the writer can supply the new field for incoming rows, or pause fixture writes. Run ordered key ranges in short transactions. Update only eligible rows that still need the value so a retry does not overwrite values already written. For this fixture, `amount_cents IS NULL` works because NULL cannot be a valid completed result. Commit each batch and its progress together, then verify both coverage and values. For future required fields, validate the historical rows and coordinate the writer before tightening nullability.

A rerun after the column is added must still report a pending backfill until it is verified. An interruption between batches should resume with the completed rows preserved. If validation fails, keep the additive column in place and report the failed check. Recovery for the local experiment is a fixture reset or a reviewed forward correction. Automatic column deletion would discard values already written.

## Risks / Trade-offs

- Adding a column can still wait on a PostgreSQL table lock even when the operation avoids a rewrite. Report lock contention separately from backfill time.
- Backfills write data and can generate WAL and table bloat. Chunking bounds each transaction and makes retries practical. The amount of history the user chooses drives total work. Mutable source values and concurrent writers need a consistency policy beyond the controlled fixture.
- Strict open source is a project requirement. Atlas Community is Apache 2.0, with some planning commands and drivers in other editions. Use it and Apache-2.0 pgschema as comparison points. The core workflow must work without commercial dependencies or paid services. [Atlas editions](https://atlasgo.io/community-edition) · [pgschema](https://github.com/pgplex/pgschema)
- dbt can handle simple additions with `append_new_columns`, but its schema-change settings do not backfill existing rows. Contracts and model versions govern output compatibility. dbt-osmosis already compares desired and live schema and emits migration SQL. These are credible alternatives for dbt teams. Practitioner reports describe useful additive behavior and expensive historical work, with frequency and willingness to adopt a tool still unmeasured. [dbt incremental models](https://docs.getdbt.com/docs/build/incremental-models) · [dbt model contracts](https://docs.getdbt.com/docs/mesh/govern/model-contracts) · [dbt-osmosis CLI](https://z3z1ma.github.io/dbt-osmosis/docs/reference/cli/) · [Backfill discussion](https://www.reddit.com/r/dataengineering/comments/1e7jsfr)
- One engine tests the workflow. A later adapter comparison can test PostgreSQL against MySQL/MariaDB, SQLite, or an analytics stack. BigQuery, Snowflake, Databricks/Delta, and Iceberg/Hive remain portability research. Track table format and execution engine together where relevant, and distinguish connection, introspection, planning, and tested execution. [Delta column mapping](https://docs.databricks.com/aws/en/tables/features/column-mapping) · [Iceberg evolution](https://iceberg.apache.org/docs/latest/evolution/) · [Hive DML](https://hive.apache.org/docs/latest/language/languagemanual-dml/) · [Snowflake DCM](https://docs.snowflake.com/en/user-guide/dcm-projects/dcm-projects-overview)
- Future rename needs an explicit identity mapping and consumer compatibility decision. Future drop needs a deprecation window where appropriate, dependency coverage, explicit approval for the reviewed action, and a recovery story. Future recalculation needs versioned SQL, historical scope, cost estimates, validation, and cutover coordination.
- Terraform can expose the plan and trigger execution later. Keep one writer for each managed schema and keep backfill progress separate from Terraform resource state. dbt integration likewise needs explicit ownership of model and source relations. [Terraform plan modification](https://developer.hashicorp.com/terraform/plugin/framework/resources/plan-modification) · [Atlas Terraform precedent](https://atlasgo.io/integrations/terraform/declarative)

## Open Questions

- Does standard ODCS represent the sample contract cleanly? Compare a companion declaration and custom properties using an actual validated fixture.
- Does the contract-based approach improve review, stale-plan detection, and recovery over pgschema or a reviewed ALTER plus a short SQL backfill script? Demonstrate the three variants, a stale plan, and an interrupted backfill before deciding whether to invest beyond the PoC.

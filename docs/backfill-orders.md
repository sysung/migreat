# Backfill historical orders

This example uses a disposable PostgreSQL database named `orders_demo`. The [declaration](../tests/fixtures/orders-amount-cents.yaml) names the database, source, target, shared bigint key and value column, and inclusive bounds.

## Prepare the paused table

For an actual batch release, pause the old schedule and drain active runs before preparing the destination. Run this SQL on a fresh demo database to simulate the old writer having finished:

```sql
CREATE SCHEMA analytics;
CREATE TABLE analytics.orders_input (id bigint, amount_cents bigint);
INSERT INTO analytics.orders_input
SELECT id, id * 100 FROM generate_series(1, 13) AS id;

CREATE TABLE analytics.orders (id bigint PRIMARY KEY);
INSERT INTO analytics.orders SELECT generate_series(1, 10);
ALTER TABLE analytics.orders ADD COLUMN amount_cents bigint;
```

## Preview and confirm

Point `DATABASE_URL` at the demo database and run from the project root:

```sh
migreat backfill plan tests/fixtures/orders-amount-cents.yaml
migreat backfill apply tests/fixtures/orders-amount-cents.yaml
```

The preview should show ten pending rows. Review the target and range, then type `yes`. A subsequent preview shows zero pending rows and ten already correct. Verify the filled values:

```sql
SELECT id, amount_cents FROM analytics.orders ORDER BY id;
```

For a real release, deploy the updated writer after verification. If the fill fails, keep the job paused and resolve the reported issue. If the database connection drops during apply, run a fresh plan to check which values are present. If the new writer fails after a successful fill, resolve the writer failure before resuming its schedule.

The proof of concept supports a range of up to 1,000 possible bigint keys. Scoped target keys must be unique and have exactly one non-NULL source value each. The fill preserves correct existing values and fails on mismatches. One transaction rechecks the preview and verifies the result. Table locks can block writers during that transaction.

## dbt handoff rehearsal

A disposable copy of db-test used PostgreSQL 17.12 and dbt Core 1.12.7. The baseline build finished with IDs 1–10, simulating a paused and drained schedule. After preparing the destination column, Migreat filled and verified those ten rows. A repeat reported zero pending rows and ten already correct.

The existing enriched command appended IDs 11–13, then appended ID 14 on a second run after it was added to the source:

```sh
docker compose run --rm dbt build --select orders --vars '{enriched: true}'
```

Both builds passed the ID uniqueness and non-null tests. SQL checks found 14 distinct IDs with the expected amounts and the same target table identity as the baseline. The rehearsal used one-shot commands in a separate Compose project. Pausing and draining a production scheduler remains an operator action.

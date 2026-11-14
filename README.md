# Migreat

Migreat previews and fills one nullable column in an existing PostgreSQL table. It targets small, paused daily batch releases.

## Install

### From GitHub

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git.
2. Install Migreat. For a backfill, replace `master` with the full SHA of a commit that passed CI. Use the same installation for preview and apply.

   ```sh
   uv tool install --python 3.12 "git+https://github.com/sysung/migreat.git@master"
   ```

3. Run `migreat --help`. If your shell can't find `migreat`, run `uv tool update-shell` and reopen the terminal.

### From a source checkout

1. In your virtual environment, run `python -m pip install .`.

### With Docker

1. Build the image with `docker build -t migreat .`.
2. Run `docker run --rm migreat --help`.

## Backfill an existing table

1. Pause the daily writer and wait for active runs to finish.
2. Prepare the nullable destination column through your schema deployment process. Use a retained input table and keep it stable during the fill.
3. Point `DATABASE_URL` at the intended database.
4. Review the declaration. If you installed from GitHub, download the [example declaration](https://raw.githubusercontent.com/sysung/migreat/master/tests/fixtures/orders-amount-cents.yaml) and substitute its local path in the commands below. If you pinned the install to a commit, use the same SHA in the example URL.
5. Preview the backfill.

   ```sh
   migreat plan tests/fixtures/orders-amount-cents.yaml
   ```

6. Apply the backfill. Review the fresh preview and type `yes` to confirm.

   ```sh
   migreat apply tests/fixtures/orders-amount-cents.yaml
   ```

7. Verify the backfill, then deploy the updated writer and resume the schedule.

## Add and backfill a column

Pause and drain the daily writer and point `DATABASE_URL` at the intended
database. Declare a new nullable column and the historical range. For example,
save this as `amount-dollars.yaml` to join on `id` and convert cents to dollars.

```yaml
database: orders_demo
target: analytics.orders
key: id
column: amount_dollars
start: 1
end: 10
fill:
  policy: scale
  source: analytics.orders_input
  column: amount_cents
  multiplier: "0.01"
```

For a timestamp column, save a declaration such as `orders-ds.yaml`.
Scoped rows will receive the apply transaction's start time.

```yaml
database: orders_demo
target: analytics.orders
key: id
column: ds
start: 1
end: 10
fill:
  policy: transaction_timestamp
```

1. Run `migreat plan amount-dollars.yaml` to preview the SQL.
2. Run `migreat apply amount-dollars.yaml` to generate a fresh plan.
   Review the SQL and type `yes` to add and fill the column in one transaction.
3. Verify the result, then deploy the updated writer and resume the schedule.

## Add a column from compiled dbt models

Save the compiled PostgreSQL `manifest.json` for the deployed baseline and for
the candidate. Use the same target database for both compilations. For example,
the baseline model can select `id, amount_cents, discount_cents` from
`analytics.orders_input` and the candidate can add
`(amount_cents - COALESCE(discount_cents, 0))::numeric / 100 AS net_dollars`. Both versions must target
the same table and read directly from the same schema-qualified source without
filters, joins, or other row-shaping clauses.

Set `DATABASE_URL` to the live target PostgreSQL database. Choose the shared
key and inclusive historical range. Pass the exact model ID from the manifest.

```sh
migreat plan --baseline deployed.json --candidate proposed.json \
  --model model.shop.orders --key id --start 1 --end 10
migreat apply --baseline deployed.json --candidate proposed.json \
  --model model.shop.orders --key id --start 1 --end 10
```

Calculations can use multiple retained fields, built-in scalar arithmetic,
comparisons, casts, CASE, and COALESCE. PostgreSQL determines the result type
and handles NULL inputs. A keyed fill needs one retained source row per
historical target key. A constant or CURRENT_TIMESTAMP needs no source match.
Time-dependent values are calculated in the apply transaction.

The plan shows the added column and checks its expression and historical keys
against PostgreSQL. If the checks pass, it shows the proposed SQL and bound
values. Unsupported calculations are reported as blockers. Pause and drain the old writer before applying. Apply generates a
fresh report and asks for literal `yes` before adding and filling the column.
Run the updated dbt model after the migration succeeds.

## Run tests

With Docker running and the installed CLI on PATH:

```sh
python -m unittest discover -s tests -v
```

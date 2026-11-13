# Migreat

Migreat previews and fills one nullable bigint column in an existing PostgreSQL table from retained data in the same database. It targets small, paused daily batch releases.

## Install

With Python 3.12, run from the project root:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install .
migreat --help
```

For Docker, run `docker build -t migreat .` and `docker run --rm migreat --help`.

## Backfill an existing table

Pause the daily writer and wait for active runs to finish. Prepare the nullable destination column through your schema deployment process. Use a retained input table and keep it stable during the fill. Point `DATABASE_URL` at the intended database.

```sh
migreat backfill plan tests/fixtures/orders-amount-cents.yaml
migreat backfill apply tests/fixtures/orders-amount-cents.yaml
```

Review the fresh preview and type `yes` to confirm. After verification, deploy the updated writer and resume the schedule. The [walkthrough](docs/backfill-orders.md) provides a disposable PostgreSQL example.

## Integration tests

With Docker running and the installed CLI on PATH:

```sh
python -m unittest discover -s tests -v
```

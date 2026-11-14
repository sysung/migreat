# Migreat

Migreat previews and fills one nullable bigint column in an existing PostgreSQL table from retained data in the same database. It targets small, paused daily batch releases.

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
   migreat backfill plan tests/fixtures/orders-amount-cents.yaml
   ```

6. Apply the backfill. Review the fresh preview and type `yes` to confirm.

   ```sh
   migreat backfill apply tests/fixtures/orders-amount-cents.yaml
   ```

7. Verify the backfill, then deploy the updated writer and resume the schedule.

## Plan a replacement table cutover

Create `orders-cutover.yaml` with the replacement schema and the retained fields
that supply its historical values.

```yaml
mode: full_refresh
database: orders_demo
old_table: analytics.orders
replacement_table: analytics.orders_next
snapshot: orders-snapshot-42
reader_owner: data-platform
freshness_seconds: 3600
key: id
columns:
  id: {type: bigint, source: id}
  amount_dollars: {type: numeric, source: amount_cents, divide_by: 100}
```

1. Run `migreat cutover plan orders-cutover.yaml` to see the proposed DDL,
   historical projections, and review steps. The command exits nonzero until
   evidence is supplied.
2. Build the replacement and compare both outputs from the same input snapshot.
   Review key coverage, duplicates, expected transformed values, and whether
   readers can safely switch back.
3. Record the observed results in `orders-evidence.yaml`. Replace the sample
   fingerprint and timestamps with the plan's fingerprint and measured UTC
   timestamps. Use the snapshot capture time for `snapshot_at` and the comparison
   completion time for `compared_at`. Record actual comparison counts and rollback readiness.

   ```yaml
   plan_sha256: "<Plan SHA-256 from the CLI>"
   old_build_snapshot: orders-snapshot-42
   replacement_build_snapshot: orders-snapshot-42
   comparison_snapshot: orders-snapshot-42
   snapshot_at: "2026-11-13T18:00:00Z"
   compared_at: "2026-11-13T18:10:00Z"
   missing_keys: 0
   extra_keys: 0
   duplicate_keys: 0
   value_mismatches: 0
   rollback_ready: true
   ```

4. Run `migreat cutover plan orders-cutover.yaml --evidence orders-evidence.yaml`.
   A zero exit status means the supplied evidence meets the gates. The deployment
   owner still verifies the live state and switches readers.

The command works offline and leaves database writes to the deployment process.
Full refresh is supported. Incremental, microbatch, and streaming declarations
report unsupported. For original load timestamps, declare an authoritative
retained timestamp as the source.

## Run tests

With Docker running and the installed CLI on PATH:

```sh
python -m unittest discover -s tests -v
```

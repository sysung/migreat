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

## Run tests

With Docker running and the installed CLI on PATH:

```sh
python -m unittest discover -s tests -v
```

# Migreat

Migreat previews and fills one nullable bigint column in an existing PostgreSQL table from retained data in the same database. It targets small, paused daily batch releases.

## Install

Install the versioned wheel from [GitHub Releases](https://github.com/sysung/migreat/releases).
The following commands use the planned first release, v0.1.0. Migreat requires
Python 3.12 or later. The unrelated `migreat` package on PyPI belongs to another project.

```sh
uv tool install --python 3.12 "https://github.com/sysung/migreat/releases/download/v0.1.0/migreat-0.1.0-py3-none-any.whl"
migreat --help
```

With pipx and a compatible Python:

```sh
pipx install "https://github.com/sysung/migreat/releases/download/v0.1.0/migreat-0.1.0-py3-none-any.whl"
```

With pip on macOS or Linux:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install "https://github.com/sysung/migreat/releases/download/v0.1.0/migreat-0.1.0-py3-none-any.whl"
.venv/bin/migreat --help
```

With pip on Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install "https://github.com/sysung/migreat/releases/download/v0.1.0/migreat-0.1.0-py3-none-any.whl"
.venv\Scripts\migreat.exe --help
```

From a source checkout, run `python -m pip install .` in the virtual
environment. For Docker, run `docker build -t migreat .` and
`docker run --rm migreat --help`.

## Backfill an existing table

Pause the daily writer and wait for active runs to finish. Prepare the nullable destination column through your schema deployment process. Use a retained input table and keep it stable during the fill. Point `DATABASE_URL` at the intended database. If you installed from a release,
download the [example declaration for v0.1.0](https://github.com/sysung/migreat/blob/v0.1.0/tests/fixtures/orders-amount-cents.yaml)
once that tag is available. Review it and substitute its local path in the commands below.

```sh
migreat backfill plan tests/fixtures/orders-amount-cents.yaml
migreat backfill apply tests/fixtures/orders-amount-cents.yaml
```

Review the fresh preview and type `yes` to confirm. After verification, deploy the updated writer and resume the schedule.

## Integration tests

With Docker running and the installed CLI on PATH:

```sh
python -m unittest discover -s tests -v
```

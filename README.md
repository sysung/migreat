# migreat

A local PostgreSQL proof of concept. It compares one ODCS 3.2.0 table contract with the live schema and previews a single nullable `bigint` addition. Existing rows read `NULL` in the new column. Backfill is a follow-up.

## Run locally

With Python 3.12, run these commands from the project root. Removing the generated `build/` directory prevents stale package files from entering the install.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
rm -rf ./build
python -m pip install .
```

## Run with Docker

```sh
docker build -t migreat .
docker run --rm migreat --help
```

Follow [Add a PostgreSQL column](docs/adding-a-column.md) to write an ODCS contract and run the migration locally or in Docker.

## Integration tests

With Docker running and the virtual environment active:

```sh
python -m unittest discover -s tests -v
```

The suite starts PostgreSQL 17.12 on a dynamically assigned localhost port, reseeds ten rows before each case, and removes the container on exit.

The bundled JSON Schema comes from [ODCS v3.2.0](https://github.com/bitol-io/open-data-contract-standard/blob/v3.2.0/schema/odcs-json-schema-latest.json), licensed under Apache 2.0.

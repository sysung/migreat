# Tasks

## 1. Give the integration suite its own input

- [x] 1.1 Move the existing contract to `tests/fixtures/orders.yaml` and update the integration suite and CLI installation scenario to use it. Run `python -m unittest discover -s tests -v` with the installed CLI and Docker to verify the original preview, apply, and failure cases.

## 2. Document the user workflow

- [x] 2.1 Write `docs/adding-a-column.md` with a complete ODCS example, disposable PostgreSQL setup, local and Docker commands, and expected results. Link it from README. Copy the guide's YAML into a fresh file and follow the guide against a disposable database to verify the generated SQL and the preserved rows.
- [x] 2.2 Search active docs, tests, and OpenSpec scenarios for stale references to the former example path. Verify that Python packaging and the Docker build context include the runtime ODCS schema and exclude the guide and fixture.

## 3. Address review findings

- [x] 3.1 Document the local install with generated build output cleared first. Verify the documented install in a temporary checkout seeded with the old package in `build/lib/` and check that only the current package is importable and its ODCS schema is installed.
- [x] 3.2 Label the installed CLI and Docker CLI as alternatives and explain the repeat-run result when both use the same demo database.

# Design

## Context

The README uses the root example as a local CLI input and mounts its directory in Docker. The integration suite reads the same file. Both the Python package and Docker build already limit their runtime inputs to the migreat package and packaging files.

## Goals / Non-Goals

Give the guide and test suite independently owned inputs. Keep consumer walkthroughs, database setup, and test fixtures outside `migreat/`. Retain the shipped CLI, migration engine, and ODCS validation schema in the package.

## Decisions

- Move `examples/orders.yaml` verbatim to `tests/fixtures/orders.yaml`. Resolve it relative to the test file. Its contract must match the seeded `public.orders` table and expected SQL.
- Put a complete, copyable ODCS 3.2.0 YAML block in `docs/adding-a-column.md`. Explain table identity, logical and physical types, and nullability. Show users how to save their own `orders.yaml`, seed a disposable table, run plan and apply locally or with Docker, and check existing rows. Inline YAML keeps the example with its explanation. A shared fixture would couple future teaching edits to the test.
- Link the guide from README and remove the obsolete root example. In the existing CLI installation scenario, point the PostgreSQL check to the test fixture. The scenario still verifies the installed CLI and bundled schema.
- Preserve the packaging boundary. The bundled ODCS JSON Schema is a runtime resource because the loader uses it to validate supplied YAML.

- Clear the generated `build/` directory in the documented local install sequence. Setuptools can reuse files from earlier builds in a dirty checkout.
- Present the installed CLI and Docker CLI as alternatives. Both connect to the same demo database, so the second run observes the already-applied schema.

## Risks / Trade-offs

- The guide and test contract can evolve independently. Validate the copied guide contract with the installed CLI against the disposable database so a stale snippet is caught during implementation.
- Removing the old path breaks copied commands that still name it. Replace repository references in the same change and search for stale paths before finishing.

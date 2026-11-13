# Proposal

## Why

The README and PostgreSQL integration suite share the same example contract, so editing the example can change the test input. Give each a home so the guide can evolve independently and the test keeps a fixture that matches its seeded table.

## What Changes

- Put the ODCS authoring and add-column walkthrough in `docs/adding-a-column.md` and link it from the README.
- Move the existing contract into `tests/fixtures/orders.yaml` and make the PostgreSQL tests use it.
- Keep shipped CLI and migration code with the ODCS validation schema in `migreat/`. Keep demo setup and user-authored contracts outside the package.

- Document how to clear generated Python build output before installing and how to choose one CLI path for the walkthrough.

## Capabilities

This repository layout and documentation change uses `skip_specs: true`.

## Impact

The change touches README, documentation, test inputs, and the example path cited by the CLI installation scenario. The old example path is replaced by the walkthrough and test fixture.

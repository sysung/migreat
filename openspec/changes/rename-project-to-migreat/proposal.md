# Proposal

## Why

The project has chosen the name migreat. Use it consistently wherever developers discover, install, import, or run the tool.

## What Changes

- Use lowercase migreat in the README, package metadata, CLI, and command examples.
- **BREAKING** Rename the Python distribution and import package to `migreat` and replace the `contract-migrate` executable with `migreat`.
- Run the PostgreSQL integration suite through the renamed executable.

## Capabilities

### New Capabilities

- `cli-installation` — Install and invoke the tool under the migreat name.

### Modified Capabilities

## Impact

The rename affects Python packaging, bundled ODCS schema lookup, CLI help, integration tests, and documentation. The change is scoped to the repository contents.

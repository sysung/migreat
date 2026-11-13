# Design

## Context

The current name appears in package metadata, the import directory, the installed entry point, CLI help, README examples, and two integration test invocations. ODCS validation loads the bundled schema through the import package name.

## Goals / Non-Goals

Use `migreat` consistently across repository-owned naming surfaces and preserve migration behavior. Hosting and checkout renames are outside this repository change.

## Decisions

- Rename the import directory to `migreat/` and update the distribution, setuptools package data, and console script entry point together. Use a relative package resource lookup for the bundled schema so the loader follows its own package.
- Update help, examples, and test invocations in the same change. Use a clean virtual environment to verify the installed name and resources independently of prior local installs.
- Use a single executable name. Existing local installations can uninstall the old distribution before installing the new one.

## Risks / Trade-offs

A source-tree test can succeed even if the wheel omits its schema. Install the built distribution in a clean environment and run the real PostgreSQL suite through its installed CLI.

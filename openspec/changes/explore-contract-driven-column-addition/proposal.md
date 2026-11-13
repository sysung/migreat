# Proposal

## Why

Teams can declare a table schema yet still have to work out how to reach it safely on a populated table. Explore whether an open-source tool can turn a portable contract and explicit migration intent into a reviewable SQL plan, including historical data changes.

## What Changes

- Explore a first proof of concept for adding one column to a populated local PostgreSQL table. PostgreSQL is the proposed first engine. The experiment requires no cloud account or paid service.
- Evaluate the Open Data Contract Standard (ODCS) as the input for desired schema and quality rules.
- Implement the nullable addition with no historical fill. Keep constant defaults and SQL backfills as follow-up experiments.
- Keep the project Apache 2.0 and the core workflow usable with open-source dependencies. Evaluate Atlas Community and pgschema as baselines.
- Keep rename, deprecation/drop, and recalculation of existing columns as future scenarios. Revisit dbt and Terraform integrations after the standalone workflow has evidence.

## Capabilities

### New Capabilities

- `contract-migration-planning` — Compare a declared table contract against live metadata and produce a reviewable schema and data migration plan.

### Modified Capabilities

## Impact

The exploration covers a local PostgreSQL fixture, ODCS inputs, generated PostgreSQL SQL, and verification of preconditions and outcomes. The long-term goal is a common contract and planning workflow across engines. This change captures the research and proposed design.

# Design

## Context

The existing backfill handles a paused in-place fill. Replacement tables enable validation before reader routing changes.

## Goals / Non-Goals

Render DDL and an operator runbook offline. External systems own builds, comparison, routing, and rollback.

## Decisions

Use `migreat cutover plan <declaration> [--evidence <file>]`. Accept schema-qualified distinct tables, a database, typed output columns with a retained source field and optional numeric divisor, a common input snapshot ID, reader owner, and a positive freshness limit in seconds. Emit quoted CREATE TABLE DDL and historical projections for review. A missing authoritative source for original timestamps blocks readiness.

Bind evidence to the parsed declaration via a canonical SHA-256 fingerprint printed with the plan. Require both builds and the keyed value comparison to reference the declared input snapshot. Require fresh UTC observation times for the snapshot and comparison, zero missing keys, extra keys, duplicate keys, and value mismatches, and an affirmative rollback-readiness observation. Report an assessment of supplied evidence only. Exit zero when supported and nonzero when blocked or invalid.

Incremental needs a proven snapshot-to-change boundary and delete/retry semantics. Microbatch also needs window completeness and late-record reconciliation. Streaming needs replay coverage and per-partition lag and boundary evidence. These modes report unsupported until their evidence contracts exist.

## Risks / Trade-offs

Equal row counts can hide differences. A fingerprint binds evidence to the declaration but does not authenticate its origin. Use a stable input snapshot to avoid comparing moving datasets.

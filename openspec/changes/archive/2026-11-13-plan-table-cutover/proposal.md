# Proposal

## Why

Operators need to review a replacement table before switching readers, across batch and streaming pipelines.

## What Changes

Add read-only PostgreSQL replacement-table planning and assessment of operator-supplied evidence. Start with full refresh.

## Capabilities

### New Capabilities

- `table-cutover` covers replacement-table planning and readiness assessment.

### Modified Capabilities

None.

## Impact

Add a CLI command and declaration. Deployment owners build tables and switch readers.

# Spec Delta

## REMOVED Requirements

### Requirement: Preview a nullable addition

**Reason**: The backfill PoC operates on an existing column and focuses on the historical data change.
**Migration**: Preview additive DDL in the existing schema deployment process. Then use `migreat backfill plan FILE` to preview the data fill.

### Requirement: Apply the reviewed addition

**Reason**: The backfill PoC delegates additive DDL to the schema deployment process.
**Migration**: Pause and drain the batch writer, apply the reviewed DDL through that process, then use `migreat backfill apply FILE`.

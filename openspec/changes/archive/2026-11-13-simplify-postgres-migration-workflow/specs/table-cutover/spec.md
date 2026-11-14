# Table cutover delta

## REMOVED Requirements

### Requirement: Preview a replacement table

**Reason**: The offline replacement-table workflow is retired.

**Migration**: Use the deployment process for full table replacement. Use `migreat plan` for supported in-place changes.

### Requirement: Assess full-refresh evidence

**Reason**: Evidence-file review belonged to the retired offline workflow.

**Migration**: Verify replacement readiness in the deployment process.

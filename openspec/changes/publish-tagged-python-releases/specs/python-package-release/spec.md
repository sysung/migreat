# Python package release

## Purpose

Give users a downloadable Python package tied to a verified Migreat version and source revision.

## ADDED Requirements

### Requirement: Publish verified tagged distributions
A release SHALL publish the tested wheel and source distribution as public GitHub Release assets only for a stable version tag that matches the package version and identifies a commit on the default branch.

#### Scenario: Publish an eligible version
- **WHEN** a `vMAJOR.MINOR.PATCH` tag matches the distribution version, its commit is on the default branch, and all release checks pass
- **THEN** the verified wheel and source distribution are downloadable from the GitHub Release for that tag

#### Scenario: Reject an ineligible version
- **WHEN** a tag is malformed, its version differs from package metadata, or its commit is outside the default branch history
- **THEN** release validation fails before publishing

#### Scenario: Block publication on verification failure
- **WHEN** a package build or validation check fails
- **THEN** publication is blocked

### Requirement: Rehearse publication checks
Maintainers SHALL be able to run the release build and verification without publishing as public GitHub Release assets.

#### Scenario: Run a rehearsal
- **WHEN** a maintainer starts a verification-only run
- **THEN** the run reports the package check results and creates no GitHub Release or public release assets

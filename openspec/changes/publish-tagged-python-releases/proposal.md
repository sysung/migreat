# Proposal

## Why

Migreat's CI verifies the checkout and Docker image. Users need a versioned package they can download and run on Linux, macOS, and Windows without cloning the repository.

## What Changes

- Publish a Python wheel and source distribution as GitHub Release assets from a version tag after package checks pass.
- Keep the distribution, import, and executable named `migreat`. Install from the versioned GitHub wheel URL because another project owns the PyPI name.
- Document isolated CLI installs and version pinning.

## Capabilities

### New Capabilities

- `python-package-release` governs verification and publication of tagged distributions.

### Modified Capabilities

- `cli-installation` defines release URL installation and the supported platforms.

## Impact

The change affects Python package metadata, GitHub Actions, GitHub release settings, and installation documentation.

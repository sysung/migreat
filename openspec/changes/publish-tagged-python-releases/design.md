# Design

## Context

Current CI runs the full PostgreSQL suite and Docker smoke test on Linux. The suite starts Docker and uses Unix pipe selection and signals. Migreat itself ships Python code, but psycopg and PyYAML have platform-dependent distributions. See [the proposal](proposal.md) for the change in distribution name.

## Goals / Non-Goals

**Goals**

- Deliver a versioned wheel and source distribution through GitHub Releases.
- Keep the version tag, source revision, artifact metadata, and published files traceable to the same release.

**Non-Goals**

- Standalone binaries, Homebrew formulas, shell installers, and container registry publishing are outside the initial release scope.

## Decisions

### Use one distribution and one release version

Keep `migreat` as the distribution name, console entry point, and import. The only top-level subcommand is `backfill`, with `plan` and `apply`. Use `pyproject.toml` as the version source. For a release, require a stable `vMAJOR.MINOR.PATCH` tag with an exact version match and a commit reachable from `origin/master`. Use `v0.1.0` if that is still the reviewed package version and the tag is unused. Tag-derived versioning would add a build dependency for a check that static metadata already supports.

### Build once and verify what users will install

Add a dedicated release workflow. Tag pushes can publish. Manual dispatch rehearses build and verification without entering the publishing job. Build one wheel and one source distribution with the standard Python build frontend. Record SHA-256 hashes and pass both artifacts to the publishing job. Keep the existing PR and default-branch jobs.

The existing CI workflow covers the PostgreSQL integration suite and Docker CLI. The release workflow checks artifact names and checksums.

### Scope publishing credentials to the upload job

Protect existing version tags and limit their creation to release maintainers. Only the gated release job receives `contents: write` using the workflow's GitHub token. Verify the build manifest, stage the verified wheel, source distribution, and manifest on a draft associated with the existing tag, then make the draft public after all assets are present. A maintainer-created tag records release intent. Manual dispatch never publishes.

## Risks / Trade-offs

- The unrelated PyPI distribution has the same name. Use the full versioned GitHub wheel URL in each install command.
- A pure Python wheel does not guarantee dependency availability on every platform.
- Manual rehearsal verifies the pipeline through the publish gate. The first authorized release verifies the public download URLs.
- An upload can fail before the draft is complete. Check existing asset hashes before uploading missing assets from the same build. Preserve published tags and assets. Release a new version to correct a defective public artifact.

## Migration Plan

Update the install docs to lead with `uv tool install <wheel-url>`, then show pipx and pip in a virtual environment, including Windows commands and versioned GitHub wheel URLs. Provide a versioned example declaration for people without a checkout. If package metadata references the README, include it in the Docker build context before the package install.

Rehearse against the intended release commit. Configure tag protections, then create the first release tag when authorized. Confirm the public release lists the wheel, source distribution, and checksum manifest.

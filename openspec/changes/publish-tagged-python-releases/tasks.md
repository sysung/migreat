# Tasks

## 1. Package and document the CLI

- [x] 1.1 Verify and complete distribution metadata for `migreat`, preserving the `migreat` import and entry point. Include project description, README, source link, and license. Copy the README into the Docker build before installation. Build from a clean tree, run `twine check --strict`, and inspect wheel and sdist metadata, contents, and version.
- [x] 1.2 Document uv, pipx, and pip in a virtual environment, with Windows and POSIX instructions, Python prerequisites, exact-version examples, and a versioned example declaration usable outside the checkout. Review the README commands for the versioned wheel URL.

## 2. Verify the release artifacts

- [x] 2.1 Add the tag and verification-only workflow triggers. Validate stable tag syntax, version equality, and reachability from `master`. Build once and upload the wheel, sdist, and hash manifest for downstream jobs. Exercise malformed, mismatched, and off-branch refs, and confirm manual dispatch skips publishing.

## 3. Publish and verify the public install

- [x] 3.1 Add the dedicated GitHub Release job gated on release validation and successful package build. Verify its event, permissions, and artifact inputs, including that a failed prerequisite prevents upload. Document tag protection, release tagging, and hash-based recovery for incomplete drafts.
- [ ] 3.2 Run the verification-only workflow on the intended release commit. Review the build result, the downloadable build artifacts, and the skipped publish job.
- [ ] 3.3 Configure tag protections. After release authorization, push the reviewed version tag and verify the public GitHub Release contains the tested wheel and sdist. Compare both public file hashes with the workflow manifest.

# Release Migreat

The release workflow builds the wheel and source distribution from the tagged
commit. It records checksums and publishes the files to GitHub Releases.

1. Set the version in `pyproject.toml` and merge the reviewed release commit
   into `master`. Run **Python package release** from the Actions tab on `master` and confirm the run
   used that commit. Manual runs build the package and record its checksums and skip publication.
2. Protect `v*` tags with GitHub tag rulesets. Restrict creation to release
   maintainers and restrict updates and deletions. Confirm the proposed tag
   is unused.
3. After release approval, create and push the tag for the reviewed commit.
   For example, for version 0.1.0:

   ```sh
   git tag -a v0.1.0 <reviewed-commit> -m "Migreat 0.1.0"
   git push origin refs/tags/v0.1.0
   ```

4. Check the release workflow and confirm the public release has the wheel,
   source distribution, and `SHA256.json`. If you want to try the download,
   use the wheel URL from the release with the README install command.

## Recover an incomplete release

The publishing job stages assets on a draft and checks the bytes of any
existing assets before retrying. Re-run the failed job in the original
workflow to reuse the same verified artifacts. If an existing asset differs
or the original build artifacts have expired, investigate before attempting
to publish. Use a new version for corrected public artifacts and preserve
the existing tag and downloads.

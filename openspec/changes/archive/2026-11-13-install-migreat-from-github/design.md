## Decisions

Install from the public Git repository with `uv tool install --python 3.12`. Use master for evaluation and a passing master commit SHA for backfill preview and apply. The SHA fixes the Migreat source while dependency versions still resolve from package metadata.

Keep the existing CI workflow and remove the package release workflow. Source installation uses the existing setuptools build and version metadata.

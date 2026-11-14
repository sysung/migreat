"""Validate release refs and identify the exact distributions to publish."""

import argparse
import configparser
import email
import hashlib
import json
import re
import subprocess
import tarfile
import tomllib
import zipfile
from pathlib import Path


def validate_ref(version, ref):
    if not re.fullmatch(r"refs/tags/v(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2}", ref):
        raise ValueError("Expected a stable vMAJOR.MINOR.PATCH release tag")
    if ref.removeprefix("refs/tags/v") != version:
        raise ValueError(f"Release tag does not match package version {version}")
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", "HEAD", "origin/master"],
        check=False,
    ).returncode:
        raise ValueError("Tagged commit must be reachable from origin/master")


def verify_metadata(data, project):
    metadata = email.message_from_bytes(data)
    for field, value in {
        "Name": project["name"],
        "Version": project["version"],
        "Requires-Python": project["requires-python"],
        "License-Expression": project["license"],
    }.items():
        if metadata[field] != value:
            raise ValueError(f"Unexpected {field} in package metadata")


def create_manifest(directory, project):
    stem = f"{project['name'].replace('-', '_')}-{project['version']}"
    wheel = directory / f"{stem}-py3-none-any.whl"
    sdist = directory / f"{stem}.tar.gz"
    if set(directory.iterdir()) != {wheel, sdist}:
        raise ValueError("Expected exactly one wheel and one source distribution")
    with zipfile.ZipFile(wheel) as archive:
        info = f"{stem}.dist-info"
        verify_metadata(archive.read(f"{info}/METADATA"), project)
        entry_points = configparser.ConfigParser()
        entry_points.read_string(archive.read(f"{info}/entry_points.txt").decode())
        if entry_points["console_scripts"]["migreat"] != project["scripts"]["migreat"]:
            raise ValueError("Unexpected migreat entry point")
        for name in ("migreat/__init__.py", "migreat/cli.py", "migreat/backfill.py",
                     f"{info}/licenses/LICENSE"):
            archive.getinfo(name)
    with tarfile.open(sdist) as archive:
        metadata = archive.extractfile(f"{stem}/PKG-INFO")
        if metadata is None:
            raise ValueError("Source distribution has no package metadata")
        verify_metadata(metadata.read(), project)
        for name in ("pyproject.toml", "README.md", "LICENSE", "migreat/cli.py"):
            archive.getmember(f"{stem}/{name}")
    manifest = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (wheel, sdist)}
    (directory / "SHA256.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref")
    parser.add_argument("--dist", type=Path)
    args = parser.parse_args()
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    if args.ref:
        validate_ref(project["version"], args.ref)
    if args.dist:
        create_manifest(args.dist, project)


if __name__ == "__main__":
    main()

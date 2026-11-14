"""Exercise the installed CLI and its runtime dependencies outside the checkout."""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(*args, **kwargs):
    return subprocess.run(
        [str(arg) for arg in args], check=True, text=True, timeout=240, **kwargs
    )


def verify_cli(executable):
    run(executable, "--help")
    result = subprocess.run(
        [str(executable), "backfill", "plan", "missing.yaml"],
        capture_output=True, timeout=15,
    )
    if result.returncode != 1 or b"Error:" not in result.stderr:
        raise RuntimeError(f"Unexpected missing declaration result: {result}")


def verify_import(python, version):
    run(
        python, "-I", "-c",
        "import importlib.metadata, pathlib, sys, migreat, psycopg, yaml; "
        "assert pathlib.Path(migreat.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve()); "
        "assert importlib.metadata.version('migreat') == sys.argv[1]",
        version,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", help="Absolute archive path or exact PyPI requirement")
    parser.add_argument("version")
    parser.add_argument("--venv", required=True, type=Path)
    parser.add_argument("--all-installers", action="store_true")
    args = parser.parse_args()

    windows = os.name == "nt"
    scripts = args.venv / ("Scripts" if windows else "bin")
    python = scripts / ("python.exe" if windows else "python")
    migreat = "migreat.exe" if windows else "migreat"
    print(f"{platform.platform()} {platform.machine()} Python {platform.python_version()}", flush=True)
    os.environ.pop("PYTHONPATH", None)
    run(sys.executable, "-m", "venv", args.venv)
    run(python, "-m", "pip", "--isolated", "install", "--no-cache-dir",
        "--index-url", "https://pypi.org/simple/", args.package)
    run(python, "-m", "pip", "check")
    verify_import(python, args.version)
    verify_cli(scripts / migreat)

    if args.all_installers:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            uv = shutil.which("uv")
            if uv is None:
                raise RuntimeError("uv is required for installer verification")
            for installer, command, env_vars in (
                ("uv", [uv, "tool", "install"],
                 {"UV_TOOL_DIR": root / "uv", "UV_TOOL_BIN_DIR": root / "uv-bin",
                  "UV_CACHE_DIR": root / "uv-cache"}),
                ("pipx", [sys.executable, "-m", "pipx", "install"],
                 {"PIPX_HOME": root / "pipx", "PIPX_BIN_DIR": root / "pipx-bin"}),
            ):
                env = os.environ | {key: str(value) for key, value in env_vars.items()}
                env["PIP_INDEX_URL"] = "https://pypi.org/simple/"
                env["UV_DEFAULT_INDEX"] = "https://pypi.org/simple/"
                run(*command, "--python", sys.executable, args.package, env=env)
                tool_root = root / installer
                if installer == "pipx":
                    tool_root /= "venvs"
                verify_import(tool_root / "migreat" / scripts.name / python.name,
                              args.version)
                verify_cli(root / f"{installer}-bin" / migreat)


if __name__ == "__main__":
    main()

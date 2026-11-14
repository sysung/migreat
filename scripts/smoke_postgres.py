"""Run a small, disposable PostgreSQL backfill through the installed CLI."""

import argparse
import os
import platform
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg

DATABASE = "orders_demo"


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, timeout=90, **kwargs)


@contextmanager
def server(bin_dir):
    if bin_dir is None:
        container = run(
            "docker", "run", "--detach", "--rm", "--env", "POSTGRES_PASSWORD=fixture",
            "--publish", "127.0.0.1::5432", "postgres:17.12",
            capture_output=True, text=True,
        ).stdout.strip()
        try:
            address = run("docker", "port", container, "5432/tcp",
                          capture_output=True, text=True).stdout.strip()
            yield f"postgresql://postgres:fixture@{address}/postgres?connect_timeout=2"
        finally:
            run("docker", "rm", "-f", container)
        return

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        data = root / "data"
        suffix = ".exe" if os.name == "nt" else ""
        run(bin_dir / f"initdb{suffix}", "-D", data, "-U", "postgres",
            "--auth=trust", "--encoding=UTF8", "--no-locale")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        control = bin_dir / f"pg_ctl{suffix}"
        log = root / "postgres.log"
        try:
            run(control, "-D", data, "-l", log, "-w", "-t", "30",
                "-o", f"-h 127.0.0.1 -p {port}", "start")
            yield f"postgresql://postgres@127.0.0.1:{port}/postgres?connect_timeout=2"
        finally:
            if (data / "postmaster.pid").exists():
                run(control, "-D", data, "-w", "-t", "30", "-m", "fast", "stop")
            if log.exists():
                print(log.read_text(encoding="utf-8", errors="replace"), flush=True)


def wait_for_server(dsn):
    deadline = time.monotonic() + 30
    while True:
        try:
            return psycopg.connect(dsn, autocommit=True)
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.25)


def verify(executable, declaration, dsn):
    with wait_for_server(dsn) as admin:
        admin.execute("CREATE DATABASE orders_demo")
    dsn = psycopg.conninfo.make_conninfo(dsn, dbname=DATABASE)
    with psycopg.connect(dsn, autocommit=True) as connection:
        postgres_version = connection.execute("SHOW server_version").fetchone()[0]
        print(f"{platform.platform()} {platform.machine()} Python {platform.python_version()} "
              f"PostgreSQL {postgres_version}", flush=True)
        connection.execute("""
            CREATE SCHEMA analytics;
            CREATE TABLE analytics.orders_input (id bigint, amount_cents bigint);
            CREATE TABLE analytics.orders (id bigint, amount_cents bigint, note text);
            INSERT INTO analytics.orders_input SELECT id, id * 100 FROM generate_series(1, 10) id;
            INSERT INTO analytics.orders VALUES (1, NULL, 'preserve'), (11, NULL, 'out of scope');
        """)

        def cli(action, reply=""):
            result = run(
                executable, "backfill", action, declaration,
                input=reply.encode(), capture_output=True,
                env=os.environ | {"DATABASE_URL": dsn},
            )
            print(result.stdout.decode(errors="replace"), flush=True)
            return result.stdout

        query = "SELECT id, amount_cents, note FROM analytics.orders ORDER BY id"
        before = connection.execute(query).fetchall()
        assert b"Pending: 1," in cli("plan")
        assert connection.execute(query).fetchall() == before
        assert b"Updated and verified 1 rows." in cli("apply", "yes\n")
        assert connection.execute(query).fetchall() == [
            (1, 100, "preserve"), (11, None, "out of scope"),
        ]
        assert b"Pending: 0," in cli("plan")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    parser.add_argument("declaration", type=Path)
    parser.add_argument("--postgres-bin", type=Path)
    args = parser.parse_args()
    with server(args.postgres_bin) as dsn:
        verify(args.executable, args.declaration, dsn)


if __name__ == "__main__":
    main()

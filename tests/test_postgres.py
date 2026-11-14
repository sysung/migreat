import os
import select
import signal
import subprocess
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import psycopg
import yaml

from migreat import backfill
from migreat.apply import apply
from migreat.plan import preview

PROMPT = b"Type yes to apply: "
DECLARATION = {
    "database": "backfill_test",
    "source": "public.orders_input",
    "target": "public.orders",
    "key": "id",
    "column": "amount_cents",
    "start": 1,
    "end": 10,
}


class PostgresIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        container = subprocess.check_output(
            [
                "docker", "run", "--detach", "--rm",
                "--env", "POSTGRES_PASSWORD=fixture",
                "--env", "POSTGRES_DB=backfill_test",
                "--publish", "127.0.0.1::5432", "postgres:17.12",
                "-c", "listen_addresses=*",
            ],
            text=True,
        ).strip()
        cls.addClassCleanup(subprocess.run, ["docker", "rm", "-f", container], check=True, capture_output=True)
        address = subprocess.check_output(["docker", "port", container, "5432/tcp"], text=True).strip()
        cls.dsn = f"postgresql://postgres:fixture@{address}/backfill_test?connect_timeout=2"
        deadline = time.monotonic() + 30
        while True:
            try:
                with psycopg.connect(cls.dsn) as connection:
                    connection.execute("SELECT 1")
                return
            except psycopg.OperationalError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)

    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.declaration = Path(directory) / "orders-amount-cents.yaml"
        self.write_declaration()
        self.seed_tables()

    def seed_tables(self):
        self.execute("""
            DROP TABLE IF EXISTS public.orders, public.orders_input CASCADE;
            CREATE TABLE public.orders (id bigint, amount_cents bigint, note text);
            CREATE TABLE public.orders_input (id bigint, amount_cents bigint);
            INSERT INTO public.orders
                SELECT id, NULL, 'original-' || id FROM generate_series(1, 13) id;
            INSERT INTO public.orders_input
                SELECT id, id * 100 FROM generate_series(1, 13) id;
            UPDATE public.orders SET amount_cents = 100 WHERE id = 1;
            UPDATE public.orders SET amount_cents = 1200 WHERE id = 12;
        """)

    def write_declaration(self, **overrides):
        self.declaration.write_text(yaml.safe_dump(DECLARATION | overrides), encoding="utf-8")

    def execute(self, statement):
        with psycopg.connect(self.dsn) as connection:
            connection.execute(statement)

    def state(self):
        with psycopg.connect(self.dsn) as connection:
            oid = connection.execute("SELECT 'public.orders'::regclass::oid").fetchone()[0]
            target = connection.execute("TABLE public.orders ORDER BY id, note").fetchall()
            source = connection.execute("TABLE public.orders_input ORDER BY id, amount_cents").fetchall()
        return oid, target, source

    def row_versions(self):
        with psycopg.connect(self.dsn) as connection:
            return connection.execute(
                "SELECT id, xmin::text FROM public.orders ORDER BY id"
            ).fetchall()

    def cli_args(self, action):
        return ["migreat", action, str(self.declaration)]

    def run_cli(self, action, reply=""):
        return subprocess.run(
            self.cli_args(action),
            env={**os.environ, "DATABASE_URL": self.dsn},
            input=reply,
            text=True,
            capture_output=True,
            timeout=10,
        )

    @contextmanager
    def waiting_for_confirmation(self):
        with subprocess.Popen(
            self.cli_args("apply"),
            env={**os.environ, "DATABASE_URL": self.dsn},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as process:
            try:
                output = b""
                deadline = time.monotonic() + 10
                while PROMPT not in output:
                    remaining = max(0, deadline - time.monotonic())
                    self.assertTrue(select.select([process.stdout], [], [], remaining)[0], output)
                    chunk = os.read(process.stdout.fileno(), 4096)
                    self.assertTrue(chunk, output)
                    output += chunk
                yield process
            finally:
                if process.poll() is None:
                    process.kill()

    def assert_blocked(self, expected_pattern):
        before = self.state()
        result = self.run_cli("apply", "yes\n")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn(PROMPT.decode(), result.stdout)
        self.assertRegex(result.stderr.lower(), expected_pattern)
        self.assertEqual(self.state(), before)

    def test_plan_previews_scope_without_writes(self):
        before = self.state()
        result = self.run_cli("plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        for label in ("backfill_test", "orders_input", "pending", "correct", "blocked"):
            self.assertIn(label, result.stdout.lower())
        self.assertRegex(result.stdout.lower(), r"pending[^\n]*9|9[^\n]*pending")
        self.assertEqual(self.state(), before)

    def test_apply_preserves_keys_unrelated_fields_and_existing_values(self):
        oid, rows, source = self.state()
        original_versions = dict(self.row_versions())
        result = self.run_cli("apply", "yes\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(PROMPT.decode(), result.stdout)
        expected = [(key, key * 100 if key <= 10 else value, note) for key, value, note in rows]
        self.assertEqual(self.state(), (oid, expected, source))

        applied_versions = self.row_versions()
        for key, version in applied_versions:
            if key == 1 or key > 10:
                self.assertEqual(version, original_versions[key])

        repeated = self.run_cli("apply")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertNotIn(PROMPT.decode(), repeated.stdout)
        self.assertRegex(repeated.stdout.lower(), r"pending[^\n]*0|0[^\n]*pending")
        self.assertEqual(self.state(), (oid, expected, source))
        self.assertEqual(self.row_versions(), applied_versions)

    def test_requires_literal_confirmation(self):
        before = self.state()
        for reply in ("no\n", "YES\n", ""):
            with self.subTest(reply=reply):
                self.run_cli("apply", reply)
                self.assertEqual(self.state(), before)

        with self.waiting_for_confirmation() as process:
            self.assertEqual(self.state(), before)
            process.send_signal(signal.SIGINT)
            process.communicate(timeout=10)
        self.assertEqual(self.state(), before)

    def test_rejects_same_count_drift_after_preview(self):
        with self.waiting_for_confirmation() as process:
            self.execute("UPDATE public.orders_input SET amount_cents = 201 WHERE id = 2")
            changed = self.state()
            _, stderr = process.communicate(b"yes\n", timeout=10)
            self.assertNotEqual(process.returncode, 0, stderr)
        self.assertEqual(self.state(), changed)

    def test_rejects_replaced_table_after_preview(self):
        with self.waiting_for_confirmation() as process:
            self.execute("""
                CREATE TABLE public.replacement AS TABLE public.orders;
                DROP TABLE public.orders;
                ALTER TABLE public.replacement RENAME TO orders;
            """)
            changed = self.state()
            _, stderr = process.communicate(b"yes\n", timeout=10)
            self.assertNotEqual(process.returncode, 0, stderr)
        self.assertEqual(self.state(), changed)

    def test_lock_timeout_does_not_write(self):
        with self.waiting_for_confirmation() as process:
            with psycopg.connect(self.dsn) as connection:
                connection.execute("LOCK TABLE public.orders IN ROW EXCLUSIVE MODE")
                _, stderr = process.communicate(b"yes\n", timeout=10)
                self.assertNotEqual(process.returncode, 0, stderr)
                self.assertIn(b"lock", stderr.lower())
        self.assertTrue(all(row[1] is None for row in self.state()[1] if 2 <= row[0] <= 10))

    def test_update_failure_rolls_back(self):
        self.execute("ALTER TABLE public.orders ADD CHECK (amount_cents <> 500)")
        before = self.state()
        result = self.run_cli("apply", "yes\n")
        self.assertIn(PROMPT.decode(), result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.state(), before)

    def test_failed_verification_rolls_back_completed_update(self):
        before = self.state()
        declaration = backfill.load_declaration(self.declaration)
        with psycopg.connect(self.dsn, autocommit=True) as connection:
            reviewed = preview(connection, declaration)
            inspect = backfill._inspect

            def fail_verification(conn, operation, **kwargs):
                result = inspect(conn, operation, **kwargs)
                if result.pending == 0:
                    raise backfill.BackfillError("Injected verification failure.")
                return result

            with patch.object(backfill, "_inspect", side_effect=fail_verification):
                with self.assertRaisesRegex(backfill.BackfillError, "Injected"):
                    apply(connection, reviewed)
        self.assertEqual(self.state(), before)

    def test_invalid_data_blocks_before_confirmation(self):
        cases = (
            ("duplicate source", "INSERT INTO public.orders_input VALUES (2, 200)", r"source|duplicate"),
            ("duplicate target", "INSERT INTO public.orders VALUES (2, NULL, 'duplicate')", r"target|duplicate"),
            ("missing source", "DELETE FROM public.orders_input WHERE id = 2", r"source|match"),
            ("NULL source", "UPDATE public.orders_input SET amount_cents = NULL WHERE id = 2", r"source|null"),
            ("conflicting value", "UPDATE public.orders SET amount_cents = 201 WHERE id = 2", r"conflict|value|match"),
        )
        for case, statement, pattern in cases:
            with self.subTest(case=case):
                self.seed_tables()
                self.execute(statement)
                self.assert_blocked(pattern)

    def test_invalid_declarations_block_before_confirmation(self):
        cases = (
            ({"database": "other_database"}, r"database"),
            ({"start": True}, r"start|range|integer"),
            ({"start": 11, "end": 10}, r"range|start|bounds"),
            ({"start": 1, "end": 1001}, r"range|limit|scope|bounds"),
            ({"start": 14, "end": 15}, r"empty|scope|row|range"),
            ({"target": "public.orders_input"}, r"source|target|table"),
            ({"column": "missing"}, r"missing|column"),
            ({"extra": "unused"}, r"extra|field|unknown|key"),
        )
        for overrides, pattern in cases:
            with self.subTest(overrides=overrides):
                self.write_declaration(**overrides)
                self.assert_blocked(pattern)

    def test_unsupported_target_features_block_before_confirmation(self):
        self.execute("ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY")
        self.assert_blocked(r"security|unsupported|table")


if __name__ == "__main__":
    unittest.main()

import os
import select
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import psycopg

CONTRACT = Path(__file__).resolve().parent / "fixtures/orders.yaml"
DDL = 'ALTER TABLE "public"."orders" ADD COLUMN "amount_cents" bigint;'
PROMPT = b"Type yes to apply: "


class PostgresIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        container = subprocess.check_output(
            [
                "docker", "run", "--detach", "--rm",
                "--env", "POSTGRES_PASSWORD=fixture",
                "--env", "POSTGRES_DB=contract_test",
                "--publish", "127.0.0.1::5432", "postgres:17.12",
                "-c", "listen_addresses=*",
            ],
            text=True,
        ).strip()
        cls.addClassCleanup(subprocess.run, ["docker", "rm", "-f", container], check=True, capture_output=True)
        address = subprocess.check_output(["docker", "port", container, "5432/tcp"], text=True).strip()
        cls.dsn = f"postgresql://postgres:fixture@{address}/contract_test?connect_timeout=2"
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
        with psycopg.connect(self.dsn) as connection:
            connection.execute("DROP TABLE IF EXISTS public.orders")
            connection.execute("CREATE TABLE public.orders (id bigint PRIMARY KEY)")
            connection.execute("INSERT INTO public.orders SELECT generate_series(1, 10)")

    def run_cli(self, command, reply="", contract=CONTRACT):
        return subprocess.run(
            ["migreat", command, str(contract)],
            env={**os.environ, "DATABASE_URL": self.dsn},
            input=reply, text=True, capture_output=True, timeout=10,
        )

    def schema_and_rows(self):
        with psycopg.connect(self.dsn) as connection:
            columns = connection.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'orders'
                ORDER BY ordinal_position
                """
            ).fetchall()
            rows = connection.execute("SELECT * FROM public.orders ORDER BY id").fetchall()
        return columns, rows

    def test_preview_is_read_only(self):
        before = self.schema_and_rows()
        result = self.run_cli("plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(DDL, result.stdout)
        self.assertIn("Existing rows will read NULL", result.stdout)
        self.assertEqual(self.schema_and_rows(), before)

    def test_cancel_apply_and_repeat(self):
        before = self.schema_and_rows()
        for reply in ("no\n", ""):
            with self.subTest(reply=reply):
                cancelled = self.run_cli("apply", reply)
                self.assertEqual(cancelled.returncode, 0, cancelled.stderr)
                self.assertIn("Cancelled.", cancelled.stdout)
                self.assertEqual(self.schema_and_rows(), before)

        applied = self.run_cli("apply", "yes\n")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertIn(DDL, applied.stdout)
        self.assertIn("Applied and verified.", applied.stdout)
        expected = (
            [("id", "bigint", "NO"), ("amount_cents", "bigint", "YES")],
            [(row_id, None) for row_id in range(1, 11)],
        )
        self.assertEqual(self.schema_and_rows(), expected)

        repeated = self.run_cli("apply")
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(repeated.stdout.strip(), "No changes.")
        self.assertEqual(self.schema_and_rows(), expected)

    def test_stale_preview_is_rejected(self):
        with subprocess.Popen(
            ["migreat", "apply", str(CONTRACT)],
            env={**os.environ, "DATABASE_URL": self.dsn},
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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
                with psycopg.connect(self.dsn) as connection:
                    connection.execute("ALTER TABLE public.orders ADD COLUMN intervening text")
                changed = self.schema_and_rows()
                _, stderr = process.communicate(b"yes\n", timeout=10)
                self.assertEqual(process.returncode, 1, stderr)
                self.assertIn(b"Plan is stale", stderr)
                self.assertEqual(self.schema_and_rows(), changed)
            finally:
                if process.poll() is None:
                    process.kill()

    def test_invalid_odcs_is_rejected(self):
        before = self.schema_and_rows()
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.yaml"
            invalid.write_text("kind: DataContract\n", encoding="utf-8")
            result = self.run_cli("apply", "yes\n", invalid)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Invalid ODCS contract", result.stderr)
        self.assertEqual(self.schema_and_rows(), before)

    def test_incompatible_existing_column_is_rejected(self):
        with psycopg.connect(self.dsn) as connection:
            connection.execute("ALTER TABLE public.orders ADD COLUMN amount_cents text")
        before = self.schema_and_rows()
        result = self.run_cli("apply", "yes\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("differs from the contract", result.stderr)
        self.assertEqual(self.schema_and_rows(), before)


if __name__ == "__main__":
    unittest.main()

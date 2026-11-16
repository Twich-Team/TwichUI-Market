"""Operational safety guards must reject real database names before any connection."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]


class MetadataOperationGuards(unittest.TestCase):
    def rejected(self, script, url):
        env={**os.environ,'DATABASE_URL':url,'PYTHONPATH':str(ROOT/'backend')}
        result=subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Refusing',result.stderr+result.stdout)
        # A connection error would mean the guard ran too late.
        self.assertNotIn('OperationalError',result.stderr)
        self.assertNotIn('could not translate',result.stderr)

    def test_migration_rejects_non_test_postgresql_without_connecting(self):
        self.rejected('verify-metadata-migration.py','postgresql+psycopg://invalid.invalid/market')

    def test_provider_rate_tools_reject_production_without_connecting(self):
        for script in ('verify-provider-rate-migration.py','verify-foreverdb-migration.py','benchmark-provider-rates.py'):
            self.rejected(script,'postgresql+psycopg://invalid.invalid/market')

    def test_provider_rate_tools_require_postgresql(self):
        for script in ('verify-provider-rate-migration.py','verify-foreverdb-migration.py','benchmark-provider-rates.py'):
            self.rejected(script,'sqlite:////tmp/market_test')

    def test_archive_migration_rejects_non_test_database_before_connecting(self):
        self.rejected('verify-archive-migration.py','postgresql+psycopg://invalid.invalid/market')
        self.rejected('verify-archive-migration.py','sqlite:////tmp/market_test')

    def test_migration_rejects_sqlite_even_with_test_name(self):
        self.rejected('verify-metadata-migration.py','sqlite:////tmp/market_test')

    def test_benchmark_rejects_non_test_postgresql_without_connecting(self):
        self.rejected('benchmark-metadata-recovery.py','postgresql+psycopg://invalid.invalid/market')

    def test_benchmark_rejects_sqlite_even_with_test_name(self):
        self.rejected('benchmark-metadata-recovery.py','sqlite:////tmp/market_test')


if __name__=='__main__':unittest.main()

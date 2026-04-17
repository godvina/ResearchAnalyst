"""Aurora Serverless v2 connection management via RDS Proxy.

Environment variables:
    AURORA_PROXY_ENDPOINT — RDS Proxy endpoint
    AURORA_DB_NAME        — Database name
    AURORA_SECRET_ARN     — Secrets Manager ARN for DB credentials
    DB_PORT               — Database port (default 5432)
    DB_MIN_CONN           — Minimum connections in pool (default 1)
    DB_MAX_CONN           — Maximum connections in pool (default 10)
"""

import json
import os
from contextlib import contextmanager
from typing import Generator

import boto3
import psycopg2
from psycopg2 import pool

_cached_secret: dict | None = None


def _get_env(name: str, default: str | None = None) -> str:
    """Return an environment variable or raise if missing and no default."""
    value = os.environ.get(name, default)
    if value is None:
        raise EnvironmentError(f"Required environment variable {name} is not set")
    return value


def _get_db_secret() -> dict:
    """Fetch and cache DB credentials from Secrets Manager."""
    global _cached_secret
    if _cached_secret is not None:
        return _cached_secret
    secret_arn = _get_env("AURORA_SECRET_ARN")
    try:
        sm = boto3.client("secretsmanager")
        resp = sm.get_secret_value(SecretId=secret_arn)
        _cached_secret = json.loads(resp["SecretString"])
        if not _cached_secret.get("password"):
            raise ValueError("Secret missing 'password' field")
        return _cached_secret
    except Exception as e:
        _cached_secret = None  # Don't cache failures
        raise RuntimeError(f"Failed to get DB secret from {secret_arn}: {e}") from e


class ConnectionManager:
    """Manages a psycopg2 connection pool for Aurora Serverless v2 via RDS Proxy."""

    def __init__(self) -> None:
        self._pool: pool.SimpleConnectionPool | None = None

    def _create_pool(self) -> pool.SimpleConnectionPool:
        secret = _get_db_secret()
        return pool.SimpleConnectionPool(
            minconn=int(_get_env("DB_MIN_CONN", "1")),
            maxconn=int(_get_env("DB_MAX_CONN", "10")),
            host=_get_env("AURORA_PROXY_ENDPOINT"),
            port=int(_get_env("DB_PORT", "5432")),
            dbname=_get_env("AURORA_DB_NAME"),
            user=secret.get("username", "postgres"),
            password=secret.get("password", ""),
            sslmode="require",
        )

    @property
    def pool(self) -> pool.SimpleConnectionPool:
        if self._pool is None or self._pool.closed:
            self._pool = self._create_pool()
        return self._pool

    @contextmanager
    def connection(self) -> Generator:
        """Yield a connection from the pool, returning it when done."""
        conn = self.pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self.pool.putconn(conn)

    @contextmanager
    def cursor(self) -> Generator:
        """Yield a cursor (auto-commits on success, rolls back on error)."""
        with self.connection() as conn:
            cur = conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool is not None and not self._pool.closed:
            self._pool.closeall()


# Module-level singleton for convenience.
connection_manager = ConnectionManager()

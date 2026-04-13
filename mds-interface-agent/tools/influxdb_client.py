"""InfluxDB client abstraction supporting both v1 (InfluxQL) and v2 (Flux).

Adapted from arjuntony/mds-san-troubleshooter for the LangGraph agent.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.config import (
    INFLUXDB_VERSION, INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG,
    INFLUXDB_BUCKET, INFLUXDB_USERNAME, INFLUXDB_PASSWORD,
)


@dataclass
class InfluxQueryResult:
    """Unified result format regardless of InfluxDB version."""

    columns: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)
    raw_query: str = ""
    execution_time_ms: float = 0.0


class InfluxV1Client:
    """InfluxDB 1.x client using InfluxQL."""

    def __init__(self, url: str, username: str, password: str, database: str):
        from influxdb import InfluxDBClient

        host = url.replace("http://", "").replace("https://", "").split(":")[0]
        port = int(url.split(":")[-1]) if ":" in url.split("//")[-1] else 8086
        ssl = url.startswith("https")

        self.client = InfluxDBClient(
            host=host, port=port, username=username, password=password,
            database=database, ssl=ssl,
        )
        self.database = database

    def query(self, query: str) -> InfluxQueryResult:
        start = time.monotonic()
        result = self.client.query(query)
        elapsed = (time.monotonic() - start) * 1000

        rows = []
        columns = []
        for table in result.raw.get("series", []):
            columns = table.get("columns", [])
            for values in table.get("values", []):
                rows.append(dict(zip(columns, values)))

        return InfluxQueryResult(
            columns=columns, rows=rows, raw_query=query,
            execution_time_ms=round(elapsed, 2),
        )

    def list_measurements(self) -> list[str]:
        result = self.query("SHOW MEASUREMENTS")
        return [row.get("name", "") for row in result.rows]

    def health_check(self) -> bool:
        try:
            self.client.ping()
            return True
        except Exception:
            return False


class InfluxV2Client:
    """InfluxDB 2.x client using Flux queries."""

    def __init__(self, url: str, token: str, org: str, bucket: str):
        from influxdb_client import InfluxDBClient as InfluxDB2Client

        self.client = InfluxDB2Client(url=url, token=token, org=org)
        self.query_api = self.client.query_api()
        self.bucket = bucket
        self.org = org

    def query(self, query: str) -> InfluxQueryResult:
        start = time.monotonic()
        tables = self.query_api.query(query, org=self.org)
        elapsed = (time.monotonic() - start) * 1000

        rows = []
        columns = set()
        for table in tables:
            for record in table.records:
                row = record.values
                columns.update(row.keys())
                rows.append(row)

        return InfluxQueryResult(
            columns=sorted(columns), rows=rows, raw_query=query,
            execution_time_ms=round(elapsed, 2),
        )

    def list_measurements(self) -> list[str]:
        flux = f"""
        import "influxdata/influxdb/schema"
        schema.measurements(bucket: "{self.bucket}")
        """
        result = self.query(flux)
        return [row.get("_value", "") for row in result.rows]

    def health_check(self) -> bool:
        try:
            health = self.client.health()
            return health.status == "pass"
        except Exception:
            return False


# Singleton client — initialized on first use
_client = None


def get_influx_client() -> InfluxV1Client | InfluxV2Client | None:
    """Factory: create/return the right client based on config. Returns None if not configured."""
    global _client
    if _client is not None:
        return _client

    if not INFLUXDB_URL:
        return None

    if INFLUXDB_VERSION == "2":
        _client = InfluxV2Client(
            url=INFLUXDB_URL, token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORG, bucket=INFLUXDB_BUCKET,
        )
    else:
        _client = InfluxV1Client(
            url=INFLUXDB_URL, username=INFLUXDB_USERNAME,
            password=INFLUXDB_PASSWORD, database=INFLUXDB_BUCKET,
        )
    return _client

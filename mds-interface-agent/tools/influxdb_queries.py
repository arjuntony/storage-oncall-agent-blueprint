"""Query builders for InfluxDB v1 (InfluxQL) and v2 (Flux).

Each builder takes structured parameters and returns a safe, parameterized query string.
The agent never writes raw queries — these builders are the only path to InfluxDB.

Adapted from arjuntony/mds-san-troubleshooter.
"""

from __future__ import annotations

import re

from app.config import INFLUXDB_VERSION, INFLUXDB_BUCKET

# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

_SAFE_PATTERN = re.compile(r"^[a-zA-Z0-9_\-/.:]+$")


def _sanitize(value: str) -> str:
    """Escape values used in queries to prevent injection."""
    if not value:
        return ""
    if _SAFE_PATTERN.match(value):
        return value
    return re.sub(r"['\";\\]", "", value)


def _time_range_clause(time_range: str, version: str) -> str:
    tr = _sanitize(time_range) or "1h"
    if version == "1":
        return f"time > now() - {tr}"
    return tr


# ---------------------------------------------------------------------------
# Field sets
# ---------------------------------------------------------------------------

_ERROR_FIELDS = "crc_errors, link_failures, signal_losses, sync_losses, invalid_tx_words"
_TRAFFIC_FIELDS = "tx_frames, rx_frames, tx_bytes, rx_bytes, input_discards, output_discards"
_CONGESTION_FIELDS = "bb_credit_zero, timeout_discards, credit_loss"
_ALL_COUNTER_FIELDS = f"{_ERROR_FIELDS}, {_TRAFFIC_FIELDS}, {_CONGESTION_FIELDS}"

_COUNTER_MAP = {
    "errors": _ERROR_FIELDS,
    "traffic": _TRAFFIC_FIELDS,
    "congestion": _CONGESTION_FIELDS,
    "all": _ALL_COUNTER_FIELDS,
}


# ---------------------------------------------------------------------------
# InfluxQL builders (v1)
# ---------------------------------------------------------------------------

def _influxql_interface_counters(
    switch: str, interface: str | None, time_range: str, counter_type: str
) -> str:
    fields = _COUNTER_MAP.get(counter_type, _ALL_COUNTER_FIELDS)
    where = [f"switch = '{_sanitize(switch)}'", _time_range_clause(time_range, "1")]
    if interface:
        where.append(f"interface = '{_sanitize(interface)}'")
    return (
        f"SELECT {fields} FROM interface_counters "
        f"WHERE {' AND '.join(where)} ORDER BY time DESC LIMIT 200"
    )


def _influxql_port_status(switch: str, interface: str | None, filter_state: str) -> str:
    where = [f"switch = '{_sanitize(switch)}'"]
    if interface:
        where.append(f"interface = '{_sanitize(interface)}'")
    if filter_state and filter_state != "all":
        where.append(f"oper_state = '{_sanitize(filter_state)}'")
    return (
        f"SELECT * FROM port_status WHERE {' AND '.join(where)} "
        "ORDER BY time DESC LIMIT 500"
    )


def _influxql_san_analytics(
    switch: str | None, initiator_wwn: str | None, target_wwn: str | None,
    port: str | None, metric: str, time_range: str, top_n: int,
) -> str:
    metric_fields = {
        "latency": "read_latency_us, write_latency_us",
        "iops": "read_iops, write_iops",
        "throughput": "read_bytes, write_bytes",
        "aborts": "io_aborts",
        "all": "read_iops, write_iops, read_latency_us, write_latency_us, read_bytes, write_bytes, io_aborts",
    }
    fields = metric_fields.get(metric, metric_fields["all"])
    where = [_time_range_clause(time_range, "1")]
    if switch:
        where.append(f"switch = '{_sanitize(switch)}'")
    if initiator_wwn:
        where.append(f"initiator_wwn = '{_sanitize(initiator_wwn)}'")
    if target_wwn:
        where.append(f"target_wwn = '{_sanitize(target_wwn)}'")
    if port:
        where.append(f"port = '{_sanitize(port)}'")
    return (
        f"SELECT {fields} FROM san_analytics "
        f"WHERE {' AND '.join(where)} ORDER BY time DESC LIMIT {int(top_n)}"
    )


def _influxql_flogi(
    switch: str | None, interface: str | None, wwpn: str | None, vsan: int | None
) -> str:
    where: list[str] = []
    if switch:
        where.append(f"switch = '{_sanitize(switch)}'")
    if interface:
        where.append(f"interface = '{_sanitize(interface)}'")
    if wwpn:
        where.append(f"wwpn = '{_sanitize(wwpn)}'")
    if vsan is not None:
        where.append(f"vsan = '{int(vsan)}'")
    where_clause = f" WHERE {' AND '.join(where)}" if where else ""
    return f"SELECT * FROM flogi_database{where_clause} ORDER BY time DESC LIMIT 500"


def _influxql_zone_info(
    switch: str | None, vsan: int | None, zone_name: str | None, member_wwn: str | None
) -> str:
    where: list[str] = []
    if switch:
        where.append(f"switch = '{_sanitize(switch)}'")
    if vsan is not None:
        where.append(f"vsan = '{int(vsan)}'")
    if zone_name:
        where.append(f"zone_name = '{_sanitize(zone_name)}'")
    if member_wwn:
        where.append(f"member_value = '{_sanitize(member_wwn)}'")
    where_clause = f" WHERE {' AND '.join(where)}" if where else ""
    return f"SELECT * FROM zone_config{where_clause} ORDER BY time DESC LIMIT 1000"


def _influxql_sfp_diagnostics(switch: str, interface: str | None) -> str:
    where = [f"switch = '{_sanitize(switch)}'"]
    if interface:
        where.append(f"interface = '{_sanitize(interface)}'")
    return (
        f"SELECT interface, temperature, tx_power, rx_power, current, voltage "
        f"FROM sfp_diagnostics WHERE {' AND '.join(where)} ORDER BY time DESC LIMIT 500"
    )


def _influxql_syslog(
    switch: str | None, severity: str | None, search_pattern: str | None,
    time_range: str, limit: int,
) -> str:
    where = [_time_range_clause(time_range, "1")]
    if switch:
        where.append(f"switch = '{_sanitize(switch)}'")
    if severity:
        where.append(f"severity = '{_sanitize(severity)}'")
    if search_pattern:
        where.append(f"message =~ /{_sanitize(search_pattern)}/")
    return (
        f"SELECT * FROM syslog WHERE {' AND '.join(where)} "
        f"ORDER BY time DESC LIMIT {int(limit)}"
    )


def _influxql_switch_inventory() -> str:
    return (
        "SELECT last(cpu_percent) AS cpu, last(memory_used_percent) AS memory "
        "FROM system_resources GROUP BY switch"
    )


def _influxql_device_aliases(alias_name: str | None, wwpn: str | None) -> str:
    where: list[str] = []
    if alias_name:
        where.append(f"alias_name =~ /{_sanitize(alias_name)}/")
    if wwpn:
        where.append(f"wwpn = '{_sanitize(wwpn)}'")
    where_clause = f" WHERE {' AND '.join(where)}" if where else ""
    return f"SELECT * FROM device_alias{where_clause} ORDER BY time DESC LIMIT 500"


# ---------------------------------------------------------------------------
# Flux builders (v2)
# ---------------------------------------------------------------------------

def _flux_base(bucket: str, time_range: str, measurement: str) -> str:
    return (
        f'from(bucket: "{bucket}")\n'
        f"  |> range(start: -{_sanitize(time_range)})\n"
        f'  |> filter(fn: (r) => r._measurement == "{measurement}")\n'
    )


def _flux_tag_filter(tag: str, value: str) -> str:
    return f'  |> filter(fn: (r) => r.{tag} == "{_sanitize(value)}")\n'


def _flux_pivot_sort_limit(limit: int = 200) -> str:
    return (
        '  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")\n'
        '  |> sort(columns: ["_time"], desc: true)\n'
        f"  |> limit(n: {int(limit)})\n"
    )


def _flux_interface_counters(
    switch: str, interface: str | None, time_range: str, counter_type: str
) -> str:
    bucket = INFLUXDB_BUCKET
    q = _flux_base(bucket, time_range, "interface_counters")
    q += _flux_tag_filter("switch", switch)
    if interface:
        q += _flux_tag_filter("interface", interface)
    field_lists = {
        "errors": ["crc_errors", "link_failures", "signal_losses", "sync_losses", "invalid_tx_words"],
        "traffic": ["tx_frames", "rx_frames", "tx_bytes", "rx_bytes", "input_discards", "output_discards"],
        "congestion": ["bb_credit_zero", "timeout_discards", "credit_loss"],
    }
    if counter_type != "all" and counter_type in field_lists:
        fields = field_lists[counter_type]
        cond = " or ".join([f'r._field == "{f}"' for f in fields])
        q += f"  |> filter(fn: (r) => {cond})\n"
    q += _flux_pivot_sort_limit()
    return q


def _flux_port_status(switch: str, interface: str | None, filter_state: str) -> str:
    bucket = INFLUXDB_BUCKET
    q = _flux_base(bucket, "1h", "port_status")
    q += _flux_tag_filter("switch", switch)
    if interface:
        q += _flux_tag_filter("interface", interface)
    q += _flux_pivot_sort_limit(500)
    return q


def _flux_san_analytics(
    switch: str | None, initiator_wwn: str | None, target_wwn: str | None,
    port: str | None, metric: str, time_range: str, top_n: int,
) -> str:
    bucket = INFLUXDB_BUCKET
    q = _flux_base(bucket, time_range, "san_analytics")
    if switch:
        q += _flux_tag_filter("switch", switch)
    if initiator_wwn:
        q += _flux_tag_filter("initiator_wwn", initiator_wwn)
    if target_wwn:
        q += _flux_tag_filter("target_wwn", target_wwn)
    if port:
        q += _flux_tag_filter("port", port)
    q += _flux_pivot_sort_limit(top_n)
    return q


def _flux_flogi(
    switch: str | None, interface: str | None, wwpn: str | None, vsan: int | None
) -> str:
    bucket = INFLUXDB_BUCKET
    q = _flux_base(bucket, "1h", "flogi_database")
    if switch:
        q += _flux_tag_filter("switch", switch)
    if interface:
        q += _flux_tag_filter("interface", interface)
    if wwpn:
        q += _flux_tag_filter("wwpn", wwpn)
    if vsan is not None:
        q += _flux_tag_filter("vsan", str(vsan))
    q += _flux_pivot_sort_limit(500)
    return q


def _flux_zone_info(
    switch: str | None, vsan: int | None, zone_name: str | None, member_wwn: str | None
) -> str:
    bucket = INFLUXDB_BUCKET
    q = _flux_base(bucket, "1h", "zone_config")
    if switch:
        q += _flux_tag_filter("switch", switch)
    if vsan is not None:
        q += _flux_tag_filter("vsan", str(vsan))
    if zone_name:
        q += _flux_tag_filter("zone_name", zone_name)
    q += _flux_pivot_sort_limit(1000)
    return q


def _flux_sfp_diagnostics(switch: str, interface: str | None) -> str:
    bucket = INFLUXDB_BUCKET
    q = _flux_base(bucket, "1h", "sfp_diagnostics")
    q += _flux_tag_filter("switch", switch)
    if interface:
        q += _flux_tag_filter("interface", interface)
    q += _flux_pivot_sort_limit(500)
    return q


def _flux_syslog(
    switch: str | None, severity: str | None, search_pattern: str | None,
    time_range: str, limit: int,
) -> str:
    bucket = INFLUXDB_BUCKET
    q = ""
    if search_pattern:
        q = 'import "strings"\n'
    q += _flux_base(bucket, time_range, "syslog")
    if switch:
        q += _flux_tag_filter("switch", switch)
    if severity:
        q += _flux_tag_filter("severity", severity)
    if search_pattern:
        q += f'  |> filter(fn: (r) => strings.containsStr(v: r.message, substr: "{_sanitize(search_pattern)}"))\n'
    q += _flux_pivot_sort_limit(limit)
    return q


def _flux_switch_inventory() -> str:
    bucket = INFLUXDB_BUCKET
    return (
        f'from(bucket: "{bucket}")\n'
        "  |> range(start: -1h)\n"
        '  |> filter(fn: (r) => r._measurement == "system_resources")\n'
        "  |> last()\n"
        '  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")\n'
        '  |> group(columns: ["switch"])\n'
    )


def _flux_device_aliases(alias_name: str | None, wwpn: str | None) -> str:
    bucket = INFLUXDB_BUCKET
    q = _flux_base(bucket, "1h", "device_alias")
    if wwpn:
        q += _flux_tag_filter("wwpn", wwpn)
    q += _flux_pivot_sort_limit(500)
    return q


# ---------------------------------------------------------------------------
# Public dispatch functions
# ---------------------------------------------------------------------------

def _is_v2() -> bool:
    return INFLUXDB_VERSION == "2"


def build_interface_counters_query(
    switch: str, interface: str | None, time_range: str, counter_type: str
) -> str:
    if _is_v2():
        return _flux_interface_counters(switch, interface, time_range, counter_type)
    return _influxql_interface_counters(switch, interface, time_range, counter_type)


def build_port_status_query(switch: str, interface: str | None, filter_state: str) -> str:
    if _is_v2():
        return _flux_port_status(switch, interface, filter_state)
    return _influxql_port_status(switch, interface, filter_state)


def build_san_analytics_query(
    switch: str | None, initiator_wwn: str | None, target_wwn: str | None,
    port: str | None, metric: str, time_range: str, top_n: int,
) -> str:
    if _is_v2():
        return _flux_san_analytics(switch, initiator_wwn, target_wwn, port, metric, time_range, top_n)
    return _influxql_san_analytics(switch, initiator_wwn, target_wwn, port, metric, time_range, top_n)


def build_flogi_query(
    switch: str | None, interface: str | None, wwpn: str | None, vsan: int | None
) -> str:
    if _is_v2():
        return _flux_flogi(switch, interface, wwpn, vsan)
    return _influxql_flogi(switch, interface, wwpn, vsan)


def build_zone_info_query(
    switch: str | None, vsan: int | None, zone_name: str | None, member_wwn: str | None
) -> str:
    if _is_v2():
        return _flux_zone_info(switch, vsan, zone_name, member_wwn)
    return _influxql_zone_info(switch, vsan, zone_name, member_wwn)


def build_sfp_diagnostics_query(switch: str, interface: str | None) -> str:
    if _is_v2():
        return _flux_sfp_diagnostics(switch, interface)
    return _influxql_sfp_diagnostics(switch, interface)


def build_syslog_query(
    switch: str | None, severity: str | None, search_pattern: str | None,
    time_range: str, limit: int,
) -> str:
    if _is_v2():
        return _flux_syslog(switch, severity, search_pattern, time_range, limit)
    return _influxql_syslog(switch, severity, search_pattern, time_range, limit)


def build_switch_inventory_query() -> str:
    if _is_v2():
        return _flux_switch_inventory()
    return _influxql_switch_inventory()


def build_device_aliases_query(alias_name: str | None, wwpn: str | None) -> str:
    if _is_v2():
        return _flux_device_aliases(alias_name, wwpn)
    return _influxql_device_aliases(alias_name, wwpn)

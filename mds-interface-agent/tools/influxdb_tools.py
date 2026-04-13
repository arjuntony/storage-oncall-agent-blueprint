"""InfluxDB-backed LangChain tools for the MDS interface triage agent.

These tools query InfluxDB for time-series interface counters, port status,
SAN analytics, FLOGI, zoning, SFP diagnostics, syslog, and device aliases.

When INFLUXDB_URL is not set, tools return an error telling the agent to
fall back to the synthetic LIVE tools or show-tech.
"""

from __future__ import annotations

from langchain_core.tools import tool

from tools.influxdb_client import get_influx_client
from tools.influxdb_queries import (
    build_interface_counters_query,
    build_port_status_query,
    build_san_analytics_query,
    build_flogi_query,
    build_zone_info_query,
    build_sfp_diagnostics_query,
    build_syslog_query,
    build_switch_inventory_query,
    build_device_aliases_query,
)


def _query_influx(query: str) -> dict:
    """Run a query against InfluxDB and return rows + metadata."""
    client = get_influx_client()
    if client is None:
        return {"error": "InfluxDB not configured — set INFLUXDB_URL in .env. Use LIVE (NX-API) tools instead."}
    result = client.query(query)
    return {
        "rows": result.rows,
        "row_count": len(result.rows),
        "execution_time_ms": result.execution_time_ms,
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def influx_get_switch_inventory() -> dict:
    """List all monitored MDS switches from InfluxDB with CPU and memory usage.

    Call this first to discover available switch names in the time-series database.
    """
    query = build_switch_inventory_query()
    result = _query_influx(query)
    if "error" in result:
        return result
    return {"switches": result["rows"], "count": result["row_count"]}


@tool
def influx_get_interface_counters(
    switch_name: str,
    interface: str = "",
    time_range: str = "1h",
    counter_type: str = "all",
) -> dict:
    """Query interface error/traffic counters from InfluxDB for a switch or port.

    Returns CRC errors, link failures, signal loss, sync loss, tx/rx frames,
    BB credit zero, timeout discards, credit loss — trended over time.

    Args:
        switch_name: MDS switch hostname (e.g. lva1-mds01)
        interface: FC interface (e.g. fc1/3). Empty = all interfaces.
        time_range: Lookback window: 1h, 6h, 24h, 7d. Default 1h.
        counter_type: errors, traffic, congestion, or all. Default all.
    """
    query = build_interface_counters_query(
        switch=switch_name,
        interface=interface or None,
        time_range=time_range,
        counter_type=counter_type,
    )
    result = _query_influx(query)
    if "error" in result:
        return result
    return {
        "switch": switch_name,
        "interface": interface or "all",
        "time_range": time_range,
        "data": result["rows"],
        "row_count": result["row_count"],
    }


@tool
def influx_get_port_status(
    switch_name: str,
    interface: str = "",
    filter_oper_state: str = "all",
) -> dict:
    """Get port operational status from InfluxDB — admin state, oper state, mode, speed, VSAN.

    Args:
        switch_name: MDS switch hostname (e.g. lva1-mds01)
        interface: FC interface. Empty = all ports.
        filter_oper_state: up, down, trunking, or all. Default all.
    """
    query = build_port_status_query(
        switch=switch_name,
        interface=interface or None,
        filter_state=filter_oper_state,
    )
    result = _query_influx(query)
    if "error" in result:
        return result
    return {
        "switch": switch_name,
        "ports": result["rows"],
        "count": result["row_count"],
    }


@tool
def influx_get_san_analytics(
    switch_name: str = "",
    initiator_wwn: str = "",
    target_wwn: str = "",
    port: str = "",
    metric: str = "all",
    time_range: str = "1h",
    top_n: int = 10,
) -> dict:
    """Query SAN Analytics (SCSI flow analytics) from InfluxDB.

    Returns per-flow IOPS, read/write latency, throughput, IO aborts.
    Filter by initiator, target, port, or switch.

    Args:
        switch_name: MDS switch hostname. Empty = all switches.
        initiator_wwn: Host initiator WWPN to filter.
        target_wwn: Storage target WWPN to filter.
        port: Switch port to filter flows.
        metric: latency, iops, throughput, aborts, or all. Default all.
        time_range: Lookback window. Default 1h.
        top_n: Return top N flows. Default 10.
    """
    query = build_san_analytics_query(
        switch=switch_name or None,
        initiator_wwn=initiator_wwn or None,
        target_wwn=target_wwn or None,
        port=port or None,
        metric=metric,
        time_range=time_range,
        top_n=top_n,
    )
    result = _query_influx(query)
    if "error" in result:
        return result
    return {"flows": result["rows"], "count": result["row_count"]}


@tool
def influx_get_flogi_database(
    switch_name: str = "",
    interface: str = "",
    wwpn: str = "",
    vsan: int = 0,
) -> dict:
    """Query FLOGI database from InfluxDB — which WWN is logged into which port.

    Args:
        switch_name: MDS switch hostname.
        interface: FC interface to filter.
        wwpn: Search for a specific WWPN.
        vsan: VSAN ID to filter. 0 = all.
    """
    query = build_flogi_query(
        switch=switch_name or None,
        interface=interface or None,
        wwpn=wwpn or None,
        vsan=vsan if vsan > 0 else None,
    )
    result = _query_influx(query)
    if "error" in result:
        return result
    return {"entries": result["rows"], "count": result["row_count"]}


@tool
def influx_get_zone_info(
    switch_name: str = "",
    vsan: int = 0,
    zone_name: str = "",
    member_wwn: str = "",
) -> dict:
    """Query zoning config from InfluxDB — active zoneset, members, device-alias mappings.

    Args:
        switch_name: MDS switch hostname.
        vsan: VSAN ID. 0 = all.
        zone_name: Search for a specific zone.
        member_wwn: Find all zones containing this WWN.
    """
    query = build_zone_info_query(
        switch=switch_name or None,
        vsan=vsan if vsan > 0 else None,
        zone_name=zone_name or None,
        member_wwn=member_wwn or None,
    )
    result = _query_influx(query)
    if "error" in result:
        return result
    return {"zones": result["rows"], "count": result["row_count"]}


@tool
def influx_get_sfp_diagnostics(
    switch_name: str,
    interface: str = "",
    alert_only: bool = False,
) -> dict:
    """Get SFP transceiver DOM data from InfluxDB — temperature, tx/rx power, current.

    Low rx power = dirty/bad fiber. High temp = failing SFP.

    Args:
        switch_name: MDS switch hostname.
        interface: Specific port. Empty = all ports.
        alert_only: Only return SFPs outside normal thresholds.
    """
    query = build_sfp_diagnostics_query(
        switch=switch_name,
        interface=interface or None,
    )
    result = _query_influx(query)
    if "error" in result:
        return result

    rows = result["rows"]
    if alert_only:
        rows = [
            r for r in rows
            if (r.get("rx_power") is not None and float(r["rx_power"]) < -10)
            or (r.get("temperature") is not None and float(r["temperature"]) > 60)
        ]

    return {"switch": switch_name, "sfps": rows, "count": len(rows)}


@tool
def influx_get_syslog_messages(
    switch_name: str = "",
    severity: str = "",
    search_pattern: str = "",
    time_range: str = "24h",
    limit: int = 50,
) -> dict:
    """Search syslog messages in InfluxDB — filter by switch, severity, text pattern.

    Critical for correlating errors with events over time.

    Args:
        switch_name: MDS switch hostname. Empty = all switches.
        severity: emergency, alert, critical, error, warning, notice, info, debug.
        search_pattern: Text pattern to search in messages.
        time_range: Lookback window. Default 24h.
        limit: Max results. Default 50.
    """
    query = build_syslog_query(
        switch=switch_name or None,
        severity=severity or None,
        search_pattern=search_pattern or None,
        time_range=time_range,
        limit=limit,
    )
    result = _query_influx(query)
    if "error" in result:
        return result
    return {"messages": result["rows"], "count": result["row_count"]}


@tool
def influx_get_device_aliases(
    alias_name: str = "",
    wwpn: str = "",
) -> dict:
    """Query device-alias database in InfluxDB — map friendly names to WWPNs.

    Args:
        alias_name: Search by alias name pattern.
        wwpn: Find alias for a specific WWPN.
    """
    query = build_device_aliases_query(
        alias_name=alias_name or None,
        wwpn=wwpn or None,
    )
    result = _query_influx(query)
    if "error" in result:
        return result
    return {"aliases": result["rows"], "count": result["row_count"]}


# All InfluxDB tools for easy import
INFLUXDB_TOOLS = [
    influx_get_switch_inventory,
    influx_get_interface_counters,
    influx_get_port_status,
    influx_get_san_analytics,
    influx_get_flogi_database,
    influx_get_zone_info,
    influx_get_sfp_diagnostics,
    influx_get_syslog_messages,
    influx_get_device_aliases,
]

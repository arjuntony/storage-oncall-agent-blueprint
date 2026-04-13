"""MDS 9710 NX-API tools — synthetic data for POC.

In production, each function makes an HTTP POST to the MDS NX-API endpoint:
  POST https://<hostname>/ins
  Content-Type: application/json
  Body: {"ins_api": {"version": "1", "type": "cli_show", "chunk": "0",
         "sid": "1", "input": "show interface brief", "output_format": "json"}}

For POC, all data is synthetic Python dicts.
"""

from langchain_core.tools import tool


# ═══════════════════════════════════════════════════════════════════
# SYNTHETIC DATA
# ═══════════════════════════════════════════════════════════════════

SWITCH_INTERFACES = {
    "lva1-mds01": [
        {
            "interface": "fc1/1", "oper_status": "up", "admin_status": "up",
            "speed": "32Gbps", "port_mode": "F", "vsan": 100,
            "connected_wwpn": "21:00:00:24:ff:4a:12:01",
            "connected_device": "stor-lva1-array05-ct0-fc0",
            "description": "storage-array05-controller0-port0",
        },
        {
            "interface": "fc1/2", "oper_status": "up", "admin_status": "up",
            "speed": "32Gbps", "port_mode": "F", "vsan": 100,
            "connected_wwpn": "21:00:00:24:ff:4a:12:02",
            "connected_device": "stor-lva1-array05-ct0-fc1",
            "description": "storage-array05-controller0-port1",
        },
        {
            "interface": "fc1/3", "oper_status": "down", "admin_status": "up",
            "speed": "auto", "port_mode": "F", "vsan": 100,
            "connected_wwpn": "21:00:00:24:ff:4a:12:03",
            "connected_device": "stor-lva1-array05-ct1-fc0",
            "description": "storage-array05-controller1-port0",
            "last_state_change": "2026-04-12T08:15:00Z",
            "down_reason": "link_failure(link_failure)",
        },
        {
            "interface": "fc1/4", "oper_status": "up", "admin_status": "up",
            "speed": "32Gbps", "port_mode": "F", "vsan": 100,
            "connected_wwpn": "21:00:00:24:ff:4a:12:04",
            "connected_device": "stor-lva1-array05-ct1-fc1",
            "description": "storage-array05-controller1-port1",
        },
        {
            "interface": "fc1/5", "oper_status": "up", "admin_status": "up",
            "speed": "32Gbps", "port_mode": "F", "vsan": 100,
            "connected_wwpn": "50:00:09:72:08:60:2a:00",
            "connected_device": "esxi-lva1-host10-hba0",
            "description": "esxi-host10-vmhba2",
        },
        {
            "interface": "fc1/6", "oper_status": "up", "admin_status": "up",
            "speed": "32Gbps", "port_mode": "F", "vsan": 100,
            "connected_wwpn": "50:00:09:72:08:60:2a:01",
            "connected_device": "esxi-lva1-host11-hba0",
            "description": "esxi-host11-vmhba2",
        },
        {
            "interface": "fc1/7", "oper_status": "up", "admin_status": "up",
            "speed": "32Gbps", "port_mode": "F", "vsan": 100,
            "connected_wwpn": "50:00:09:72:08:60:2a:02",
            "connected_device": "esxi-lva1-host12-hba0",
            "description": "esxi-host12-vmhba2",
        },
        {
            "interface": "fc1/47", "oper_status": "up", "admin_status": "up",
            "speed": "32Gbps", "port_mode": "TE", "vsan": "1,100",
            "connected_wwpn": "20:01:00:0d:ec:6a:40:01",
            "connected_device": "lva1-mds02",
            "description": "ISL-to-mds02-po1-member",
            "port_channel": 1,
        },
        {
            "interface": "fc1/48", "oper_status": "up", "admin_status": "up",
            "speed": "32Gbps", "port_mode": "TE", "vsan": "1,100",
            "connected_wwpn": "20:02:00:0d:ec:6a:40:01",
            "connected_device": "lva1-mds02",
            "description": "ISL-to-mds02-po1-member",
            "port_channel": 1,
        },
    ],
}

INTERFACE_COUNTERS = {
    "lva1-mds01": {
        "fc1/1": {
            "frames_in": 48523019, "frames_out": 51203847,
            "crc_errors": 0, "link_failures": 0, "sync_losses": 0,
            "signal_losses": 0, "invalid_tx_words": 0,
            "credit_loss": 0, "timeout_discards": 0,
            "encoding_errors": 0, "too_long_frames": 0,
            "too_short_frames": 0, "input_errors": 0, "output_errors": 0,
            "b2b_credits_remaining": 16, "b2b_credits_total": 16,
        },
        "fc1/2": {
            "frames_in": 42150233, "frames_out": 44890122,
            "crc_errors": 12, "link_failures": 3, "sync_losses": 1,
            "signal_losses": 0, "invalid_tx_words": 0,
            "credit_loss": 0, "timeout_discards": 0,
            "encoding_errors": 0, "too_long_frames": 0,
            "too_short_frames": 0, "input_errors": 12, "output_errors": 0,
            "b2b_credits_remaining": 14, "b2b_credits_total": 16,
        },
        "fc1/3": {
            "frames_in": 0, "frames_out": 0,
            "crc_errors": 892, "link_failures": 47, "sync_losses": 15,
            "signal_losses": 3, "invalid_tx_words": 8,
            "credit_loss": 0, "timeout_discards": 0,
            "encoding_errors": 23, "too_long_frames": 0,
            "too_short_frames": 0, "input_errors": 938, "output_errors": 0,
            "b2b_credits_remaining": 0, "b2b_credits_total": 16,
            "last_counter_clear": "never",
        },
        "fc1/4": {
            "frames_in": 39802451, "frames_out": 41203098,
            "crc_errors": 0, "link_failures": 0, "sync_losses": 0,
            "signal_losses": 0, "invalid_tx_words": 0,
            "credit_loss": 0, "timeout_discards": 0,
            "encoding_errors": 0, "too_long_frames": 0,
            "too_short_frames": 0, "input_errors": 0, "output_errors": 0,
            "b2b_credits_remaining": 16, "b2b_credits_total": 16,
        },
        "fc1/5": {
            "frames_in": 28190442, "frames_out": 30120887,
            "crc_errors": 0, "link_failures": 0, "sync_losses": 0,
            "signal_losses": 0, "invalid_tx_words": 0,
            "credit_loss": 0, "timeout_discards": 0,
            "encoding_errors": 0, "too_long_frames": 0,
            "too_short_frames": 0, "input_errors": 0, "output_errors": 0,
            "b2b_credits_remaining": 16, "b2b_credits_total": 16,
        },
        "fc1/47": {
            "frames_in": 982304551, "frames_out": 1002405887,
            "crc_errors": 0, "link_failures": 0, "sync_losses": 0,
            "signal_losses": 0, "invalid_tx_words": 0,
            "credit_loss": 0, "timeout_discards": 0,
            "encoding_errors": 0, "too_long_frames": 0,
            "too_short_frames": 0, "input_errors": 0, "output_errors": 0,
            "b2b_credits_remaining": 32, "b2b_credits_total": 32,
        },
        "fc1/48": {
            "frames_in": 978102334, "frames_out": 998301002,
            "crc_errors": 0, "link_failures": 0, "sync_losses": 0,
            "signal_losses": 0, "invalid_tx_words": 0,
            "credit_loss": 0, "timeout_discards": 0,
            "encoding_errors": 0, "too_long_frames": 0,
            "too_short_frames": 0, "input_errors": 0, "output_errors": 0,
            "b2b_credits_remaining": 32, "b2b_credits_total": 32,
        },
    },
}

FLOGI_DATABASE = {
    "lva1-mds01": [
        {"interface": "fc1/1", "vsan": 100, "fcid": "0x610001",
         "port_wwn": "21:00:00:24:ff:4a:12:01", "node_wwn": "20:00:00:24:ff:4a:12:00",
         "device_alias": "stor-lva1-array05-ct0-fc0"},
        {"interface": "fc1/2", "vsan": 100, "fcid": "0x610002",
         "port_wwn": "21:00:00:24:ff:4a:12:02", "node_wwn": "20:00:00:24:ff:4a:12:00",
         "device_alias": "stor-lva1-array05-ct0-fc1"},
        {"interface": "fc1/4", "vsan": 100, "fcid": "0x610004",
         "port_wwn": "21:00:00:24:ff:4a:12:04", "node_wwn": "20:00:00:24:ff:4a:12:00",
         "device_alias": "stor-lva1-array05-ct1-fc1"},
        {"interface": "fc1/5", "vsan": 100, "fcid": "0x610005",
         "port_wwn": "50:00:09:72:08:60:2a:00", "node_wwn": "50:00:09:72:08:60:2a:ff",
         "device_alias": "esxi-lva1-host10-hba0"},
        {"interface": "fc1/6", "vsan": 100, "fcid": "0x610006",
         "port_wwn": "50:00:09:72:08:60:2a:01", "node_wwn": "50:00:09:72:08:60:2a:fe",
         "device_alias": "esxi-lva1-host11-hba0"},
        {"interface": "fc1/7", "vsan": 100, "fcid": "0x610007",
         "port_wwn": "50:00:09:72:08:60:2a:02", "node_wwn": "50:00:09:72:08:60:2a:fd",
         "device_alias": "esxi-lva1-host12-hba0"},
    ],
}

FCNS_DATABASE = {
    "lva1-mds01": [
        {"fcid": "0x610001", "port_wwn": "21:00:00:24:ff:4a:12:01",
         "node_wwn": "20:00:00:24:ff:4a:12:00", "type": "target",
         "fc4_type": "scsi-fcp", "device_alias": "stor-lva1-array05-ct0-fc0"},
        {"fcid": "0x610002", "port_wwn": "21:00:00:24:ff:4a:12:02",
         "node_wwn": "20:00:00:24:ff:4a:12:00", "type": "target",
         "fc4_type": "scsi-fcp", "device_alias": "stor-lva1-array05-ct0-fc1"},
        {"fcid": "0x610004", "port_wwn": "21:00:00:24:ff:4a:12:04",
         "node_wwn": "20:00:00:24:ff:4a:12:00", "type": "target",
         "fc4_type": "scsi-fcp", "device_alias": "stor-lva1-array05-ct1-fc1"},
        {"fcid": "0x610005", "port_wwn": "50:00:09:72:08:60:2a:00",
         "node_wwn": "50:00:09:72:08:60:2a:ff", "type": "initiator",
         "fc4_type": "scsi-fcp", "device_alias": "esxi-lva1-host10-hba0"},
        {"fcid": "0x610006", "port_wwn": "50:00:09:72:08:60:2a:01",
         "node_wwn": "50:00:09:72:08:60:2a:fe", "type": "initiator",
         "fc4_type": "scsi-fcp", "device_alias": "esxi-lva1-host11-hba0"},
        {"fcid": "0x610007", "port_wwn": "50:00:09:72:08:60:2a:02",
         "node_wwn": "50:00:09:72:08:60:2a:fd", "type": "initiator",
         "fc4_type": "scsi-fcp", "device_alias": "esxi-lva1-host12-hba0"},
    ],
}

FSPF_NEIGHBORS = {
    "lva1-mds01": [
        {"local_interface": "port-channel1", "neighbor_switch": "lva1-mds02",
         "neighbor_domain_id": 2, "neighbor_wwn": "20:00:00:0d:ec:6a:40:01",
         "state": "FULL", "cost": 500, "dead_interval": 80, "hello_interval": 20},
    ],
}

PORT_CHANNELS = {
    "lva1-mds01": [
        {
            "port_channel": "port-channel1",
            "admin_status": "up", "oper_status": "up",
            "mode": "TE", "speed": "64Gbps (aggregated)",
            "vsan_trunking": "1,100",
            "members": [
                {"interface": "fc1/47", "status": "up", "speed": "32Gbps"},
                {"interface": "fc1/48", "status": "up", "speed": "32Gbps"},
            ],
            "active_members": 2, "total_members": 2,
            "peer_switch": "lva1-mds02",
        },
    ],
}

VSAN_STATUS = {
    "lva1-mds01": [
        {"vsan_id": 1, "name": "default", "state": "active",
         "interop_mode": "default", "loadbalancing": "src-id/dst-id/oxid"},
        {"vsan_id": 100, "name": "prod-san-a", "state": "active",
         "interop_mode": "default", "loadbalancing": "src-id/dst-id/oxid",
         "member_ports": ["fc1/1", "fc1/2", "fc1/3", "fc1/4", "fc1/5", "fc1/6", "fc1/7",
                          "fc1/47 (TE)", "fc1/48 (TE)"],
         "active_zones": 4, "zone_set": "zs_prod_lva1"},
    ],
}

ZONE_STATUS = {
    "lva1-mds01": {
        100: {
            "active_zoneset": "zs_prod_lva1",
            "zones": [
                {
                    "name": "z_array05ct0_host10",
                    "members": [
                        {"pwwn": "21:00:00:24:ff:4a:12:01", "alias": "stor-lva1-array05-ct0-fc0",
                         "logged_in": True, "fcid": "0x610001"},
                        {"pwwn": "50:00:09:72:08:60:2a:00", "alias": "esxi-lva1-host10-hba0",
                         "logged_in": True, "fcid": "0x610005"},
                    ],
                },
                {
                    "name": "z_array05ct0_host11",
                    "members": [
                        {"pwwn": "21:00:00:24:ff:4a:12:02", "alias": "stor-lva1-array05-ct0-fc1",
                         "logged_in": True, "fcid": "0x610002"},
                        {"pwwn": "50:00:09:72:08:60:2a:01", "alias": "esxi-lva1-host11-hba0",
                         "logged_in": True, "fcid": "0x610006"},
                    ],
                },
                {
                    "name": "z_array05ct1_host12",
                    "members": [
                        {"pwwn": "21:00:00:24:ff:4a:12:03", "alias": "stor-lva1-array05-ct1-fc0",
                         "logged_in": False, "fcid": "N/A"},
                        {"pwwn": "50:00:09:72:08:60:2a:02", "alias": "esxi-lva1-host12-hba0",
                         "logged_in": True, "fcid": "0x610007"},
                    ],
                },
                {
                    "name": "z_array05ct1_host10",
                    "members": [
                        {"pwwn": "21:00:00:24:ff:4a:12:04", "alias": "stor-lva1-array05-ct1-fc1",
                         "logged_in": True, "fcid": "0x610004"},
                        {"pwwn": "50:00:09:72:08:60:2a:00", "alias": "esxi-lva1-host10-hba0",
                         "logged_in": True, "fcid": "0x610005"},
                    ],
                },
            ],
            "total_zones": 4,
            "zones_with_all_members_online": 3,
            "zones_with_offline_members": 1,
            "alerts": [
                "z_array05ct1_host12: member 21:00:00:24:ff:4a:12:03 NOT logged in — "
                "esxi-lva1-host12 has lost one storage path"
            ],
        },
    },
}

DEVICE_HEALTH = {
    "lva1-mds01": {
        "hostname": "lva1-mds01",
        "model": "Cisco MDS 9710",
        "serial": "FDO24350ABC",
        "firmware": "9.4(2a)",
        "uptime_days": 182,
        "cpu_1min": 35.2, "cpu_5min": 28.4,
        "memory_total_mb": 32768, "memory_used_mb": 20316, "memory_used_percent": 62.0,
        "power_supplies": [
            {"id": "PS1", "status": "ok", "watts": 3000, "input": "AC"},
            {"id": "PS2", "status": "ok", "watts": 3000, "input": "AC"},
            {"id": "PS3", "status": "ok", "watts": 3000, "input": "AC"},
            {"id": "PS4", "status": "ok", "watts": 3000, "input": "AC"},
        ],
        "fan_trays": [
            {"id": "Fan1", "status": "ok", "speed_rpm": 4200},
            {"id": "Fan2", "status": "ok", "speed_rpm": 4150},
            {"id": "Fan3", "status": "ok", "speed_rpm": 4180},
        ],
        "temperature": {"inlet": 28.5, "sup1": 42.0, "sup2": 41.5, "module1": 48.2},
    },
}

MODULE_STATUS = {
    "lva1-mds01": [
        {"slot": 1, "type": "Supervisor", "model": "DS-X97-SF4-K9",
         "status": "active", "hw_ver": "1.0", "fw_ver": "9.4(2a)"},
        {"slot": 2, "type": "Supervisor", "model": "DS-X97-SF4-K9",
         "status": "ha-standby", "hw_ver": "1.0", "fw_ver": "9.4(2a)"},
        {"slot": 3, "type": "48-port 32Gbps FC", "model": "DS-X9748-3072K9",
         "status": "ok", "hw_ver": "1.1", "fw_ver": "9.4(2a)",
         "ports_up": 7, "ports_down": 1, "ports_total": 48},
        {"slot": 5, "type": "48-port 32Gbps FC", "model": "DS-X9748-3072K9",
         "status": "ok", "hw_ver": "1.1", "fw_ver": "9.4(2a)",
         "ports_up": 24, "ports_down": 0, "ports_total": 48},
    ],
}


# ═══════════════════════════════════════════════════════════════════
# TOOL DEFINITIONS
# ═══════════════════════════════════════════════════════════════════

@tool
def get_interface_status(hostname: str) -> dict:
    """Get all interface status for an MDS switch — port mode, speed, VSAN, connected device.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
    """
    interfaces = SWITCH_INTERFACES.get(hostname, [])
    if not interfaces:
        return {"error": f"No data for hostname '{hostname}'", "available": list(SWITCH_INTERFACES.keys())}

    ports_up = sum(1 for i in interfaces if i["oper_status"] == "up")
    ports_down = sum(1 for i in interfaces if i["oper_status"] == "down")

    alerts = []
    for iface in interfaces:
        if iface["oper_status"] == "down" and iface["admin_status"] == "up":
            alerts.append(
                f"{iface['interface']}: DOWN — {iface.get('down_reason', 'unknown')} — "
                f"connected to {iface.get('connected_device', 'unknown')}"
            )

    return {
        "hostname": hostname, "model": "Cisco MDS 9710",
        "firmware": DEVICE_HEALTH.get(hostname, {}).get("firmware", "unknown"),
        "interfaces": interfaces,
        "summary": {"total": len(interfaces), "up": ports_up, "down": ports_down},
        "alerts": alerts,
    }


@tool
def get_interface_detail(hostname: str, interface: str) -> dict:
    """Get detailed status for a SINGLE interface.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        interface: Interface name (e.g. fc1/3)
    """
    interfaces = SWITCH_INTERFACES.get(hostname, [])
    for iface in interfaces:
        if iface["interface"] == interface:
            return {"hostname": hostname, "interface": iface}
    return {"error": f"Interface '{interface}' not found on '{hostname}'"}


@tool
def get_interface_counters(hostname: str, interface: str) -> dict:
    """Get error counters for a specific interface — CRC, link failures, signal loss, credits.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        interface: Interface name (e.g. fc1/3)
    """
    host_counters = INTERFACE_COUNTERS.get(hostname, {})
    counters = host_counters.get(interface)
    if not counters:
        return {"error": f"No counter data for '{interface}' on '{hostname}'"}

    severity = "OK"
    findings = []
    if counters["crc_errors"] > 100:
        severity = "CRITICAL"
        findings.append(f"CRC errors: {counters['crc_errors']} — likely bad SFP or fiber")
    elif counters["crc_errors"] > 0:
        severity = "DEGRADED"
        findings.append(f"CRC errors: {counters['crc_errors']} — monitor trend")
    if counters["signal_losses"] > 0:
        severity = "CRITICAL"
        findings.append(f"Signal losses: {counters['signal_losses']} — fiber break or SFP failure")
    if counters["link_failures"] > 5:
        severity = "CRITICAL"
        findings.append(f"Link failures: {counters['link_failures']} — sustained flapping")
    elif counters["link_failures"] > 0:
        findings.append(f"Link failures: {counters['link_failures']}")
    if counters["credit_loss"] > 0:
        findings.append(f"Credit loss: {counters['credit_loss']} — possible slow-drain")
    if counters["timeout_discards"] > 0:
        findings.append(f"Timeout discards: {counters['timeout_discards']} — active slow-drain")

    return {"hostname": hostname, "interface": interface, "counters": counters,
            "severity": severity, "findings": findings}


@tool
def get_flogi_database(hostname: str) -> dict:
    """Get Fabric Login (FLOGI) database — shows which devices are logged into the fabric.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
    """
    entries = FLOGI_DATABASE.get(hostname, [])
    if not entries:
        return {"error": f"No FLOGI data for '{hostname}'"}
    return {"hostname": hostname, "flogi_count": len(entries), "entries": entries,
            "note": "Devices NOT in this list are NOT logged into the fabric"}


@tool
def get_fcns_database(hostname: str) -> dict:
    """Get FC Name Server (FCNS) database — registered devices in fabric name service.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
    """
    entries = FCNS_DATABASE.get(hostname, [])
    if not entries:
        return {"error": f"No FCNS data for '{hostname}'"}
    initiators = sum(1 for e in entries if e["type"] == "initiator")
    targets = sum(1 for e in entries if e["type"] == "target")
    return {"hostname": hostname, "fcns_count": len(entries),
            "initiators": initiators, "targets": targets, "entries": entries}


@tool
def get_fspf_neighbors(hostname: str) -> dict:
    """Get FSPF neighbors — fabric routing adjacency. Neighbors should be in FULL state.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
    """
    neighbors = FSPF_NEIGHBORS.get(hostname, [])
    if not neighbors:
        return {"error": f"No FSPF data for '{hostname}'"}
    alerts = [f"Neighbor {n['neighbor_switch']} in state {n['state']} — NOT FULL"
              for n in neighbors if n["state"] != "FULL"]
    return {"hostname": hostname, "neighbor_count": len(neighbors), "neighbors": neighbors,
            "all_full": all(n["state"] == "FULL" for n in neighbors), "alerts": alerts}


@tool
def get_port_channel_summary(hostname: str) -> dict:
    """Get port-channel (ISL bundle) summary — shows ISL redundancy.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
    """
    pcs = PORT_CHANNELS.get(hostname, [])
    if not pcs:
        return {"error": f"No port-channel data for '{hostname}'"}
    alerts = []
    for pc in pcs:
        if pc["active_members"] < pc["total_members"]:
            alerts.append(f"{pc['port_channel']}: {pc['active_members']}/{pc['total_members']} members active")
        if pc["active_members"] == 1:
            alerts.append(f"{pc['port_channel']}: CRITICAL — single member, next failure = fabric partition")
    return {"hostname": hostname, "port_channels": pcs, "alerts": alerts}


@tool
def get_vsan_status(hostname: str) -> dict:
    """Get VSAN status — virtual SAN state, member ports, active zoneset.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
    """
    vsans = VSAN_STATUS.get(hostname, [])
    if not vsans:
        return {"error": f"No VSAN data for '{hostname}'"}
    alerts = [f"VSAN {v['vsan_id']} ({v['name']}): {v['state']} — CRITICAL"
              for v in vsans if v["state"] != "active"]
    return {"hostname": hostname, "vsans": vsans, "alerts": alerts}


@tool
def get_zone_status(hostname: str, vsan: int = 100) -> dict:
    """Get zone database status for a VSAN — active zoneset, zone members, login status.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        vsan: VSAN ID to check (default 100)
    """
    host_zones = ZONE_STATUS.get(hostname, {})
    zone_data = host_zones.get(vsan)
    if not zone_data:
        return {"error": f"No zone data for VSAN {vsan} on '{hostname}'"}
    return {"hostname": hostname, "vsan": vsan, **zone_data}


@tool
def get_device_health(hostname: str) -> dict:
    """Get MDS switch health — CPU, memory, power supplies, fans, temperature.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
    """
    health = DEVICE_HEALTH.get(hostname)
    if not health:
        return {"error": f"No health data for '{hostname}'"}

    verdict = "OK"
    findings = []
    if health["cpu_1min"] > 85:
        verdict = "CRITICAL"
        findings.append(f"CPU 1-min avg: {health['cpu_1min']}% — very high")
    elif health["cpu_1min"] > 60:
        verdict = "DEGRADED"
        findings.append(f"CPU 1-min avg: {health['cpu_1min']}% — elevated")
    if health["memory_used_percent"] > 90:
        verdict = "CRITICAL"
        findings.append(f"Memory: {health['memory_used_percent']}% — critical")
    elif health["memory_used_percent"] > 75:
        if verdict != "CRITICAL":
            verdict = "DEGRADED"
        findings.append(f"Memory: {health['memory_used_percent']}% — elevated")
    for ps in health["power_supplies"]:
        if ps["status"] != "ok":
            findings.append(f"PSU {ps['id']}: {ps['status']}")
    for fan in health["fan_trays"]:
        if fan["status"] != "ok":
            findings.append(f"Fan {fan['id']}: {fan['status']}")
    for location, temp in health["temperature"].items():
        if temp > 55:
            verdict = "CRITICAL"
            findings.append(f"Temperature {location}: {temp}C — CRITICAL")
        elif temp > 45:
            if verdict != "CRITICAL":
                verdict = "DEGRADED"
            findings.append(f"Temperature {location}: {temp}C — elevated")
    if not findings:
        findings.append("All subsystems healthy")
    return {**health, "verdict": verdict, "findings": findings}


@tool
def get_module_status(hostname: str) -> dict:
    """Get linecard and supervisor module status.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
    """
    modules = MODULE_STATUS.get(hostname, [])
    if not modules:
        return {"error": f"No module data for '{hostname}'"}
    alerts = []
    for m in modules:
        if m["status"] in ("failed", "err-disabled"):
            alerts.append(f"Slot {m['slot']} ({m['type']}): {m['status']} — CRITICAL")
        elif m["status"] == "powered-down":
            alerts.append(f"Slot {m['slot']} ({m['type']}): powered-down")
    return {"hostname": hostname, "modules": modules, "alerts": alerts}

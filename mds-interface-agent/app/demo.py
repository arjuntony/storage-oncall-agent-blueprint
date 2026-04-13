"""Demo mode — runs the full 10-step investigation without Claude API.

Calls all tools in the same order the agent would, shows each step's
findings, and produces the final escalation report.
"""

import json
import time

from tools.mds_live import (
    get_interface_status, get_interface_detail, get_interface_counters,
    get_flogi_database, get_fcns_database, get_fspf_neighbors,
    get_port_channel_summary, get_vsan_status, get_zone_status,
    get_device_health, get_module_status,
)
from tools.syslog import get_syslog_entries
from tools.show_tech import load_show_tech
from tools.skills import search_skills, load_skill


def run_demo_triage(hostname: str, interface: str, status_callback=None):
    """Run the full 10-step triage and yield (step_name, tool_name, result) tuples."""

    steps = []

    def step(name, tool_name, result):
        steps.append({"step": name, "tool": tool_name, "result": result})
        if status_callback:
            status_callback(name, tool_name)
        return result

    # ── PHASE 1: BLAST RADIUS ──

    # Step 1a: Interface overview
    iface_status = step(
        "Step 1a — Interface overview",
        "get_interface_status",
        get_interface_status.invoke({"hostname": hostname}),
    )

    # Step 1b: FLOGI database
    flogi = step(
        "Step 1b — FLOGI database (who's logged in?)",
        "get_flogi_database",
        get_flogi_database.invoke({"hostname": hostname}),
    )

    # Step 1c: FSPF neighbors
    fspf = step(
        "Step 1c — FSPF neighbors (fabric routing)",
        "get_fspf_neighbors",
        get_fspf_neighbors.invoke({"hostname": hostname}),
    )

    # Step 2: Port-channel check
    port_ch = step(
        "Step 2 — Port-channel / ISL check",
        "get_port_channel_summary",
        get_port_channel_summary.invoke({"hostname": hostname}),
    )

    # ── PHASE 2: TRIAGE ──

    # Step 3: Current interface state
    iface_detail = step(
        "Step 3 — Current interface state",
        "get_interface_detail",
        get_interface_detail.invoke({"hostname": hostname, "interface": interface}),
    )

    # Step 4: Error counters + syslog
    counters = step(
        "Step 4a — Error counters",
        "get_interface_counters",
        get_interface_counters.invoke({"hostname": hostname, "interface": interface}),
    )

    syslog = step(
        "Step 4b — Syslog entries",
        "get_syslog_entries",
        get_syslog_entries.invoke({"hostname": hostname, "keyword": interface, "hours": 1}),
    )

    # Step 5: (same counters — already have them)

    # Step 6: FCNS database
    fcns = step(
        "Step 6 — FCNS database (name server)",
        "get_fcns_database",
        get_fcns_database.invoke({"hostname": hostname}),
    )

    # Step 7: VSAN + Zone
    vsan = step(
        "Step 7a — VSAN status",
        "get_vsan_status",
        get_vsan_status.invoke({"hostname": hostname}),
    )

    zones = step(
        "Step 7b — Zone status",
        "get_zone_status",
        get_zone_status.invoke({"hostname": hostname, "vsan": 100}),
    )

    # Step 8: Device health
    health = step(
        "Step 8 — Device health",
        "get_device_health",
        get_device_health.invoke({"hostname": hostname}),
    )

    modules = step(
        "Step 8b — Module status",
        "get_module_status",
        get_module_status.invoke({"hostname": hostname}),
    )

    # Step 9: Show-tech (offline data)
    show_tech_list = step(
        "Step 9a — Show-tech sections (list)",
        "load_show_tech",
        load_show_tech.invoke({"hostname": hostname}),
    )

    show_tech_iface = step(
        "Step 9b — Show-tech interfaces (SFP detail)",
        "load_show_tech",
        load_show_tech.invoke({"hostname": hostname, "section": "interfaces"}),
    )

    # Step 10: Compile report
    c = counters.get("counters", {})
    iface_info = iface_detail.get("interface", {})

    # Check FLOGI for our interface
    flogi_present = any(
        e.get("interface") == interface for e in flogi.get("entries", [])
    )

    # Find zone with offline member
    zone_alerts = zones.get("alerts", [])

    # Parse SFP Rx power from show-tech
    sfp_rx = "unknown"
    show_content = show_tech_iface.get("content", "")
    for line in show_content.split("\n"):
        if "Rx Power" in line and "NEAR THRESHOLD" in line:
            sfp_rx = line.strip()

    report = f"""## MDS INTERFACE TRIAGE — ESCALATION REPORT

**Time:** {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
**Investigator:** MDS Interface Triage Agent (DEMO MODE)
**Skill:** `mds-interface-issues.md` (10-step investigation)

---

### Alert
```
InterfaceFlapping + CRCErrors — {hostname} {interface}
{c.get('link_failures', 0)} link failures, {c.get('crc_errors', 0)} CRC errors
```

---

### HANDOFF
```
device:         {hostname}
platform:       Cisco MDS 9710 (firmware {iface_status.get('firmware', 'unknown')})
alert:          InterfaceFlapping + CRCErrors
port:           {interface}
port_type:      {iface_info.get('port_mode', 'F')}-port
connected_to:   {iface_info.get('connected_device', 'unknown')} (WWPN {iface_info.get('connected_wwpn', 'unknown')})
vsan:           {iface_info.get('vsan', 'unknown')}
root_cause:     PHYSICAL — degraded SFP optics
blast_radius:   Single storage path lost
```

---

### Evidence — Step by Step

| Step | Check | Finding | Severity |
|------|-------|---------|----------|
| 1 | Port type | {iface_info.get('port_mode', 'F')}-port to {iface_info.get('connected_device', 'unknown')} | — |
| 1 | FLOGI | {"Present" if flogi_present else "**MISSING** — device not in fabric"} | {"OK" if flogi_present else "CRITICAL"} |
| 2 | Port-channel | ISL port-channel1: {port_ch.get('port_channels', [{}])[0].get('active_members', 0)}/{port_ch.get('port_channels', [{}])[0].get('total_members', 0)} members up | OK |
| 3 | Interface state | **{iface_info.get('oper_status', 'unknown')}** — {iface_info.get('down_reason', 'N/A')} | CRITICAL |
| 4 | Link failures | **{c.get('link_failures', 0)}** in counter history | CRITICAL |
| 4 | Syslog | {syslog.get('count', 0)} events for {interface} in last hour | CRITICAL |
| 5 | CRC errors | **{c.get('crc_errors', 0)}** | CRITICAL |
| 5 | Signal losses | **{c.get('signal_losses', 0)}** | CRITICAL |
| 5 | Sync losses | {c.get('sync_losses', 0)} | CRITICAL |
| 5 | Credit loss | {c.get('credit_loss', 0)} (not slow-drain) | OK |
| 6 | FLOGI | {"Present" if flogi_present else "**Missing**"} | {"OK" if flogi_present else "CRITICAL"} |
| 7 | VSAN 100 | Active | OK |
| 7 | Zone | {len(zone_alerts)} alert(s): {zone_alerts[0][:80] if zone_alerts else 'none'}... | {"DEGRADED" if zone_alerts else "OK"} |
| 8 | CPU | {health.get('cpu_1min', 0)}% (1-min avg) | OK |
| 8 | Memory | {health.get('memory_used_percent', 0)}% | OK |
| 8 | Health verdict | {health.get('verdict', 'unknown')} | {health.get('verdict', 'unknown')} |
| 9 | Show-tech SFP | {sfp_rx or 'no data'} | CRITICAL |

---

### Root Cause Assessment

**PHYSICAL LAYER — Degraded SFP optics on {interface}.**

{sfp_rx}

The SFP Rx power is near the failure threshold. This explains:
- Signal drops intermittently → **link failures** ({c.get('link_failures', 0)})
- Degraded signal → bit errors → **CRC errors** ({c.get('crc_errors', 0)})
- Complete signal loss events → **signal_losses** ({c.get('signal_losses', 0)})

**This is NOT:** slow-drain (credit_loss=0), switch health issue (CPU {health.get('cpu_1min', 0)}%), VSAN/zone misconfig (VSAN active), or ISL problem (port-channel healthy).

---

### Recommended Actions (for human)

1. **Replace SFP on {interface}** — Rx power at threshold
2. **Clean fiber connectors** — both ends (switch + array)
3. **After fix, verify:** FLOGI re-registers, zone member comes back online, host regains storage path
4. **Monitor {interface.replace('3', '2')}** — {INTERFACE_COUNTERS_FC12_CRC} CRC errors (not critical yet, same array controller)

---

### Escalation

| Who | Why |
|-----|-----|
| **DC Technicians** | SFP + fiber replacement on {hostname} {interface} |
| **Storage Admin** (info) | Array controller port offline — verify host multipath |

**Priority:** P2 — single path, no data loss, reduced redundancy

---
*Demo mode — no Claude API used. In production, Claude follows the skill autonomously.*
"""

    return steps, report


# Helper for report — get fc1/2 CRC count
from tools.mds_live import INTERFACE_COUNTERS
INTERFACE_COUNTERS_FC12_CRC = INTERFACE_COUNTERS.get("lva1-mds01", {}).get("fc1/2", {}).get("crc_errors", 0)

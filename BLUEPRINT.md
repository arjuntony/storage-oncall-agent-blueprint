# Storage Oncall Agent — Complete Build Blueprint

> **What this is:** A complete specification for building an AI-powered storage oncall triage agent from scratch. Hand this entire document to Claude (or any AI coding assistant) and say: **"Build this."**
>
> **What you need:** Python 3.11+, an Anthropic API key (`sk-ant-...`), and a terminal.
>
> **What you get:** A working chat agent that triages storage incidents — MDS switches, storage arrays, ESXi VMs, RV tool — using Claude as the brain and your custom tools as the hands.

---

## Table of Contents

1. [How It Works — The Core Concept](#1-how-it-works)
2. [Architecture Overview](#2-architecture-overview)
3. [Project Structure](#3-project-structure)
4. [Dependencies](#4-dependencies)
5. [Step-by-Step Build Instructions](#5-build-instructions)
6. [Complete Code for Every File](#6-complete-code)
7. [Runbooks](#7-runbooks)
8. [Running the Application](#8-running)
9. [Testing](#9-testing)
10. [Graduating to Real APIs](#10-graduating)

---

## 1. How It Works — The Core Concept <a name="1-how-it-works"></a>

### The Analogy

In **Claude Code**, you type something → Claude reads your code → responds.

In this **Storage Agent**, you type something → Claude reads your message → **calls your tools** (Python functions that query MDS switches, storage arrays, VMs) → reads the results → **calls more tools** → finally gives you a structured triage report.

### The Key Insight

**Claude never touches your infrastructure directly.** Your Python functions do. Claude just decides:
1. Which tool to call
2. What parameters to pass
3. What to do with the results

This is called a **ReAct loop** (Reason + Act):

```
User: "triage MDS switch lva1-mds01 — ports flapping"

Claude thinks: "I need port status" → calls mds_port_status("lva1-mds01")
  Your code runs → returns: {ports: [...], fc1/3: DOWN, 47 flaps, 892 CRC errors}

Claude thinks: "CRC errors — let me check the runbook" → calls search_runbooks("MDS port flap")
  Your code runs → returns: mds-port-flap.md found

Claude thinks: "Need the full runbook" → calls load_runbook("mds-port-flap.md")
  Your code runs → returns: full runbook text

Claude thinks: "Need blast radius" → calls esxi_vm_status("esxi-lva1-host10")
  Your code runs → returns: {47 VMs affected, latency spike}

Claude thinks: "I have everything now" → returns final triage report
  No more tool calls → streams answer to user
```

Each "Claude thinks" is a separate API call to `https://api.anthropic.com/v1/messages`. The LangGraph framework manages the loop automatically.

### What Each API Call Looks Like

```json
POST https://api.anthropic.com/v1/messages
{
  "model": "claude-sonnet-4-5-20250929",
  "system": "You are a storage oncall assistant...",
  "messages": [
    {"role": "user", "content": "triage lva1-mds01"},
    {"role": "assistant", "content": [
      {"type": "tool_use", "name": "mds_port_status", "input": {"hostname": "lva1-mds01"}}
    ]},
    {"role": "user", "content": [
      {"type": "tool_result", "content": "{\"ports\": [...], \"alerts\": [...]}"}
    ]}
  ],
  "tools": [
    {"name": "mds_port_status", "description": "Get MDS switch port status...", "input_schema": {...}},
    {"name": "search_runbooks", "description": "Search storage runbooks...", "input_schema": {...}}
  ]
}
```

Claude sees the tool definitions and previous tool results, then decides what to do next.

---

## 2. Architecture Overview <a name="2-architecture-overview"></a>

```
┌────────────────────────────────────────────────────────────┐
│                     YOUR MACHINE                            │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ FRONTEND — Streamlit Chat UI (:8501)                 │  │
│  │  • Chat input box                                    │  │
│  │  • Streaming response display                        │  │
│  │  • Shows which tools Claude is calling               │  │
│  │  • Conversation history                              │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │ calls                             │
│  ┌──────────────────────▼───────────────────────────────┐  │
│  │ AGENT ENGINE — LangGraph ReAct Loop                  │  │
│  │                                                      │  │
│  │  ┌─────────┐          ┌────────────┐                 │  │
│  │  │ CLAUDE  │──tools?──│ EXECUTE    │                 │  │
│  │  │  (API)  │   YES    │ TOOL       │                 │  │
│  │  │         │◀─results─│ (Python fn)│                 │  │
│  │  └────┬────┘          └────────────┘                 │  │
│  │       │ NO tools = final answer                      │  │
│  │       ▼                                              │  │
│  │  Stream to user                                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                         │                                   │
│         ┌───────────────┼───────────────┐                  │
│         ▼               ▼               ▼                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ TOOLS      │  │ RUNBOOKS   │  │ DATABASE   │           │
│  │ (Python)   │  │ (Markdown) │  │ (SQLite)   │           │
│  │            │  │            │  │            │           │
│  │ Synthetic  │  │ mds-port-  │  │ chat       │           │
│  │ data for   │  │ flap.md    │  │ history    │           │
│  │ POC        │  │ disk-      │  │            │           │
│  │            │  │ failure.md │  │            │           │
│  │ Real APIs  │  │ esxi-      │  │            │           │
│  │ later      │  │ hang.md    │  │            │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│                                                             │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTPS (outbound only)
                             ▼
                  ┌──────────────────────┐
                  │   api.anthropic.com  │
                  │   (Claude API)       │
                  │                      │
                  │   ONLY external      │
                  │   dependency         │
                  └──────────────────────┘
```

---

## 3. Project Structure <a name="3-project-structure"></a>

```
storage-oncall-agent/
│
├── .env                           # ANTHROPIC_API_KEY=sk-ant-...
├── pyproject.toml                 # Python dependencies
├── README.md                      # How to run
│
├── app/
│   ├── __init__.py
│   ├── main.py                    # Streamlit chat app (frontend + agent in one)
│   ├── agent.py                   # LangGraph ReAct agent setup
│   └── config.py                  # Settings (model, API key)
│
├── tools/
│   ├── __init__.py                # Exports all tools as a list
│   ├── incidents.py               # get_storage_incidents
│   ├── mds.py                     # mds_port_status, mds_zoneset
│   ├── esxi.py                    # esxi_vm_status, datastore_health
│   ├── storage_array.py           # array_health, disk_failures
│   ├── backup.py                  # get_backup_status
│   ├── rv_tool.py                 # rv_tool_check
│   ├── fabric.py                  # fabric_topology
│   └── runbooks.py                # search_runbooks, load_runbook (loads skills)
│
├── runbooks/                      # Skills — investigation procedures (markdown)
│   ├── mds-port-flap.md           # Skill: MDS port flap investigation
│   ├── disk-failure.md            # Skill: Disk failure investigation
│   ├── esxi-vm-hang.md            # Skill: ESXi VM hang investigation
│   ├── datastore-full.md          # Skill: Datastore capacity investigation
│   ├── rv-tool-errors.md          # Skill: RV tool failure investigation
│   └── backup-failure.md          # Skill: Backup failure investigation + escalation
│
└── tests/
    ├── __init__.py
    ├── test_tools.py              # Unit tests for tools
    └── test_agent.py              # Integration test for agent
```

---

## 4. Dependencies <a name="4-dependencies"></a>

### pyproject.toml

```toml
[project]
name = "storage-oncall-agent"
version = "0.1.0"
description = "AI-powered storage oncall triage agent"
requires-python = ">=3.11"
dependencies = [
    "langchain-anthropic>=0.3.0",
    "langgraph>=0.3.0",
    "langchain-core>=0.3.0",
    "streamlit>=1.40.0",
    "python-dotenv>=1.0.0",
    "anthropic>=0.40.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24.0",
]
```

### .env

```bash
ANTHROPIC_API_KEY=sk-ant-api03-YOUR_KEY_HERE
# Optional: override default model
# MODEL_NAME=claude-sonnet-4-5-20250929
```

---

## 5. Step-by-Step Build Instructions <a name="5-build-instructions"></a>

### For Claude (the AI building this):

1. Create the project directory and all subdirectories
2. Write `pyproject.toml` and `.env` (with placeholder API key)
3. Write all tool files in `tools/` — each tool is a Python function decorated with `@tool`
4. Write all runbook markdown files in `runbooks/`
5. Write `app/config.py` — loads .env, provides settings
6. Write `app/agent.py` — creates the LangGraph ReAct agent with all tools
7. Write `app/main.py` — Streamlit chat interface that calls the agent
8. Write tests in `tests/`
9. Verify: `pip install -e .` then `streamlit run app/main.py`

### For the human:

```bash
# 1. Create project
mkdir storage-oncall-agent && cd storage-oncall-agent

# 2. Have Claude build everything (give it this document)

# 3. Set up
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 4. Add your API key
echo "ANTHROPIC_API_KEY=sk-ant-api03-YOUR_KEY" > .env

# 5. Run
streamlit run app/main.py

# 6. Open browser: http://localhost:8501
```

---

## 6. Complete Code for Every File <a name="6-complete-code"></a>

### `app/config.py`

```python
"""Application configuration — loads from .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "claude-sonnet-4-5-20250929")
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "25"))

if not ANTHROPIC_API_KEY:
    raise ValueError(
        "ANTHROPIC_API_KEY not set. Create a .env file with: ANTHROPIC_API_KEY=sk-ant-..."
    )
```

### `tools/__init__.py`

```python
"""Export all tools as a single list for the agent."""

from tools.incidents import get_storage_incidents
from tools.mds import mds_port_status, mds_zoneset
from tools.esxi import esxi_vm_status, datastore_health
from tools.storage_array import array_health, disk_failures
from tools.rv_tool import rv_tool_check
from tools.fabric import fabric_topology
from tools.runbooks import search_runbooks, load_runbook
from tools.backup import get_backup_status

ALL_TOOLS = [
    # Always call first during triage
    get_storage_incidents,
    # MDS Fibre Channel switches
    mds_port_status,
    mds_zoneset,
    # ESXi / VMware
    esxi_vm_status,
    datastore_health,
    # Storage arrays
    array_health,
    disk_failures,
    # Backup
    get_backup_status,
    # RV Tool
    rv_tool_check,
    # FC Fabric
    fabric_topology,
    # Runbooks
    search_runbooks,
    load_runbook,
]
```

### `tools/incidents.py`

```python
"""Storage incident tools — synthetic data for POC."""

from langchain_core.tools import tool


# ── Synthetic incident data (replace with real API later) ──────────

SYNTHETIC_INCIDENTS = [
    {
        "incident_id": "STOR-2001",
        "severity": "SEV2",
        "title": "Storage array stor-lva1-array05 degraded -- 2 disk failures",
        "status": "active",
        "created": "2026-04-12T06:30:00Z",
        "alerts": [
            {"type": "DiskFailure", "device": "stor-lva1-array05", "detail": "disk-2-14 SMART FAILING"},
            {"type": "RaidDegraded", "device": "stor-lva1-array05", "detail": "RG02 lost redundancy"},
            {"type": "LatencySpike", "device": "stor-lva1-array05", "detail": "Write latency 45ms (baseline 12ms)"},
        ],
        "affected_hosts": ["esxi-lva1-host10", "esxi-lva1-host11", "esxi-lva1-host12"],
        "affected_vms": 47,
        "oncall": "storage-infra-oncall",
    },
    {
        "incident_id": "STOR-2002",
        "severity": "SEV3",
        "title": "MDS switch lva1-mds01 port fc1/3 flapping",
        "status": "active",
        "created": "2026-04-12T08:15:00Z",
        "alerts": [
            {"type": "PortFlap", "device": "lva1-mds01", "detail": "fc1/3 -- 47 flaps in 24h"},
            {"type": "CRCErrors", "device": "lva1-mds01", "detail": "fc1/3 -- 892 CRC errors"},
        ],
        "affected_hosts": ["stor-lva1-array05"],
        "affected_vms": 12,
        "oncall": "storage-infra-oncall",
    },
    {
        "incident_id": "STOR-2003",
        "severity": "SEV3",
        "title": "ESXi host esxi-lva1-host10 datastore latency elevated",
        "status": "active",
        "created": "2026-04-12T09:00:00Z",
        "alerts": [
            {"type": "LatencyHigh", "device": "esxi-lva1-host10", "detail": "ds-lva1-stor05 write latency 45ms"},
            {"type": "MemoryHigh", "device": "esxi-lva1-host10", "detail": "92% memory usage"},
        ],
        "affected_hosts": ["esxi-lva1-host10"],
        "affected_vms": 23,
        "oncall": "storage-infra-oncall",
    },
    {
        "incident_id": "STOR-1998",
        "severity": "SEV2",
        "title": "FC Fabric fab-ltx1-b ISL link down -- single path",
        "status": "resolved",
        "created": "2026-04-11T14:00:00Z",
        "resolved": "2026-04-11T16:30:00Z",
        "alerts": [
            {"type": "ISLDown", "device": "ltx1-mds02", "detail": "fc1/48 ISL to ltx1-mds01 down"},
        ],
        "affected_hosts": [],
        "affected_vms": 0,
        "oncall": "storage-infra-oncall",
    },
]


@tool
def get_storage_incidents(
    severity: str = "ALL",
    status: str = "active",
) -> dict:
    """Get current storage incidents. ALWAYS call this FIRST when triaging.

    Args:
        severity: Filter by severity — SEV1, SEV2, SEV3, or ALL (default ALL)
        status: Filter by status — active, resolved, or ALL (default active)

    Returns:
        Dictionary with incidents list and count.
    """
    results = SYNTHETIC_INCIDENTS
    if severity != "ALL":
        results = [i for i in results if i["severity"] == severity]
    if status != "ALL":
        results = [i for i in results if i["status"] == status]
    return {"incidents": results, "count": len(results)}
```

### `tools/mds.py`

```python
"""MDS Fibre Channel switch tools — synthetic data for POC."""

from langchain_core.tools import tool


@tool
def mds_port_status(hostname: str, interface: str = "") -> dict:
    """Get MDS switch port status including flap count, speed, and CRC errors.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        interface: Optional specific interface (e.g. fc1/1). Omit for all ports.

    Returns:
        Port status with flap counts, CRC errors, speeds, and alerts.
    """
    all_ports = [
        {"interface": "fc1/1", "status": "up", "speed": "32Gbps", "vsan": 100,
         "flap_count": 0, "crc_errors": 0, "connected_device": "stor-lva1-array05-hba1",
         "connected_wwn": "21:00:00:24:ff:4a:12:01"},
        {"interface": "fc1/2", "status": "up", "speed": "32Gbps", "vsan": 100,
         "flap_count": 3, "crc_errors": 12, "connected_device": "stor-lva1-array05-hba2",
         "connected_wwn": "21:00:00:24:ff:4a:12:02"},
        {"interface": "fc1/3", "status": "down", "speed": "N/A", "vsan": 100,
         "flap_count": 47, "crc_errors": 892, "connected_device": "stor-lva1-array05-hba3",
         "connected_wwn": "21:00:00:24:ff:4a:12:03",
         "last_flap": "2026-04-12T08:15:00Z", "down_reason": "link_failure"},
        {"interface": "fc1/4", "status": "up", "speed": "32Gbps", "vsan": 100,
         "flap_count": 0, "crc_errors": 0, "connected_device": "esxi-lva1-host10-hba1",
         "connected_wwn": "50:00:09:72:08:60:2a:00"},
        {"interface": "fc1/47", "status": "up", "speed": "32Gbps", "vsan": 100,
         "flap_count": 0, "crc_errors": 0, "connected_device": "lva1-mds02 (ISL)",
         "port_type": "ISL"},
        {"interface": "fc1/48", "status": "up", "speed": "32Gbps", "vsan": 100,
         "flap_count": 0, "crc_errors": 0, "connected_device": "lva1-mds02 (ISL)",
         "port_type": "ISL"},
    ]

    if interface:
        all_ports = [p for p in all_ports if p["interface"] == interface]

    alerts = []
    for p in all_ports:
        if p["flap_count"] > 5:
            alerts.append(f"{p['interface']}: {p['flap_count']} flaps in last 24h (threshold: 5)")
        if p["crc_errors"] > 10:
            alerts.append(f"{p['interface']}: {p['crc_errors']} CRC errors (trending up)")
        if p["status"] == "down":
            alerts.append(f"{p['interface']}: PORT DOWN — {p.get('down_reason', 'unknown')}")

    return {
        "hostname": hostname,
        "model": "Cisco MDS 9706",
        "firmware": "9.4(2a)",
        "ports": all_ports,
        "alerts": alerts,
        "total_ports": 48,
        "ports_up": sum(1 for p in all_ports if p["status"] == "up"),
        "ports_down": sum(1 for p in all_ports if p["status"] == "down"),
    }


@tool
def mds_zoneset(hostname: str) -> dict:
    """Get active zoneset and zone members for an MDS switch.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)

    Returns:
        Active zoneset with zone names and WWPN members.
    """
    return {
        "hostname": hostname,
        "vsan": 100,
        "active_zoneset": "zs_prod_lva1",
        "zones": [
            {
                "name": "z_array05_host10",
                "members": [
                    {"wwpn": "21:00:00:24:ff:4a:12:01", "alias": "stor-lva1-array05-hba1", "logged_in": True},
                    {"wwpn": "50:00:09:72:08:60:2a:00", "alias": "esxi-lva1-host10-hba1", "logged_in": True},
                ],
            },
            {
                "name": "z_array05_host11",
                "members": [
                    {"wwpn": "21:00:00:24:ff:4a:12:02", "alias": "stor-lva1-array05-hba2", "logged_in": True},
                    {"wwpn": "50:00:09:72:08:60:2a:01", "alias": "esxi-lva1-host11-hba1", "logged_in": True},
                ],
            },
            {
                "name": "z_array05_host12_DEGRADED",
                "members": [
                    {"wwpn": "21:00:00:24:ff:4a:12:03", "alias": "stor-lva1-array05-hba3", "logged_in": False},
                    {"wwpn": "50:00:09:72:08:60:2a:02", "alias": "esxi-lva1-host12-hba1", "logged_in": True},
                ],
            },
        ],
        "total_zones": 3,
        "alerts": ["z_array05_host12_DEGRADED: member 21:00:00:24:ff:4a:12:03 not logged in"],
    }
```

### `tools/esxi.py`

```python
"""ESXi / VMware tools — synthetic data for POC."""

from langchain_core.tools import tool


@tool
def esxi_vm_status(hostname: str) -> dict:
    """Get ESXi host or VM status — power state, CPU, memory, datastore, and alerts.

    Args:
        hostname: ESXi host or VM name (e.g. esxi-lva1-host10)

    Returns:
        Host/VM status with resource usage and alerts.
    """
    return {
        "hostname": hostname,
        "type": "ESXi Host",
        "power_state": "poweredOn",
        "esxi_version": "8.0 Update 2",
        "cpu_cores": 64,
        "cpu_usage_percent": 78.5,
        "memory_total_gb": 512,
        "memory_used_gb": 471.6,
        "memory_usage_percent": 92.1,
        "vms_running": 23,
        "vms_total": 25,
        "datastores": [
            {"name": "ds-lva1-stor05", "capacity_tb": 50.0, "free_tb": 2.7,
             "read_latency_ms": 12.5, "write_latency_ms": 45.2, "type": "VMFS6"},
            {"name": "ds-lva1-stor03", "capacity_tb": 30.0, "free_tb": 12.1,
             "read_latency_ms": 3.2, "write_latency_ms": 4.1, "type": "VMFS6"},
        ],
        "hbas": [
            {"name": "vmhba2", "wwpn": "50:00:09:72:08:60:2a:00", "status": "online",
             "speed": "32Gbps", "fabric": "fab-lva1-a"},
            {"name": "vmhba3", "wwpn": "50:00:09:72:08:60:2a:10", "status": "online",
             "speed": "32Gbps", "fabric": "fab-lva1-b"},
        ],
        "alerts": [
            "Memory usage 92.1% — above 90% threshold",
            "ds-lva1-stor05: write latency 45.2ms — 3.6x above baseline (12ms)",
            "ds-lva1-stor05: free space 5.4% — below 10% threshold",
        ],
        "recent_events": [
            {"time": "2026-04-12T08:30:00Z", "event": "SCSI sense error on ds-lva1-stor05"},
            {"time": "2026-04-12T07:15:00Z", "event": "Path failover on vmhba2 — path restored"},
        ],
    }


@tool
def datastore_health(datastore_name: str) -> dict:
    """Get detailed datastore health — capacity, latency, SCSI errors, and connected hosts.

    Args:
        datastore_name: Datastore name (e.g. ds-lva1-stor05)

    Returns:
        Datastore health with capacity, latency, errors, and alerts.
    """
    return {
        "datastore": datastore_name,
        "type": "VMFS6",
        "backing_array": "stor-lva1-array05",
        "backing_lun": "LUN-0042",
        "capacity_tb": 50.0,
        "used_tb": 47.3,
        "free_tb": 2.7,
        "free_percent": 5.4,
        "avg_read_latency_ms": 12.5,
        "avg_write_latency_ms": 45.2,
        "peak_write_latency_ms": 120.0,
        "iops_read": 15000,
        "iops_write": 8500,
        "scsi_errors_24h": 8,
        "scsi_errors_7d": 12,
        "connected_hosts": [
            {"host": "esxi-lva1-host10", "path_count": 4, "active_paths": 3, "status": "degraded"},
            {"host": "esxi-lva1-host11", "path_count": 4, "active_paths": 4, "status": "healthy"},
            {"host": "esxi-lva1-host12", "path_count": 4, "active_paths": 2, "status": "degraded"},
        ],
        "snapshots": [
            {"vm": "prod-db-01", "size_gb": 80.5, "age_days": 14, "description": "pre-upgrade"},
            {"vm": "prod-app-03", "size_gb": 25.0, "age_days": 7, "description": "backup"},
            {"vm": "prod-app-07", "size_gb": 15.0, "age_days": 30, "description": "test"},
        ],
        "alerts": [
            "Free space 5.4% — CRITICAL (threshold 10%)",
            "Write latency 45.2ms — 3.6x above 7-day baseline",
            "8 SCSI sense errors in 24h — investigate backing array",
            "3 VMs with stale snapshots consuming 120.5 GB",
            "esxi-lva1-host10: only 3/4 paths active (degraded multipathing)",
        ],
    }
```

### `tools/storage_array.py`

```python
"""Storage array tools — synthetic data for POC."""

from langchain_core.tools import tool


@tool
def array_health(array_name: str) -> dict:
    """Get storage array health — disk state, RAID status, I/O latency, rebuild progress.

    Args:
        array_name: Storage array name (e.g. stor-lva1-array05)

    Returns:
        Array health with disk counts, RAID groups, performance, and alerts.
    """
    return {
        "array_name": array_name,
        "model": "Dell PowerStore 9200T",
        "firmware": "3.6.0.1",
        "status": "degraded",
        "serial": "PS9200T-LVA1-05",
        "total_disks": 240,
        "healthy_disks": 237,
        "failed_disks": 2,
        "rebuilding_disks": 1,
        "spare_disks": 8,
        "raid_groups": [
            {"name": "rg01", "status": "optimal", "type": "RAID6", "disks": 24,
             "capacity_tb": 40.0, "used_percent": 78.5},
            {"name": "rg02", "status": "degraded", "type": "RAID6", "disks": 24,
             "capacity_tb": 40.0, "used_percent": 82.1,
             "failed_disk": "disk-2-14", "failure_time": "2026-04-12T06:30:00Z"},
            {"name": "rg03", "status": "rebuilding", "type": "RAID6", "disks": 24,
             "capacity_tb": 40.0, "used_percent": 65.3,
             "rebuilding_disk": "disk-3-08", "rebuild_percent": 43.2,
             "rebuild_start": "2026-04-12T07:00:00Z", "rebuild_eta_hours": 6.5},
        ],
        "performance": {
            "avg_read_latency_ms": 3.2,
            "avg_write_latency_ms": 8.5,
            "iops_total": 45000,
            "throughput_mbps": 3200,
            "cache_hit_percent": 72.5,
        },
        "controllers": [
            {"id": "ctrl-A", "status": "online", "cpu_percent": 45, "memory_percent": 62},
            {"id": "ctrl-B", "status": "online", "cpu_percent": 42, "memory_percent": 58},
        ],
        "alerts": [
            "CRITICAL: RG02 degraded -- disk-2-14 failed at 06:30 UTC",
            "WARNING: RG03 rebuilding -- disk-3-08, 43.2% complete, ETA 6.5 hours",
            "WARNING: 2 failed disks -- only 8 hot spares remaining",
            "INFO: Write latency elevated 8.5ms (baseline 4ms) during rebuild",
        ],
    }


@tool
def disk_failures(cluster_name: str, time_window_hours: int = 24) -> dict:
    """Get disk failure report — failed/degraded disks, SMART data, replacement status.

    Args:
        cluster_name: Storage cluster name (e.g. stor-lva1)
        time_window_hours: Lookback window in hours (default 24)

    Returns:
        Failed disks with SMART status, replacement tickets, and trend analysis.
    """
    return {
        "cluster_name": cluster_name,
        "time_window_hours": time_window_hours,
        "failed_disks": [
            {
                "disk_id": "disk-2-14",
                "array": "stor-lva1-array05",
                "slot": "enclosure-2, slot-14",
                "model": "Seagate ST16000NM002J",
                "capacity_tb": 16,
                "failure_time": "2026-04-12T06:30:00Z",
                "smart_status": "FAILING",
                "smart_details": {
                    "reallocated_sectors": 842,
                    "pending_sectors": 156,
                    "temperature_c": 52,
                    "power_on_hours": 43200,
                },
                "replacement_ticket": "STOR-44521",
                "replacement_status": "pending — part ordered",
                "eta": "2026-04-13T10:00:00Z",
            },
            {
                "disk_id": "disk-5-08",
                "array": "stor-lva1-array03",
                "slot": "enclosure-5, slot-08",
                "model": "Seagate ST16000NM002J",
                "capacity_tb": 16,
                "failure_time": "2026-04-11T22:15:00Z",
                "smart_status": "FAILED",
                "smart_details": {
                    "reallocated_sectors": 2048,
                    "pending_sectors": 0,
                    "temperature_c": 48,
                    "power_on_hours": 51000,
                },
                "replacement_ticket": "STOR-44519",
                "replacement_status": "shipped — in transit",
                "eta": "2026-04-12T14:00:00Z",
            },
        ],
        "trend_analysis": {
            "failures_24h": 1,
            "failures_7d": 4,
            "failures_30d": 8,
            "normal_rate_30d": 3,
            "assessment": "ELEVATED — 2.7x normal failure rate. Check batch/firmware correlation.",
        },
        "affected_raid_groups": ["rg02 (degraded)", "rg03 (rebuilding)"],
    }
```

### `tools/rv_tool.py`

```python
"""RV Tool integration — synthetic data for POC."""

from langchain_core.tools import tool


@tool
def rv_tool_check(hostname: str, check_type: str = "all") -> dict:
    """Run RV tool health check for a storage host — connectivity, firmware, zoning.

    Args:
        hostname: Target hostname (e.g. lva1-mds01 or stor-lva1-array05)
        check_type: Check type — connectivity, firmware, zoning, or all (default all)

    Returns:
        RV tool check results with pass/fail per category.
    """
    results = {
        "connectivity": {
            "status": "pass",
            "details": {
                "fabric_a": {"reachable": True, "latency_ms": 0.3, "switch": "lva1-mds01"},
                "fabric_b": {"reachable": True, "latency_ms": 0.4, "switch": "lva1-mds02"},
                "paths_total": 4,
                "paths_active": 3,
                "paths_standby": 1,
            },
            "alerts": ["1 path in standby — verify if intentional"],
        },
        "firmware": {
            "status": "pass",
            "details": {
                "current_version": "9.4(2a)",
                "recommended_version": "9.4(2a)",
                "hba_firmware": "14.2.507.15",
                "hba_recommended": "14.2.507.15",
            },
            "alerts": [],
        },
        "zoning": {
            "status": "warning",
            "details": {
                "active_zoneset": "zs_prod_lva1",
                "zones_for_host": 3,
                "orphan_zones": 1,
                "single_initiator_zones": True,
            },
            "alerts": ["1 orphan zone detected: z_array05_host12_DEGRADED — member not logged in"],
        },
    }

    if check_type != "all":
        if check_type not in results:
            return {"error": f"Unknown check_type '{check_type}'. Options: connectivity, firmware, zoning, all"}
        results = {check_type: results[check_type]}

    overall = "pass"
    for check in results.values():
        if check["status"] == "fail":
            overall = "fail"
            break
        if check["status"] == "warning":
            overall = "warning"

    return {
        "hostname": hostname,
        "check_type": check_type,
        "overall_status": overall,
        "results": results,
        "timestamp": "2026-04-12T09:30:00Z",
    }
```

### `tools/fabric.py`

```python
"""FC Fabric topology tools — synthetic data for POC."""

from langchain_core.tools import tool


@tool
def fabric_topology(fabric_name: str) -> dict:
    """Get FC fabric topology — switches, ISL links, path redundancy.

    Args:
        fabric_name: Fabric name (e.g. fab-lva1-a)

    Returns:
        Fabric topology with switches, ISLs, and redundancy assessment.
    """
    return {
        "fabric_name": fabric_name,
        "vsan": 100,
        "principal_switch": "lva1-mds01",
        "switches": [
            {
                "name": "lva1-mds01",
                "role": "principal",
                "domain_id": 1,
                "model": "Cisco MDS 9706",
                "firmware": "9.4(2a)",
                "ports_up": 45,
                "ports_down": 1,
                "ports_total": 48,
                "uptime_days": 182,
            },
            {
                "name": "lva1-mds02",
                "role": "subordinate",
                "domain_id": 2,
                "model": "Cisco MDS 9706",
                "firmware": "9.4(2a)",
                "ports_up": 44,
                "ports_down": 0,
                "ports_total": 48,
                "uptime_days": 182,
            },
        ],
        "isl_links": [
            {"src": "lva1-mds01:fc1/47", "dst": "lva1-mds02:fc1/47",
             "speed": "32Gbps", "status": "up", "utilization_percent": 35},
            {"src": "lva1-mds01:fc1/48", "dst": "lva1-mds02:fc1/48",
             "speed": "32Gbps", "status": "up", "utilization_percent": 32},
        ],
        "path_redundancy": "FULL — 2 ISL links active between switches",
        "connected_devices": {
            "storage_arrays": ["stor-lva1-array03", "stor-lva1-array05"],
            "esxi_hosts": ["esxi-lva1-host10", "esxi-lva1-host11", "esxi-lva1-host12"],
            "total_initiators": 6,
            "total_targets": 4,
        },
        "alerts": [
            "lva1-mds01: fc1/3 DOWN — connected device stor-lva1-array05-hba3 unreachable",
        ],
    }
```

### `tools/runbooks.py`

```python
"""Runbook search and loading tools."""

from pathlib import Path
from langchain_core.tools import tool

RUNBOOKS_PATH = Path(__file__).parent.parent / "runbooks"
MAX_RUNBOOK_CHARS = 15_000


@tool
def search_runbooks(query: str, max_results: int = 5) -> str:
    """Search storage oncall runbooks by keyword. Returns matching runbook names and snippets.

    Args:
        query: Search query (e.g. 'MDS port flap', 'disk failure', 'ESXi hang')
        max_results: Maximum results to return (default 5)

    Returns:
        Formatted list of matching runbooks with snippets.
    """
    results = []
    query_lower = query.lower()

    for md_file in sorted(RUNBOOKS_PATH.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        title_line = content.split("\n")[0].lstrip("# ").strip()
        score = 0

        # Score by filename match (strongest signal)
        for word in query_lower.split():
            if word in md_file.stem.lower():
                score += 3

        # Score by content match
        for word in query_lower.split():
            if word in content.lower():
                score += 1

        if score > 0:
            snippet = content[:300].replace("\n", " ").strip()
            results.append({
                "title": title_line,
                "file": md_file.name,
                "score": score,
                "snippet": snippet,
            })

    results.sort(key=lambda r: r["score"], reverse=True)

    if not results:
        available = [f.stem for f in RUNBOOKS_PATH.glob("*.md")]
        return f"No runbooks found matching '{query}'. Available runbooks: {available}"

    lines = [f"Found {min(len(results), max_results)} matching runbook(s):\n"]
    for r in results[:max_results]:
        lines.append(f"**{r['title']}** (`{r['file']}`, relevance={r['score']})")
        lines.append(f"  {r['snippet'][:200]}...\n")
    lines.append("Use `load_runbook` with the filename to read the full content.")
    return "\n".join(lines)


@tool
def load_runbook(runbook_name: str) -> str:
    """Load the full content of a storage runbook.

    Args:
        runbook_name: Runbook filename from search_runbooks (e.g. 'mds-port-flap.md')

    Returns:
        Full runbook content as markdown text.
    """
    # Security: block path traversal
    if ".." in runbook_name or "/" in runbook_name or "\\" in runbook_name:
        return "Error: Invalid runbook name — path traversal not allowed."

    target = RUNBOOKS_PATH / runbook_name
    if not target.exists():
        # Try with .md extension
        target = RUNBOOKS_PATH / f"{runbook_name}.md"

    if not target.exists():
        available = [f.name for f in RUNBOOKS_PATH.glob("*.md")]
        return f"Runbook '{runbook_name}' not found. Available: {available}"

    content = target.read_text(encoding="utf-8")
    if len(content) > MAX_RUNBOOK_CHARS:
        content = content[:MAX_RUNBOOK_CHARS] + f"\n\n... [truncated at {MAX_RUNBOOK_CHARS} chars]"
    return content
```

### `tools/backup.py`

```python
"""Backup status tools — synthetic data for POC."""

from langchain_core.tools import tool


SYNTHETIC_BACKUP_DATA = [
    {
        "vm_name": "prod-db-01",
        "backup_type": "full",
        "status": "failed",
        "error": "snapshot_locked",
        "error_detail": "Cannot create snapshot — existing snapshot 'pre-upgrade' is 14 days old and locked",
        "last_success": "2026-04-10T02:00:00Z",
        "failed_at": "2026-04-12T02:15:00Z",
        "datastore": "ds-lva1-stor05",
        "backup_size_gb": 450,
        "backup_server": "bkp-lva1-01",
        "policy": "daily-full",
        "sla": "RPO 24h",
        "sla_violated": True,
        "owner_team": "database-infra",
        "priority": "P1",
    },
    {
        "vm_name": "prod-app-03",
        "backup_type": "incremental",
        "status": "failed",
        "error": "disk_full",
        "error_detail": "Backup target volume /backup/lva1 is at 98.2% capacity — 12 GB free, need 85 GB",
        "last_success": "2026-04-11T02:00:00Z",
        "failed_at": "2026-04-12T02:30:00Z",
        "datastore": "ds-lva1-stor03",
        "backup_size_gb": 85,
        "backup_server": "bkp-lva1-01",
        "policy": "daily-incremental",
        "sla": "RPO 24h",
        "sla_violated": False,
        "owner_team": "app-platform",
        "priority": "P2",
    },
    {
        "vm_name": "prod-web-07",
        "backup_type": "full",
        "status": "failed",
        "error": "timeout",
        "error_detail": "Backup timed out after 6 hours — VM I/O latency was 120ms during backup window",
        "last_success": "2026-04-09T02:00:00Z",
        "failed_at": "2026-04-12T08:00:00Z",
        "datastore": "ds-lva1-stor05",
        "backup_size_gb": 200,
        "backup_server": "bkp-lva1-02",
        "policy": "daily-full",
        "sla": "RPO 24h",
        "sla_violated": True,
        "owner_team": "web-infra",
        "priority": "P1",
    },
    {
        "vm_name": "staging-api-01",
        "backup_type": "incremental",
        "status": "failed",
        "error": "network_error",
        "error_detail": "Connection refused to backup target — bkp-lva1-02 agent not responding on port 9392",
        "last_success": "2026-04-11T03:00:00Z",
        "failed_at": "2026-04-12T03:10:00Z",
        "datastore": "ds-lva1-stor03",
        "backup_size_gb": 30,
        "backup_server": "bkp-lva1-02",
        "policy": "daily-incremental",
        "sla": "RPO 48h",
        "sla_violated": False,
        "owner_team": "qa-infra",
        "priority": "P3",
    },
    {
        "vm_name": "prod-db-05",
        "backup_type": "full",
        "status": "success",
        "last_success": "2026-04-12T04:30:00Z",
        "datastore": "ds-lva1-stor03",
        "backup_size_gb": 320,
        "backup_server": "bkp-lva1-01",
        "policy": "daily-full",
        "sla": "RPO 24h",
        "sla_violated": False,
        "owner_team": "database-infra",
        "priority": "P1",
    },
]


@tool
def get_backup_status(
    status: str = "failed",
    hours: int = 24,
    vm_name: str = "",
) -> dict:
    """Get VM backup status — failed, success, or all. Includes error details, SLA status, and owner team.

    Args:
        status: Filter — failed, success, or all (default failed)
        hours: Lookback window in hours (default 24)
        vm_name: Optional — filter to a specific VM name

    Returns:
        List of backup jobs with status, errors, SLA info, and owner team.
    """
    results = SYNTHETIC_BACKUP_DATA

    if vm_name:
        results = [r for r in results if vm_name.lower() in r["vm_name"].lower()]
    elif status != "all":
        results = [r for r in results if r["status"] == status]

    sla_violations = sum(1 for r in results if r.get("sla_violated"))

    return {
        "backups": results,
        "count": len(results),
        "sla_violations": sla_violations,
        "summary": {
            "total_failed": sum(1 for r in SYNTHETIC_BACKUP_DATA if r["status"] == "failed"),
            "total_success": sum(1 for r in SYNTHETIC_BACKUP_DATA if r["status"] == "success"),
            "unique_errors": list({r.get("error", "") for r in results if r.get("error")}),
            "affected_backup_servers": list({r["backup_server"] for r in results}),
        },
    }
```

### `app/agent.py`

```python
"""LangGraph ReAct agent setup — the brain of the system."""

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.config import ANTHROPIC_API_KEY, MODEL_NAME, MAX_ITERATIONS
from tools import ALL_TOOLS


SYSTEM_PROMPT = """You are a Storage Infrastructure Oncall Assistant.

You help storage engineers triage and resolve incidents involving:
- **MDS Fibre Channel switches** — port flaps, zoning issues, CRC errors, ISL failures
- **Storage arrays** — disk failures, RAID degradation, I/O latency, rebuild progress
- **ESXi VMs and datastores** — VM hangs, datastore latency, capacity issues, SCSI errors
- **RV Tool** — connectivity checks, firmware validation, zoning verification
- **FC Fabrics** — topology, ISL links, path redundancy

## Your Triage Workflow

1. **ALWAYS call `get_storage_incidents` FIRST** to see active incidents
2. Use infrastructure tools to gather data (mds_port_status, array_health, esxi_vm_status, etc.)
3. Use `search_runbooks` and `load_runbook` to find and follow standard procedures
4. Correlate findings across tools — a disk failure may cause latency on ESXi hosts
5. Synthesize everything into a structured triage report

## Triage Report Format

Always end your analysis with a structured report:

### Root Cause
What broke and why (confirmed or suspected).

### Blast Radius
- Affected devices (switches, arrays, hosts)
- Affected VMs and services
- Quantify the impact (numbers matter)

### Immediate Actions
Step-by-step what to do RIGHT NOW, in priority order.

### Follow-up Actions
What to do after the immediate fire is out.

### Escalation
Who to contact if this gets worse — include specific teams.

## Rules
- Never guess infrastructure state — always query tools first
- If a tool returns an error, report it and try an alternative
- Be specific: hostnames, port numbers, error counts, timestamps
- Time is critical during incidents — be concise and actionable
- Correlate across tools — storage issues cascade (disk → array → datastore → VM)
"""


def create_agent():
    """Create and return the LangGraph ReAct agent."""
    llm = ChatAnthropic(
        model=MODEL_NAME,
        api_key=ANTHROPIC_API_KEY,
        temperature=0,
        max_tokens=8192,
    )

    # MemorySaver keeps conversation history in memory.
    # For persistence across restarts, replace with SqliteSaver.
    checkpointer = MemorySaver()

    agent = create_react_agent(
        model=llm,
        tools=ALL_TOOLS,
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer,
    )

    return agent
```

### `app/main.py`

```python
"""Streamlit chat interface for the Storage Oncall Agent."""

import uuid
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.agent import create_agent

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Storage Oncall Agent",
    page_icon="💾",
    layout="wide",
)

st.title("💾 Storage Oncall Agent")
st.caption("AI-powered triage for MDS switches, storage arrays, ESXi VMs, and FC fabrics")

# ── Session state ────────────────────────────────────────────
if "agent" not in st.session_state:
    st.session_state.agent = create_agent()
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.header("Quick Actions")
    if st.button("🔥 Show Active Incidents"):
        st.session_state.quick_action = "Show me all active storage incidents"
    if st.button("🔍 Check MDS lva1-mds01"):
        st.session_state.quick_action = "Check MDS switch lva1-mds01 — give me full port status"
    if st.button("💿 Array Health"):
        st.session_state.quick_action = "Check storage array stor-lva1-array05 health"
    if st.button("🖥️ ESXi Status"):
        st.session_state.quick_action = "Check ESXi host esxi-lva1-host10 status"
    if st.button("🌐 Fabric Topology"):
        st.session_state.quick_action = "Show FC fabric fab-lva1-a topology"

    st.divider()
    if st.button("🗑️ New Conversation"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.header("Available Tools")
    st.markdown("""
    - `get_storage_incidents` — Active incidents
    - `mds_port_status` — MDS switch ports
    - `mds_zoneset` — FC zoning
    - `esxi_vm_status` — ESXi host/VM info
    - `datastore_health` — Datastore details
    - `array_health` — Storage array status
    - `disk_failures` — Disk failure report
    - `rv_tool_check` — RV tool checks
    - `fabric_topology` — FC fabric map
    - `search_runbooks` — Find runbooks
    - `load_runbook` — Read a runbook
    """)

# ── Chat history display ────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    elif msg["role"] == "assistant":
        with st.chat_message("assistant"):
            st.write(msg["content"])
    elif msg["role"] == "tool":
        with st.chat_message("assistant", avatar="🔧"):
            st.caption(f"Tool: {msg.get('tool_name', 'unknown')}")
            with st.expander("Tool result", expanded=False):
                st.code(msg["content"][:2000], language="json")

# ── Handle quick actions ─────────────────────────────────────
if "quick_action" in st.session_state:
    user_input = st.session_state.pop("quick_action")
else:
    user_input = st.chat_input("Describe the storage issue or ask a question...")

# ── Process user input ───────────────────────────────────────
if user_input:
    # Show user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Run agent
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        response_placeholder = st.empty()

        full_response = ""
        tool_calls_made = []

        try:
            for event in st.session_state.agent.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config=config,
                stream_mode="updates",
            ):
                for node_name, node_output in event.items():
                    if "messages" not in node_output:
                        continue

                    for message in node_output["messages"]:
                        # AI message with tool calls — show status
                        if isinstance(message, AIMessage) and message.tool_calls:
                            for tc in message.tool_calls:
                                tool_name = tc["name"]
                                tool_args = tc.get("args", {})
                                tool_calls_made.append(tool_name)
                                status_placeholder.info(
                                    f"🔧 Calling **{tool_name}**({', '.join(f'{k}={v!r}' for k, v in tool_args.items())})"
                                )

                        # Tool results — log them
                        elif isinstance(message, ToolMessage):
                            st.session_state.messages.append({
                                "role": "tool",
                                "tool_name": message.name,
                                "content": str(message.content)[:2000],
                            })

                        # Final AI text response
                        elif isinstance(message, AIMessage) and message.content and not message.tool_calls:
                            full_response = message.content

            status_placeholder.empty()
            if full_response:
                response_placeholder.write(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            if tool_calls_made:
                st.caption(f"Tools used: {', '.join(tool_calls_made)}")

        except Exception as e:
            st.error(f"Error: {e}")
            st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})
```

### `app/__init__.py`

```python
# Storage Oncall Agent
```

### `tests/test_tools.py`

```python
"""Unit tests for all tools — verifies synthetic data returns correctly."""

from tools.incidents import get_storage_incidents
from tools.mds import mds_port_status, mds_zoneset
from tools.esxi import esxi_vm_status, datastore_health
from tools.storage_array import array_health, disk_failures
from tools.rv_tool import rv_tool_check
from tools.fabric import fabric_topology
from tools.runbooks import search_runbooks, load_runbook


class TestIncidentTools:
    def test_get_all_incidents(self):
        result = get_storage_incidents.invoke({"severity": "ALL", "status": "ALL"})
        assert result["count"] >= 3

    def test_filter_active_only(self):
        result = get_storage_incidents.invoke({"status": "active"})
        for inc in result["incidents"]:
            assert inc["status"] == "active"

    def test_filter_by_severity(self):
        result = get_storage_incidents.invoke({"severity": "SEV2"})
        for inc in result["incidents"]:
            assert inc["severity"] == "SEV2"


class TestMDSTools:
    def test_port_status(self):
        result = mds_port_status.invoke({"hostname": "lva1-mds01"})
        assert result["hostname"] == "lva1-mds01"
        assert len(result["ports"]) > 0
        assert any(p["status"] == "down" for p in result["ports"])

    def test_port_status_specific_interface(self):
        result = mds_port_status.invoke({"hostname": "lva1-mds01", "interface": "fc1/3"})
        assert len(result["ports"]) == 1
        assert result["ports"][0]["interface"] == "fc1/3"

    def test_zoneset(self):
        result = mds_zoneset.invoke({"hostname": "lva1-mds01"})
        assert result["active_zoneset"] == "zs_prod_lva1"
        assert len(result["zones"]) > 0


class TestESXiTools:
    def test_vm_status(self):
        result = esxi_vm_status.invoke({"hostname": "esxi-lva1-host10"})
        assert result["power_state"] == "poweredOn"
        assert result["memory_usage_percent"] > 90

    def test_datastore_health(self):
        result = datastore_health.invoke({"datastore_name": "ds-lva1-stor05"})
        assert result["free_percent"] < 10
        assert len(result["alerts"]) > 0


class TestStorageArrayTools:
    def test_array_health(self):
        result = array_health.invoke({"array_name": "stor-lva1-array05"})
        assert result["status"] == "degraded"
        assert result["failed_disks"] >= 1

    def test_disk_failures(self):
        result = disk_failures.invoke({"cluster_name": "stor-lva1"})
        assert len(result["failed_disks"]) >= 1
        assert result["trend_analysis"]["assessment"].startswith("ELEVATED")


class TestRVTool:
    def test_all_checks(self):
        result = rv_tool_check.invoke({"hostname": "lva1-mds01"})
        assert result["overall_status"] in ("pass", "warning", "fail")

    def test_specific_check(self):
        result = rv_tool_check.invoke({"hostname": "lva1-mds01", "check_type": "firmware"})
        assert "firmware" in result["results"]


class TestFabricTools:
    def test_topology(self):
        result = fabric_topology.invoke({"fabric_name": "fab-lva1-a"})
        assert len(result["switches"]) >= 2
        assert len(result["isl_links"]) >= 1


class TestRunbookTools:
    def test_search_finds_mds(self):
        result = search_runbooks.invoke({"query": "MDS port flap"})
        assert "mds" in result.lower()

    def test_load_runbook(self):
        result = load_runbook.invoke({"runbook_name": "mds-port-flap.md"})
        assert "MDS" in result or "port" in result.lower()

    def test_load_nonexistent(self):
        result = load_runbook.invoke({"runbook_name": "nonexistent.md"})
        assert "not found" in result.lower()

    def test_path_traversal_blocked(self):
        result = load_runbook.invoke({"runbook_name": "../../etc/passwd"})
        assert "error" in result.lower() or "invalid" in result.lower()
```

---

## 7. Runbooks <a name="7-runbooks"></a>

### `runbooks/mds-port-flap.md`

```markdown
# MDS Switch Port Flap Troubleshooting

## Symptoms
- FC port toggling up/down repeatedly (flap count > 5 in 24h)
- CRC error counters incrementing on the interface
- Connected hosts losing storage paths or experiencing I/O timeouts
- Zone members showing as "not logged in"

## Severity Guide
- **SEV2**: Multiple ports flapping OR ISL port affected
- **SEV3**: Single host port flapping, redundant paths available

## Triage Steps

### Step 1: Assess the scope
- Run `mds_port_status` to check all ports on the switch
- Count how many ports are flapping vs. total ports
- Check if ISL ports (inter-switch links) are affected — this is CRITICAL

### Step 2: Identify the pattern
- **CRC errors + flaps** = Physical layer issue (bad SFP, cable, or dirty connector)
- **Flaps without CRC errors** = Host HBA issue or firmware bug
- **Multiple ports flapping simultaneously** = Switch hardware issue or power problem

### Step 3: Check connected devices
- Run `mds_zoneset` to identify which hosts/arrays are on the affected port
- Run `esxi_vm_status` for affected ESXi hosts to check multipath status
- Run `array_health` if a storage array is on the affected port

### Step 4: Check fabric impact
- Run `fabric_topology` to verify ISL redundancy
- If ISL is down: CRITICAL — all cross-switch traffic affected

## Remediation

### Bad SFP/Cable (CRC errors present)
1. Check if redundant path exists (run `rv_tool_check` with check_type=connectivity)
2. If redundant path is UP: schedule SFP replacement during maintenance window
3. If NO redundant path: emergency SFP swap
   - Get replacement SFP from spare inventory
   - Bounce the port: `shut` / `no shut` on the interface
   - If bounce doesn't help: swap SFP
4. Clean fiber connectors with IPA wipes before reinserting

### Host HBA Issue (no CRC errors)
1. Check HBA firmware against recommended version (`rv_tool_check` firmware)
2. Restart HBA driver on the host (ESXi: `esxcli storage core adapter rescan`)
3. If persists: replace HBA during next maintenance window

### Switch Hardware Issue (multiple ports)
1. **Escalate immediately** — page storage-infra-lead
2. Drain the switch if possible (redirect traffic to redundant paths)
3. RMA the switch line card or chassis

## Escalation
- Single port, redundant path available: Handle during business hours
- ISL port or multiple ports: Page `storage-infra-oncall` immediately
- Switch hardware suspected: Page `storage-infra-lead` + open vendor TAC case
```

### `runbooks/disk-failure.md`

```markdown
# Storage Array Disk Failure Troubleshooting

## Symptoms
- RAID group status: degraded or rebuilding
- Disk SMART status: FAILING or FAILED
- Elevated I/O latency during rebuild
- Replacement tickets generated automatically

## Severity Guide
- **SEV1**: 2+ disks failed in same RAID group (data at risk)
- **SEV2**: 1 disk failed, RAID degraded, rebuild in progress
- **SEV3**: Disk SMART predictive failure, no RAID impact yet

## Triage Steps

### Step 1: Assess array health
- Run `array_health` to see RAID group status, rebuild progress, and spare count
- Check if multiple RAID groups are affected

### Step 2: Check disk failure details
- Run `disk_failures` to see SMART data, replacement ticket status, and trend
- Look at `power_on_hours` — old disks (>40K hours) fail more often
- Check if failures are in the same enclosure (hardware issue)

### Step 3: Assess blast radius
- Run `datastore_health` for datastores backed by this array
- Run `esxi_vm_status` for hosts using those datastores
- Count affected VMs

### Step 4: Monitor rebuild
- Rebuild ETA is in `array_health` output
- Elevated write latency is NORMAL during rebuild — warn affected teams
- Do NOT rebalance or move data during rebuild

## Remediation

### Single Disk Failure (RAID degraded)
1. Verify hot spare has been activated (check `rebuilding_disks` count)
2. Confirm replacement ticket exists (`disk_failures` → `replacement_ticket`)
3. Monitor rebuild progress — do NOT interrupt
4. After rebuild completes: replace failed disk with new spare

### SMART Predictive Failure
1. Disk is still functioning but predicted to fail soon
2. Schedule proactive replacement during maintenance window
3. Ensure hot spares are available

### Multiple Disk Failures (CRITICAL)
1. **ESCALATE IMMEDIATELY** — data at risk if another disk fails
2. Stop all non-essential I/O to the array
3. Do NOT start any new rebuilds
4. Contact vendor support for emergency assistance
5. Consider failover to secondary array if available

## Escalation
- Single disk, rebuild in progress: Informational — monitor
- Multiple disks, same RAID group: Page `storage-infra-lead` IMMEDIATELY
- Elevated failure rate trend: Create problem ticket for root cause analysis
```

### `runbooks/esxi-vm-hang.md`

```markdown
# ESXi VM Hang / Performance Degradation

## Symptoms
- VMs unresponsive or extremely slow
- High datastore latency (> 20ms write)
- SCSI sense errors in ESXi logs
- Memory usage above 90% on host

## Triage Steps

### Step 1: Check host status
- Run `esxi_vm_status` for the affected host
- Look at CPU, memory, and datastore latency

### Step 2: Check datastore backing
- Run `datastore_health` for the high-latency datastore
- Check if the backing storage array is degraded

### Step 3: Check storage array
- If datastore latency is high → run `array_health` for the backing array
- RAID rebuild causes latency spikes — this is expected

### Step 4: Check FC paths
- Run `rv_tool_check` with connectivity check
- Verify multipathing is active (all paths should be "active")

## Remediation
- **Datastore full**: Delete stale snapshots, migrate VMs to another datastore
- **Array degraded**: Wait for rebuild, notify affected teams about latency
- **Path failure**: Check MDS switch port status, bounce HBA if needed
- **Memory pressure**: vMotion VMs to less loaded hosts

## Escalation
- Multiple VMs down: Page `vm-infra-oncall`
- Storage array unresponsive: Page `storage-infra-oncall`
```

### `runbooks/datastore-full.md`

```markdown
# Datastore Full / Low Space

## Symptoms
- Datastore free space below 10%
- VM provisioning failures
- Snapshot growth consuming space

## Triage Steps

### Step 1: Check datastore details
- Run `datastore_health` to see capacity, snapshots, connected hosts

### Step 2: Identify space consumers
- Check snapshot list in datastore_health output
- Look for stale snapshots (age > 7 days)

### Step 3: Assess impact
- Run `esxi_vm_status` for hosts using this datastore
- Check if VMs are affected by low space

## Remediation

### Stale Snapshots (most common cause)
1. Identify snapshots older than 7 days
2. Verify with VM owner before deleting
3. Delete snapshots starting with oldest
4. Monitor space recovery — snapshot deletion can be slow

### Legitimate Growth
1. Migrate VMs to datastores with more space
2. Request storage expansion (create JIRA ticket)
3. Set up monitoring alert at 15% free (early warning)

## Escalation
- Below 5% free: Immediate action required
- Below 2% free: Page `storage-infra-oncall` — VMs may crash
```

### `runbooks/rv-tool-errors.md`

```markdown
# RV Tool Check Failures

## Symptoms
- RV tool connectivity check failing
- Zoning mismatches detected
- Firmware version mismatch

## Triage Steps

### Step 1: Run comprehensive check
- Run `rv_tool_check` with check_type=all
- Review each category: connectivity, firmware, zoning

### Step 2: For connectivity failures
- Run `fabric_topology` to check ISL and switch health
- Run `mds_port_status` on the relevant switch

### Step 3: For zoning issues
- Run `mds_zoneset` to check active zoneset
- Look for orphan zones (no logged-in members)

## Remediation
- **Connectivity failure**: Check physical layer (SFP, cable, port)
- **Firmware mismatch**: Schedule firmware upgrade in maintenance window
- **Orphan zones**: Clean up after confirming devices are decommissioned
```

### `runbooks/backup-failure.md`

This is a **skill** — it tells the agent HOW to investigate, step by step, using telemetry tools. It does NOT tell the agent to fix anything. It gathers evidence and escalates to a human.

```markdown
# Skill: Backup Failure Investigation

> **Purpose:** Systematically investigate VM backup failures using telemetry, determine root cause, assess blast radius, and escalate to the right human with all evidence. **DO NOT attempt remediation — investigate and escalate only.**

## When to use this skill
- User reports backup failures
- Backup monitoring alert fires
- User asks "why did backup fail on [VM]?"

## Investigation Steps

### Step 1: Get the failure data
**Tool:** `get_backup_status(status="failed", hours=24)`

Collect:
- [ ] Which VMs failed
- [ ] Error type for each (snapshot_locked, disk_full, timeout, network_error)
- [ ] Last successful backup time for each
- [ ] SLA violation status (RPO breached?)
- [ ] Owner team for each VM

**Classify by priority:**
- P1: SLA violated (RPO breached) — production database or critical service
- P2: Failed but SLA not yet violated — still within RPO window
- P3: Non-production or long RPO — can wait

### Step 2: Check the backup infrastructure
**Tool:** `get_backup_status(status="all")` — look at the `summary` field

Investigate:
- [ ] Are failures concentrated on one backup server? (bkp-lva1-01 vs bkp-lva1-02)
  - If YES → backup server issue, not VM issue
- [ ] Are failures concentrated on one error type?
  - All `timeout` → likely storage latency issue, check Step 3
  - All `disk_full` → backup target volume full, check Step 4
  - All `network_error` → backup agent down, check Step 5
  - Mixed errors → multiple independent issues

### Step 3: For timeout errors — check storage latency
**Tool:** `datastore_health(datastore_name="<datastore from backup data>")`
**Tool:** `array_health(array_name="<backing array>")`

Collect:
- [ ] Current write latency vs baseline
- [ ] Is the backing array degraded or rebuilding?
- [ ] SCSI error count in last 24h

**Root cause pattern:** If array is rebuilding → backup I/O competes with rebuild I/O → timeouts are EXPECTED. Do not fix. Wait for rebuild to complete.

### Step 4: For disk_full errors — check backup target
**Tool:** `esxi_vm_status(hostname="<backup server>")`

Collect:
- [ ] Backup target volume capacity and free space
- [ ] Are there stale backups consuming space?
- [ ] Any VMs with oversized or frequent snapshots?

### Step 5: For network_error — check connectivity
**Tool:** `rv_tool_check(hostname="<backup server>", check_type="connectivity")`

Collect:
- [ ] Is backup server reachable?
- [ ] Is the backup agent service running?
- [ ] Network path between VM host and backup server

### Step 6: For snapshot_locked errors — check VM snapshots
**Tool:** `esxi_vm_status(hostname="<VM name>")`
**Tool:** `datastore_health(datastore_name="<datastore>")`

Collect:
- [ ] Current snapshots on the VM (count, age, size)
- [ ] Who created the snapshot and why
- [ ] Is the snapshot preventing new backup snapshots?

### Step 7: Compile escalation report

**Format for human escalation — copy this structure:**

---

**BACKUP FAILURE INVESTIGATION REPORT**

**Time of investigation:** [timestamp]
**Investigator:** Storage Oncall Agent (automated)

**Summary:**
- X VMs with failed backups in last 24 hours
- Y SLA violations (RPO breached)
- Primary error type: [error type]
- Root cause: [confirmed/suspected]

**Failed VMs (by priority):**

| Priority | VM | Error | Last Success | SLA | Owner Team |
|----------|-----|-------|-------------|-----|------------|
| P1 | ... | ... | ... | VIOLATED | ... |
| P2 | ... | ... | ... | OK | ... |

**Telemetry Evidence:**
- Storage array status: [normal/degraded/rebuilding]
- Datastore write latency: [X ms] (baseline: [Y ms])
- Backup target free space: [X GB] / [Y GB]
- Network connectivity: [pass/fail]

**Root Cause Assessment:**
[What broke and why — based on telemetry evidence]

**Recommended Actions (for human to execute):**
1. [Action 1 — specific, with device names and commands]
2. [Action 2]
3. [Action 3]

**Escalation:**
- Page: [team name] — because [reason]
- JIRA: Create ticket in [project] with severity [X]

---

> **IMPORTANT:** This skill investigates and reports. It does NOT execute remediation. The human decides what to fix and when.
```

---

## Worked Examples — How Tools and Skills Work Together

### Example 1: Data Query — "Show me all VMs with failed backups last 24 hours"

This is a **data question**. The agent uses a **tool** to get data. No skill/runbook needed.

```
User: "show me all VMs where backup failed in the last 24 hours"

STEP 1 — Claude API call (reasoning)
  Your app → api.anthropic.com
  Claude thinks: "This is a data query. I need get_backup_status."
  Claude replies: call get_backup_status(status="failed", hours=24)

STEP 2 — Tool runs locally (NO Claude, NO internet)
  Your Python function executes on your machine.
  Returns:
    {
      "backups": [
        {vm: "prod-db-01",   error: "snapshot_locked", sla_violated: true,  owner: "database-infra"},
        {vm: "prod-app-03",  error: "disk_full",       sla_violated: false, owner: "app-platform"},
        {vm: "prod-web-07",  error: "timeout",         sla_violated: true,  owner: "web-infra"},
        {vm: "staging-api-01", error: "network_error",  sla_violated: false, owner: "qa-infra"},
      ],
      "count": 4,
      "sla_violations": 2
    }

STEP 3 — Claude API call (reasoning)
  Your app → api.anthropic.com (sends tool result)
  Claude thinks: "4 VMs failed. 2 SLA violations. Let me present this clearly."
  Claude replies (final answer — no more tool calls):

    "4 VMs had backup failures in the last 24 hours:

     | VM | Error | SLA | Owner |
     |----|-------|-----|-------|
     | prod-db-01 | snapshot locked (14-day-old snapshot) | VIOLATED | database-infra |
     | prod-web-07 | timeout (120ms I/O latency) | VIOLATED | web-infra |
     | prod-app-03 | backup target disk full (98.2%) | OK | app-platform |
     | staging-api-01 | network error (agent down) | OK | qa-infra |

     2 SLA violations need immediate attention (prod-db-01 and prod-web-07)."

DONE. 2 Claude API calls. 1 tool execution. ~5 seconds.
```

**Key point:** This was pure data retrieval. Claude called ONE tool, formatted the results, done. No skill/runbook was involved.

---

### Example 2: Investigation + Escalation — "Backup failed on prod-db-01, investigate and escalate"

This needs a **tool** (to get data) AND a **skill** (to follow investigation procedure). The agent loads the skill/runbook and follows it step by step, collecting telemetry at each step, then compiles an escalation report for a human.

```
User: "backup failed on prod-db-01, investigate and escalate"

STEP 1 — Claude API call
  Claude thinks: "Investigation request. Let me get the failure details first
                  and find the relevant skill."
  Calls: get_backup_status(vm_name="prod-db-01")
  Calls: search_runbooks("backup failure investigation")

STEP 2 — Both tools run locally
  get_backup_status returns:
    {vm: "prod-db-01", error: "snapshot_locked", sla_violated: true,
     error_detail: "snapshot 'pre-upgrade' is 14 days old and locked",
     datastore: "ds-lva1-stor05", owner: "database-infra"}

  search_runbooks returns:
    "Found: backup-failure.md (score 8) — Skill: Backup Failure Investigation"

STEP 3 — Claude API call
  Claude thinks: "Got the failure. Let me load the full skill."
  Calls: load_runbook("backup-failure.md")

STEP 4 — Tool runs locally
  Returns: full skill text with all investigation steps

STEP 5 — Claude API call
  Claude thinks: "Skill says check storage latency and VM snapshots.
                  The error is snapshot_locked on ds-lva1-stor05."
  Calls: datastore_health(datastore_name="ds-lva1-stor05")
  Calls: esxi_vm_status(hostname="prod-db-01")

STEP 6 — Both tools run locally
  datastore_health returns:
    {free_percent: 5.4, write_latency_ms: 45.2, scsi_errors_24h: 8,
     snapshots: [{vm: "prod-db-01", size_gb: 80.5, age_days: 14}]}

  esxi_vm_status returns:
    {memory_usage: 92.1%, datastores: [{latency: 45.2ms}],
     alerts: ["datastore latency elevated"]}

STEP 7 — Claude API call
  Claude thinks: "Skill says check the backing array too."
  Calls: array_health(array_name="stor-lva1-array05")

STEP 8 — Tool runs locally
  Returns: {status: "degraded", failed_disks: 2, rebuilding: 1,
            rebuild_percent: 43.2, rebuild_eta_hours: 6.5}

STEP 9 — Claude API call (FINAL — compiles escalation report)
  Claude thinks: "I have all the telemetry. Following the skill's
                  escalation report format..."
  Returns:

    BACKUP FAILURE INVESTIGATION REPORT

    Time: 2026-04-12T09:45:00Z
    Investigator: Storage Oncall Agent (automated)

    Summary:
    - prod-db-01 backup failed due to locked snapshot
    - SLA VIOLATED — RPO 24h breached (last success: Apr 10)
    - Contributing factor: storage array degraded with active rebuild

    Telemetry Evidence:
    - Snapshot: "pre-upgrade" — 14 days old, 80.5 GB, LOCKED
    - Storage array: stor-lva1-array05 DEGRADED
      - 2 failed disks, 1 rebuilding (43.2%, ETA 6.5h)
    - Datastore: ds-lva1-stor05 — write latency 45.2ms (baseline 12ms)
    - SCSI errors: 8 in last 24h
    - Host memory: 92.1% (elevated)

    Root Cause:
    14-day-old locked snapshot is preventing new backup snapshots.
    The snapshot was likely created pre-upgrade and never cleaned up.
    Storage latency is elevated due to array rebuild, which would have
    caused timeout even without the snapshot lock.

    Recommended Actions (for human):
    1. Delete stale snapshot "pre-upgrade" on prod-db-01 (14 days old, 80.5 GB)
       — Verify with database-infra team first, they created it
    2. Retry backup after snapshot deletion
    3. Wait for array rebuild to complete (ETA 6.5h) before expecting
       normal backup performance
    4. Clean up any other stale snapshots on ds-lva1-stor05
       (datastore is at 5.4% free)

    Escalation:
    - Page: database-infra — SLA violated on prod-db-01, need snapshot cleanup approval
    - JIRA: Create STOR ticket, severity P1, assign to storage-infra

    NOTE: This report was generated by automated investigation.
    No remediation was attempted. Human review required before action.

DONE. 5 Claude API calls. 6 tool executions. ~20 seconds.
```

**Key point:** The skill (runbook) told Claude WHAT to investigate and in WHAT ORDER. The tools gave Claude the telemetry DATA at each step. Claude compiled everything into a human-readable escalation report. **No remediation was attempted — investigate and escalate only.**

---

### The Difference — Tool vs Skill:

```
TOOL = gets data         →  "What's happening?"
       Python function        get_backup_status() → returns JSON data
       Runs on your machine   Claude calls it, reads result

SKILL = procedure        →  "What should I do about it?"
        Markdown file         backup-failure.md → step-by-step investigation
        Loaded by Claude      Claude reads it, FOLLOWS the steps
```

Claude uses BOTH together: call tools to get data, follow skills for procedure.

---

## 8. Running the Application <a name="8-running"></a>

```bash
# Install dependencies
pip install -e ".[dev]"

# Set your API key
echo "ANTHROPIC_API_KEY=sk-ant-api03-YOUR_KEY" > .env

# Run the app
streamlit run app/main.py

# Open http://localhost:8501
```

### Test queries to try:

1. **"Show me all active storage incidents"**
   - Agent calls `get_storage_incidents` → lists all active incidents

2. **"Triage incident STOR-2001"**
   - Agent calls incidents → array_health → disk_failures → esxi_vm_status → datastore_health → search_runbooks → load_runbook → final triage report

3. **"Check MDS switch lva1-mds01 — ports seem to be flapping"**
   - Agent calls mds_port_status → search_runbooks → load_runbook → fabric_topology → triage report

4. **"What's the blast radius if stor-lva1-array05 goes completely down?"**
   - Agent calls array_health → datastore_health → esxi_vm_status → fabric_topology → blast radius analysis

5. **"Run a full RV tool check on lva1-mds01"**
   - Agent calls rv_tool_check → interprets results → recommendations

6. **"Show me all VMs with failed backups in the last 24 hours"** (Example 1 — data query, tool only)
   - Agent calls `get_backup_status(status="failed", hours=24)` → formats results → done. No skill needed.

7. **"Backup failed on prod-db-01 — investigate and escalate"** (Example 2 — investigation, tool + skill)
   - Agent calls `get_backup_status` → `search_runbooks` → `load_runbook("backup-failure.md")` → follows skill steps → `datastore_health` → `esxi_vm_status` → `array_health` → compiles escalation report for human. No remediation attempted.

---

## 9. Testing <a name="9-testing"></a>

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_tools.py -v

# Run with output
pytest tests/test_tools.py -v -s
```

---

## 10. Graduating to Real APIs <a name="10-graduating"></a>

When you're ready to replace synthetic data with real infrastructure:

### For each tool, the change is simple:

**Before (synthetic):**
```python
@tool
def mds_port_status(hostname: str) -> dict:
    return SYNTHETIC_DATA[hostname]  # hardcoded dict
```

**After (real API):**
```python
import httpx

@tool
def mds_port_status(hostname: str) -> dict:
    response = httpx.get(f"https://your-mds-api.internal/switches/{hostname}/ports")
    response.raise_for_status()
    return response.json()
```

### Integration priority:
1. **Incident API** — real incidents from your alerting system (PagerDuty, OpsGenie, etc.)
2. **MDS NX-API** — real port/zone data via Cisco NX-API (JSON-RPC over HTTP)
3. **vCenter API** — real VM/datastore data via vSphere REST API
4. **Storage array API** — vendor-specific (Dell PowerStore, NetApp ONTAP, Pure Storage)
5. **RV Tool** — whatever your internal RV tool exposes

### Adding new tools:
1. Create a new file in `tools/`
2. Write a `@tool` decorated function
3. Add it to `ALL_TOOLS` in `tools/__init__.py`
4. The agent discovers it automatically — no other changes needed

### Adding middleware (when tool count grows past 15):
Copy the SmartRoutingMiddleware pattern from LIPA — classify query as triage/analytics, filter tools to relevant subset, switch model for different query types.

---

## Quick Reference

| Component | Technology | Purpose |
|-----------|-----------|---------|
| LLM | Claude (Anthropic API) | The brain — decides what to do |
| Agent Framework | LangGraph | Manages the tool loop |
| LLM Wrapper | LangChain Anthropic | Translates between LangGraph and Claude API |
| Frontend | Streamlit | Chat UI |
| Backend | Built into Streamlit | No separate server needed for POC |
| Database | SQLite (via MemorySaver) | Conversation history |
| Tools | Plain Python functions | Your infrastructure queries |
| Runbooks | Markdown files | Standard procedures |

**Total external dependencies: 1 (Anthropic API key)**

That's it. Hand this to Claude and say "Build this." Everything is here.

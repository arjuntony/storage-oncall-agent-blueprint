# MDS 9710 Interface Triage Agent — Build Blueprint v1

> **What this is:** A complete specification for building an AI agent that triages MDS 9710 Fibre Channel interface issues. Hand this to Claude and say: **"Build this."**
>
> **Scope:** MDS 9710 interface issues ONLY — flapping, CRC errors, link failures, credit loss, ISL disruption.
>
> **What you need:** Python 3.11+, an Anthropic API key (`sk-ant-...`), and a terminal.
>
> **What you get:** A working chat agent that follows a structured 10-step investigation skill, collects evidence from live APIs + syslog + offline show-tech files, and produces a human-readable escalation report.

---

## Table of Contents

1. [How It Works](#1-how-it-works)
2. [Data Collection Strategy — No Live Show-Tech](#2-data-collection)
3. [Architecture](#3-architecture)
4. [Project Structure](#4-project-structure)
5. [Dependencies](#5-dependencies)
6. [Build Instructions](#6-build-instructions)
7. [Complete Code — Every File](#7-complete-code)
8. [Skills — Investigation Procedures](#8-skills)
9. [Worked Example — Full MDS Interface Triage](#9-worked-example)
10. [Running It](#10-running)
11. [Tests](#11-tests)
12. [Graduating to Real APIs](#12-graduating)

---

## 1. How It Works <a name="1-how-it-works"></a>

### The Core Loop

```
User: "fc1/3 on lva1-mds01 is flapping, 47 flaps and CRC errors"

Claude thinks: "Interface issue. I need the investigation skill."
  → calls load_skill("mds-interface-issues.md")

Claude reads the skill, follows it step by step:

  Step 1: → calls get_interface_status("lva1-mds01")
          → calls get_flogi_database("lva1-mds01")
          Result: fc1/3 is F-port, storage array, VSAN 100, FLOGI missing

  Step 3: → calls get_interface_detail("lva1-mds01", "fc1/3")
          Result: status=down, reason=link_failure

  Step 4: → calls get_interface_counters("lva1-mds01", "fc1/3")
          → calls get_syslog_entries("lva1-mds01", "fc1/3", 1)
          Result: 47 link failures, 892 CRC, 3 signal losses

  Step 5: → same counters — CRC + signal loss = physical layer issue

  Step 6: → calls get_flogi_database("lva1-mds01")
          Result: fc1/3 FLOGI missing — device not in fabric

  Step 7: → calls get_vsan_status("lva1-mds01")
          Result: VSAN 100 active, zone member missing

  Step 8: → calls get_device_health("lva1-mds01")
          Result: CPU 35%, memory 62%, all modules OK

  Step 9: → calls load_show_tech("lva1-mds01") → get section list
          → calls load_show_tech("lva1-mds01", "interfaces") → confirm CRC trend

  Step 10: → compiles HANDOFF report with all evidence

Claude returns: structured escalation report → human takes action
```

Each "Claude thinks" is a separate API call to `https://api.anthropic.com/v1/messages`. LangGraph manages the loop.

### Two Things Alternate

```
CLAUDE (internet)          YOUR TOOLS (local)
─────────────────          ─────────────────
Reads skill, decides    →  get_interface_status()  → returns data
what tool to call           runs on YOUR machine

Reads tool result,      →  get_interface_counters() → returns data
decides next step           runs on YOUR machine

Reads all evidence,     →  (no tool call)
writes final report         streams answer to user
```

Claude never touches your switches. Your Python functions do. Claude just decides which tool to call and what to do with the results.

---

## 2. Data Collection Strategy — No Live Show-Tech <a name="2-data-collection"></a>

> Running `show tech-support` live on an MDS 9710 during an incident is slow (5-10 min), generates 10,000+ lines, and spikes CPU. **Don't do it.**

### Three Data Tiers

```
┌──────────────────────────────────────────────────────────────────┐
│  TIER 1: LIVE — NX-API (REST/JSON)                               │
│                                                                   │
│  MDS 9710 has NX-API built in. HTTP call → JSON response.        │
│  No SSH. No CLI parsing. No CPU spike on the switch.             │
│                                                                   │
│  What you get:                                                    │
│  • Interface status + counters    • FLOGI database               │
│  • FSPF neighbors                 • VSAN status                  │
│  • Zone database + active zoneset • Port-channel summary         │
│  • Module status                  • CPU/memory/temperature       │
│                                                                   │
│  How: HTTP POST to https://<switch>/ins with NX-API payload      │
│  Speed: < 1 second per query                                     │
│  Impact: Zero — read-only API call                               │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  TIER 2: STREAMING — Syslog                                      │
│                                                                   │
│  MDS sends syslog messages automatically on every event:         │
│  interface flap, link failure, zone change, FSPF reconvergence.  │
│                                                                   │
│  Already flowing to your syslog server. Just read it.            │
│                                                                   │
│  What you get:                                                    │
│  • Timestamped flap events        • Link failure messages        │
│  • Zone merge events              • FSPF topology changes        │
│  • errDisable triggers            • Hardware alerts              │
│                                                                   │
│  How: Query syslog server (Splunk, ELK, rsyslog files)           │
│  Speed: < 1 second                                               │
│  Impact: Zero — reading logs, not touching the switch            │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  TIER 3: OFFLINE — Show-Tech Files on Disk                       │
│                                                                   │
│  For deep data when live APIs don't have enough history.         │
│  NOT run live. Collected via scheduled cron job or on alert.     │
│                                                                   │
│  Collection options:                                              │
│  • Cron job every 4-6 hours → SSH → show tech → save to disk    │
│  • Alert trigger → auto-collect once → save to disk              │
│  • Manual collection after incident → save to disk               │
│                                                                   │
│  Files stored at: /data/show-tech/<hostname>/<timestamp>.txt     │
│                                                                   │
│  TWO-STEP LOADING (critical — files are 10K+ lines):            │
│  1. load_show_tech(hostname) → returns SECTION LIST only         │
│  2. load_show_tech(hostname, "interfaces") → returns ONE section │
│                                                                   │
│  Never dump the entire file into Claude. Load by section.        │
└──────────────────────────────────────────────────────────────────┘
```

### When Each Tier Is Used

| Investigation Step | Primary Source | Fallback Source |
|---|---|---|
| Step 1: Port type + topology | **LIVE** — NX-API interface status | OFFLINE — show-tech `interfaces` |
| Step 2: Port-channel check | **LIVE** — NX-API port-channel | OFFLINE — show-tech `port-channel` |
| Step 3: Current state | **LIVE** — NX-API interface detail | OFFLINE — show-tech `interfaces` |
| Step 4: Flap history | **LIVE** — NX-API counters + **STREAMING** — syslog | OFFLINE — show-tech `logging` |
| Step 5: Error counters | **LIVE** — NX-API counters | OFFLINE — show-tech `interfaces` |
| Step 6: FLOGI/FCNS | **LIVE** — NX-API FLOGI database | OFFLINE — show-tech `flogi` |
| Step 7: VSAN + zones | **LIVE** — NX-API VSAN/zone status | OFFLINE — show-tech `vsan`, `zoneset` |
| Step 8: Device health | **LIVE** — NX-API system health | OFFLINE — show-tech `hardware` |
| Step 9: Fill gaps | **OFFLINE** — show-tech (any section with gaps) | — |

### For the POC

All three tiers use **synthetic data** (Python dicts and text files). The tool interface is identical — when you graduate to real APIs, you change the inside of the function, not the function signature.

```python
# POC — synthetic data
@tool
def get_interface_status(hostname: str) -> dict:
    return SYNTHETIC_DATA[hostname]

# Production — real NX-API call
@tool
def get_interface_status(hostname: str) -> dict:
    response = httpx.post(f"https://{hostname}/ins", json=nxapi_payload("show interface brief"))
    return parse_nxapi_response(response.json())
```

Same tool name. Same parameters. Same return shape. Agent code doesn't change.

---

## 3. Architecture <a name="3-architecture"></a>

```
┌──────────────────────────────────────────────────────────────────┐
│                          YOUR MACHINE                             │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ STREAMLIT CHAT UI (:8501)                                  │  │
│  │  User types: "triage fc1/3 on lva1-mds01"                 │  │
│  └───────────────────────┬────────────────────────────────────┘  │
│                          │                                        │
│  ┌───────────────────────▼────────────────────────────────────┐  │
│  │ LANGGRAPH REACT AGENT                                      │  │
│  │                                                            │  │
│  │  ┌──────────┐         ┌─────────────┐                      │  │
│  │  │ CLAUDE   │──call──▶│ EXECUTE     │                      │  │
│  │  │ (API)    │  tool   │ TOOL        │                      │  │
│  │  │          │◀─result─│ (Python fn) │                      │  │
│  │  └────┬─────┘         └─────────────┘                      │  │
│  │       │ no more tools = final answer                       │  │
│  │       ▼                                                    │  │
│  │  Stream to user                                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│         ┌────────────┬─────────────┬──────────────┐              │
│         ▼            ▼             ▼              ▼              │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐  ┌───────────┐        │
│  │ MDS TOOLS │ │ SYSLOG   │ │ SHOW-TECH│  │ SKILLS    │        │
│  │ (NX-API)  │ │ TOOL     │ │ LOADER   │  │ (search + │        │
│  │           │ │          │ │ (2-step) │  │  load .md)│        │
│  │ LIVE data │ │ STREAMING│ │ OFFLINE  │  │ PROCEDURE │        │
│  └───────────┘ └──────────┘ └──────────┘  └───────────┘        │
│                                                                   │
└───────────────────────────┬───────────────────────────────────────┘
                            │ HTTPS (outbound only)
                            ▼
                 ┌───────────────────────┐
                 │  api.anthropic.com    │
                 │  (Claude API)         │
                 │                       │
                 │  ONLY external dep    │
                 └───────────────────────┘
```

---

## 4. Project Structure <a name="4-project-structure"></a>

```
mds-interface-agent/
│
├── .env                              # ANTHROPIC_API_KEY=sk-ant-...
├── pyproject.toml                    # Python dependencies
│
├── app/
│   ├── __init__.py
│   ├── config.py                     # Settings (model, API key)
│   ├── agent.py                      # LangGraph ReAct agent
│   └── main.py                       # Streamlit chat UI
│
├── tools/
│   ├── __init__.py                   # Exports ALL_TOOLS list
│   ├── mds_live.py                   # LIVE: NX-API tools (interface, counters, FLOGI, FSPF, VSAN, zones, health)
│   ├── syslog.py                     # STREAMING: syslog query tool
│   ├── show_tech.py                  # OFFLINE: show-tech two-step loader
│   └── skills.py                     # search_skills, load_skill (reads .md files)
│
├── skills/                           # Investigation procedures (markdown)
│   ├── mds-interface-issues.md       # 10-step interface triage (THE main skill)
│   └── mds-health-check.md           # Device health assessment (called from Step 8)
│
├── data/                             # Synthetic show-tech files (POC only)
│   └── show-tech/
│       └── lva1-mds01/
│           └── latest.txt            # Simulated show-tech output
│
└── tests/
    ├── __init__.py
    └── test_tools.py                 # Unit tests for all tools
```

---

## 5. Dependencies <a name="5-dependencies"></a>

### pyproject.toml

```toml
[project]
name = "mds-interface-agent"
version = "1.0.0"
description = "AI agent for MDS 9710 Fibre Channel interface triage"
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

## 6. Build Instructions <a name="6-build-instructions"></a>

### For Claude (the AI building this):

1. Create the project directory and all subdirectories
2. Write `pyproject.toml` and `.env`
3. Write all tool files in `tools/` — every tool is a `@tool` decorated Python function
4. Write all skill markdown files in `skills/`
5. Write synthetic show-tech data in `data/show-tech/`
6. Write `app/config.py`, `app/agent.py`, `app/main.py`
7. Write tests in `tests/`
8. Verify: `pip install -e .` then `streamlit run app/main.py`

### For the human:

```bash
mkdir mds-interface-agent && cd mds-interface-agent

# Have Claude build everything (give it this document)

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

echo "ANTHROPIC_API_KEY=sk-ant-api03-YOUR_KEY" > .env

streamlit run app/main.py
# Open http://localhost:8501
```

---

## 7. Complete Code — Every File <a name="7-complete-code"></a>

### `app/__init__.py`

```python
# MDS Interface Triage Agent
```

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

from tools.mds_live import (
    get_interface_status,
    get_interface_detail,
    get_interface_counters,
    get_flogi_database,
    get_fcns_database,
    get_fspf_neighbors,
    get_port_channel_summary,
    get_vsan_status,
    get_zone_status,
    get_device_health,
    get_module_status,
)
from tools.syslog import get_syslog_entries
from tools.show_tech import load_show_tech
from tools.skills import search_skills, load_skill

ALL_TOOLS = [
    # ── LIVE: MDS NX-API tools ──
    get_interface_status,       # All ports — overview
    get_interface_detail,       # Single port — deep status
    get_interface_counters,     # Error counters for a port
    get_flogi_database,         # Fabric Login entries
    get_fcns_database,          # FC Name Server entries
    get_fspf_neighbors,         # FC routing neighbors
    get_port_channel_summary,   # ISL port-channel bundles
    get_vsan_status,            # VSAN membership + state
    get_zone_status,            # Active zoneset + members
    get_device_health,          # CPU, memory, PSU, fans, temp
    get_module_status,          # Linecard/supervisor modules
    # ── STREAMING: Syslog ──
    get_syslog_entries,         # Timestamped log events
    # ── OFFLINE: Show-tech files ──
    load_show_tech,             # Two-step: list sections, then load one
    # ── SKILLS: Investigation procedures ──
    search_skills,              # Find relevant skill by keyword
    load_skill,                 # Load full skill content
]
```

### `tools/mds_live.py`

```python
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
# SYNTHETIC DATA — replace with NX-API calls in production
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
        # fc1/3 — NO ENTRY (device not logged in — port is down)
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
        # fc1/3 device NOT in FCNS — lost from fabric
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
            "active_members": 2,
            "total_members": 2,
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
        "cpu_1min": 35.2,
        "cpu_5min": 28.4,
        "memory_total_mb": 32768,
        "memory_used_mb": 20316,
        "memory_used_percent": 62.0,
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
        "temperature": {
            "inlet": 28.5,
            "sup1": 42.0,
            "sup2": 41.5,
            "module1": 48.2,
        },
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
    Use this for an overview of all ports. For a single port deep dive, use get_interface_detail.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)

    Returns:
        All interfaces with status, port mode (F/E/TE), speed, VSAN, and connected device.
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
        "hostname": hostname,
        "model": "Cisco MDS 9710",
        "firmware": DEVICE_HEALTH.get(hostname, {}).get("firmware", "unknown"),
        "interfaces": interfaces,
        "summary": {"total": len(interfaces), "up": ports_up, "down": ports_down},
        "alerts": alerts,
    }


@tool
def get_interface_detail(hostname: str, interface: str) -> dict:
    """Get detailed status for a SINGLE interface — includes port mode, state, reason, speed, VSAN.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        interface: Interface name (e.g. fc1/3)

    Returns:
        Detailed interface status.
    """
    interfaces = SWITCH_INTERFACES.get(hostname, [])
    for iface in interfaces:
        if iface["interface"] == interface:
            return {"hostname": hostname, "interface": iface}
    return {"error": f"Interface '{interface}' not found on '{hostname}'"}


@tool
def get_interface_counters(hostname: str, interface: str) -> dict:
    """Get error counters for a specific interface — CRC, link failures, signal loss, credits.

    These are the key counters for physical layer triage:
    - crc_errors: Bad frames (SFP, cable, dirty connector)
    - link_failures: Physical link drop events
    - sync_losses: Optical sync lost
    - signal_losses: Optical signal lost (fiber or SFP)
    - credit_loss: Remote device not returning B2B credits (slow-drain)
    - timeout_discards: Frames discarded due to credit timeout

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        interface: Interface name (e.g. fc1/3)

    Returns:
        All error counters for the interface.
    """
    host_counters = INTERFACE_COUNTERS.get(hostname, {})
    counters = host_counters.get(interface)
    if not counters:
        return {"error": f"No counter data for '{interface}' on '{hostname}'"}

    # Classify severity based on counters
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

    return {
        "hostname": hostname,
        "interface": interface,
        "counters": counters,
        "severity": severity,
        "findings": findings,
    }


@tool
def get_flogi_database(hostname: str) -> dict:
    """Get Fabric Login (FLOGI) database — shows which devices are logged into the fabric.
    If a device is missing from FLOGI, it is NOT reachable via the SAN fabric.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)

    Returns:
        FLOGI entries with WWPN, FCID, VSAN, and interface for each logged-in device.
    """
    entries = FLOGI_DATABASE.get(hostname, [])
    if not entries:
        return {"error": f"No FLOGI data for '{hostname}'"}

    return {
        "hostname": hostname,
        "flogi_count": len(entries),
        "entries": entries,
        "note": "Devices NOT in this list are NOT logged into the fabric (port down or device offline)",
    }


@tool
def get_fcns_database(hostname: str) -> dict:
    """Get FC Name Server (FCNS) database — shows registered devices in the fabric name service.
    If FLOGI exists but FCNS doesn't, the device logged in but failed name registration (zone issue).

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)

    Returns:
        FCNS entries with WWPN, FCID, device type (initiator/target), and FC4 type.
    """
    entries = FCNS_DATABASE.get(hostname, [])
    if not entries:
        return {"error": f"No FCNS data for '{hostname}'"}

    initiators = sum(1 for e in entries if e["type"] == "initiator")
    targets = sum(1 for e in entries if e["type"] == "target")

    return {
        "hostname": hostname,
        "fcns_count": len(entries),
        "initiators": initiators,
        "targets": targets,
        "entries": entries,
    }


@tool
def get_fspf_neighbors(hostname: str) -> dict:
    """Get FSPF (FC Shortest Path First) neighbors — shows fabric routing adjacency.
    FSPF is the FC equivalent of OSPF. Neighbors should be in FULL state.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)

    Returns:
        FSPF neighbor list with state (FULL/INIT), cost, and connected switch info.
    """
    neighbors = FSPF_NEIGHBORS.get(hostname, [])
    if not neighbors:
        return {"error": f"No FSPF data for '{hostname}'"}

    alerts = []
    for n in neighbors:
        if n["state"] != "FULL":
            alerts.append(f"Neighbor {n['neighbor_switch']} in state {n['state']} — NOT FULL")

    return {
        "hostname": hostname,
        "neighbor_count": len(neighbors),
        "neighbors": neighbors,
        "all_full": all(n["state"] == "FULL" for n in neighbors),
        "alerts": alerts,
    }


@tool
def get_port_channel_summary(hostname: str) -> dict:
    """Get port-channel (ISL bundle) summary — shows ISL redundancy.
    If a port-channel has only 1 member left, the next failure causes fabric partition.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)

    Returns:
        Port-channel list with member status, active count, and peer switch.
    """
    pcs = PORT_CHANNELS.get(hostname, [])
    if not pcs:
        return {"error": f"No port-channel data for '{hostname}'"}

    alerts = []
    for pc in pcs:
        if pc["active_members"] < pc["total_members"]:
            alerts.append(
                f"{pc['port_channel']}: only {pc['active_members']}/{pc['total_members']} members active"
            )
        if pc["active_members"] == 1:
            alerts.append(f"{pc['port_channel']}: CRITICAL — single member, next failure = fabric partition")

    return {
        "hostname": hostname,
        "port_channels": pcs,
        "alerts": alerts,
    }


@tool
def get_vsan_status(hostname: str) -> dict:
    """Get VSAN status — shows virtual SAN state, member ports, and active zoneset.
    A suspended VSAN means all devices in that VSAN lose SAN connectivity.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)

    Returns:
        VSAN list with state (active/suspended), member ports, and zoneset info.
    """
    vsans = VSAN_STATUS.get(hostname, [])
    if not vsans:
        return {"error": f"No VSAN data for '{hostname}'"}

    alerts = []
    for v in vsans:
        if v["state"] != "active":
            alerts.append(f"VSAN {v['vsan_id']} ({v['name']}): {v['state']} — CRITICAL")

    return {
        "hostname": hostname,
        "vsans": vsans,
        "alerts": alerts,
    }


@tool
def get_zone_status(hostname: str, vsan: int = 100) -> dict:
    """Get zone database status for a VSAN — active zoneset, zone members, login status.
    Zones control which initiators can see which targets. A missing member means broken path.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        vsan: VSAN ID to check (default 100)

    Returns:
        Active zoneset with all zones, members, and login status.
    """
    host_zones = ZONE_STATUS.get(hostname, {})
    zone_data = host_zones.get(vsan)
    if not zone_data:
        return {"error": f"No zone data for VSAN {vsan} on '{hostname}'"}

    return {"hostname": hostname, "vsan": vsan, **zone_data}


@tool
def get_device_health(hostname: str) -> dict:
    """Get MDS switch health — CPU, memory, power supplies, fans, temperature.
    Use this to determine if the switch itself is healthy or if the issue is device-level.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)

    Returns:
        Device health with CPU, memory, PSU, fan, and temperature status.
    """
    health = DEVICE_HEALTH.get(hostname)
    if not health:
        return {"error": f"No health data for '{hostname}'"}

    # Classify
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
    """Get linecard and supervisor module status. Failed modules mean ports on that card are down.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)

    Returns:
        Module list with slot, type, status, and port counts.
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

    return {
        "hostname": hostname,
        "modules": modules,
        "alerts": alerts,
    }
```

### `tools/syslog.py`

```python
"""Syslog query tool — synthetic data for POC.

In production, this queries your syslog server (Splunk, ELK, rsyslog, etc.)
via API or file read. The MDS sends syslog automatically on every event.
"""

from langchain_core.tools import tool


SYNTHETIC_SYSLOG = {
    "lva1-mds01": [
        {"timestamp": "2026-04-12T08:15:00Z", "facility": "PORT",
         "severity": "WARNING", "message": "fc1/3: Interface fc1/3 is down (link_failure)"},
        {"timestamp": "2026-04-12T08:14:58Z", "facility": "PORT",
         "severity": "INFO", "message": "fc1/3: Interface fc1/3 is up"},
        {"timestamp": "2026-04-12T08:14:45Z", "facility": "PORT",
         "severity": "WARNING", "message": "fc1/3: Interface fc1/3 is down (link_failure)"},
        {"timestamp": "2026-04-12T08:14:42Z", "facility": "PORT",
         "severity": "INFO", "message": "fc1/3: Interface fc1/3 is up"},
        {"timestamp": "2026-04-12T08:14:30Z", "facility": "PORT",
         "severity": "WARNING", "message": "fc1/3: Interface fc1/3 is down (link_failure)"},
        {"timestamp": "2026-04-12T08:14:10Z", "facility": "ETH_PORT_CHANNEL",
         "severity": "INFO", "message": "port-channel1: member fc1/47 is up"},
        {"timestamp": "2026-04-12T08:10:00Z", "facility": "PORT",
         "severity": "WARNING", "message": "fc1/3: Interface fc1/3 is down (link_failure)"},
        {"timestamp": "2026-04-12T08:09:55Z", "facility": "PORT",
         "severity": "INFO", "message": "fc1/3: Interface fc1/3 is up"},
        {"timestamp": "2026-04-12T08:05:00Z", "facility": "ZONE",
         "severity": "INFO", "message": "VSAN 100: Full zoneset activation successful"},
        {"timestamp": "2026-04-12T07:55:00Z", "facility": "PORT",
         "severity": "WARNING", "message": "fc1/3: Interface fc1/3 is down (link_failure)"},
        {"timestamp": "2026-04-12T07:54:50Z", "facility": "PORT",
         "severity": "INFO", "message": "fc1/3: Interface fc1/3 is up"},
        {"timestamp": "2026-04-12T07:50:00Z", "facility": "PORT",
         "severity": "WARNING", "message": "fc1/3: Interface fc1/3 is down (link_failure)"},
        {"timestamp": "2026-04-12T07:30:00Z", "facility": "PORT",
         "severity": "ERR",
         "message": "fc1/3: CRC error threshold exceeded — 892 errors in last interval"},
        {"timestamp": "2026-04-12T07:00:00Z", "facility": "PORT",
         "severity": "WARNING",
         "message": "fc1/3: Link failure count 47 in last 24 hours — physical layer investigation recommended"},
        {"timestamp": "2026-04-12T06:30:00Z", "facility": "FSPF",
         "severity": "INFO", "message": "VSAN 100: FSPF neighbor lva1-mds02 is FULL"},
    ],
}


@tool
def get_syslog_entries(hostname: str, keyword: str = "", hours: int = 1) -> dict:
    """Get syslog entries for an MDS switch — filtered by keyword and time window.
    MDS sends syslog automatically: interface flaps, link failures, zone changes, FSPF events.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        keyword: Filter by keyword in message (e.g. fc1/3, link_failure, FSPF). Empty = all.
        hours: Lookback window in hours (default 1)

    Returns:
        Matching syslog entries with timestamp, facility, severity, and message.
    """
    entries = SYNTHETIC_SYSLOG.get(hostname, [])
    if not entries:
        return {"error": f"No syslog data for '{hostname}'"}

    if keyword:
        keyword_lower = keyword.lower()
        entries = [e for e in entries if keyword_lower in e["message"].lower()]

    return {
        "hostname": hostname,
        "filter": {"keyword": keyword or "(none)", "hours": hours},
        "entries": entries,
        "count": len(entries),
    }
```

### `tools/show_tech.py`

```python
"""Show-tech-support loader — reads pre-collected files from disk.

NOT run live on the switch. Files are collected via:
  - Scheduled cron job (every 4-6 hours)
  - Alert-triggered collection
  - Manual collection after incidents

Files stored at: data/show-tech/<hostname>/latest.txt

TWO-STEP LOADING:
  1. load_show_tech(hostname) → returns section list only (small)
  2. load_show_tech(hostname, "interfaces") → returns one section (targeted)

Never dump 10,000+ lines into Claude. Always load by section.
"""

from pathlib import Path
from langchain_core.tools import tool

SHOW_TECH_PATH = Path(__file__).parent.parent / "data" / "show-tech"

# Synthetic show-tech sections for POC
SYNTHETIC_SHOW_TECH = {
    "lva1-mds01": {
        "interfaces": """
`show interface fc1/1`
fc1/1 is up
  Hardware is Fibre Channel, SFP is short wave laser
  Port WWN is 20:01:00:0d:ec:6a:30:01
  Admin port mode is F, trunk mode is off
  Port mode is F, FCID is 0x610001
  Port vsan is 100
  Speed is 32 Gbps
  Transmit B2B Credit is 16, Receive B2B Credit is 16
  5 minutes input rate 512000 bits/sec, 8000 frames/sec
  5 minutes output rate 640000 bits/sec, 10000 frames/sec
    48523019 frames input, 32105890234 bytes
    51203847 frames output, 34201290112 bytes
    0 CRC errors, 0 unknown class, 0 too long, 0 too short
    0 input errors, 0 output errors
    0 link failures, 0 sync losses, 0 signal losses

`show interface fc1/3`
fc1/3 is down (link_failure)
  Hardware is Fibre Channel, SFP is short wave laser
  Port WWN is 20:03:00:0d:ec:6a:30:01
  Admin port mode is F, trunk mode is off
  Port mode is F
  Port vsan is 100
  Speed is auto
  Last clearing of counters: never
  Last link flapped at 2026-04-12T08:15:00Z
    0 frames input, 0 bytes
    0 frames output, 0 bytes
    892 CRC errors, 0 unknown class, 0 too long, 0 too short
    938 input errors, 0 output errors
    47 link failures, 15 sync losses, 3 signal losses
    23 invalid transmission words, 8 encoding errors
  SFP info:
    Vendor: CISCO-FINISAR
    Part: FTLF8532P4BCV-C1
    Serial: FNS234100AB
    Temperature: 52.3C (threshold: 70C)
    Tx Power: -3.2 dBm (threshold: -8.0 dBm)
    Rx Power: -14.8 dBm (threshold: -15.0 dBm) *** NEAR THRESHOLD ***
    Voltage: 3.28V
""",
        "flogi": """
`show flogi database vsan 100`
-----------------------------------------------------------------------------------
INTERFACE  VSAN  FCID       PORT NAME               NODE NAME
-----------------------------------------------------------------------------------
fc1/1      100   0x610001   21:00:00:24:ff:4a:12:01 20:00:00:24:ff:4a:12:00
fc1/2      100   0x610002   21:00:00:24:ff:4a:12:02 20:00:00:24:ff:4a:12:00
fc1/4      100   0x610004   21:00:00:24:ff:4a:12:04 20:00:00:24:ff:4a:12:00
fc1/5      100   0x610005   50:00:09:72:08:60:2a:00 50:00:09:72:08:60:2a:ff
fc1/6      100   0x610006   50:00:09:72:08:60:2a:01 50:00:09:72:08:60:2a:fe
fc1/7      100   0x610007   50:00:09:72:08:60:2a:02 50:00:09:72:08:60:2a:fd

Total number of flogi entries = 6

NOTE: fc1/3 has NO FLOGI entry — device is not logged into the fabric.
""",
        "fcns": """
`show fcns database vsan 100`
VSAN 100:
---------------------------------------------------------------------------
FCID       TYPE       PORT WWN                NODE WWN                ALIAS
---------------------------------------------------------------------------
0x610001   target     21:00:00:24:ff:4a:12:01 20:00:00:24:ff:4a:12:00 stor-lva1-array05-ct0-fc0
0x610002   target     21:00:00:24:ff:4a:12:02 20:00:00:24:ff:4a:12:00 stor-lva1-array05-ct0-fc1
0x610004   target     21:00:00:24:ff:4a:12:04 20:00:00:24:ff:4a:12:00 stor-lva1-array05-ct1-fc1
0x610005   initiator  50:00:09:72:08:60:2a:00 50:00:09:72:08:60:2a:ff esxi-lva1-host10-hba0
0x610006   initiator  50:00:09:72:08:60:2a:01 50:00:09:72:08:60:2a:fe esxi-lva1-host11-hba0
0x610007   initiator  50:00:09:72:08:60:2a:02 50:00:09:72:08:60:2a:fd esxi-lva1-host12-hba0

Total entries = 6

NOTE: WWPN 21:00:00:24:ff:4a:12:03 (stor-lva1-array05-ct1-fc0) is MISSING from FCNS.
This device was on fc1/3 which is currently down.
""",
        "vsan": """
`show vsan`
vsan 1 information
  name: default, state: active
  interoperability mode: default
  loadbalancing: src-id/dst-id/oxid

vsan 100 information
  name: prod-san-a, state: active
  interoperability mode: default
  loadbalancing: src-id/dst-id/oxid
  member ports: fc1/1-7, fc1/47-48 (via trunk)
""",
        "zoneset": """
`show zoneset active vsan 100`
zoneset name zs_prod_lva1 vsan 100
  zone name z_array05ct0_host10 vsan 100
    pwwn 21:00:00:24:ff:4a:12:01 [stor-lva1-array05-ct0-fc0] ** logged in **
    pwwn 50:00:09:72:08:60:2a:00 [esxi-lva1-host10-hba0] ** logged in **

  zone name z_array05ct0_host11 vsan 100
    pwwn 21:00:00:24:ff:4a:12:02 [stor-lva1-array05-ct0-fc1] ** logged in **
    pwwn 50:00:09:72:08:60:2a:01 [esxi-lva1-host11-hba0] ** logged in **

  zone name z_array05ct1_host12 vsan 100
    pwwn 21:00:00:24:ff:4a:12:03 [stor-lva1-array05-ct1-fc0]  <<<< NOT LOGGED IN >>>>
    pwwn 50:00:09:72:08:60:2a:02 [esxi-lva1-host12-hba0] ** logged in **

  zone name z_array05ct1_host10 vsan 100
    pwwn 21:00:00:24:ff:4a:12:04 [stor-lva1-array05-ct1-fc1] ** logged in **
    pwwn 50:00:09:72:08:60:2a:00 [esxi-lva1-host10-hba0] ** logged in **
""",
        "hardware": """
`show environment`
Power Supply:
  PS1: ok, 3000W AC input
  PS2: ok, 3000W AC input
  PS3: ok, 3000W AC input
  PS4: ok, 3000W AC input

Fan:
  Fan1: ok, 4200 RPM
  Fan2: ok, 4150 RPM
  Fan3: ok, 4180 RPM

Temperature:
  Inlet:   28.5C (alarm: 45C)
  Sup1:    42.0C (alarm: 75C)
  Sup2:    41.5C (alarm: 75C)
  Module3: 48.2C (alarm: 75C)

`show module`
Mod  Type                         Model              Status
---  ---------------------------  -----------------  ----------
1    Supervisor                   DS-X97-SF4-K9      active
2    Supervisor                   DS-X97-SF4-K9      ha-standby
3    48-port 32Gbps FC            DS-X9748-3072K9    ok
5    48-port 32Gbps FC            DS-X9748-3072K9    ok

`show system resources`
CPU: 1-min avg 35.2%, 5-min avg 28.4%
Memory: 20316/32768 MB used (62.0%)
""",
        "logging": """
`show logging last 50`
2026-04-12T08:15:00 %PORT-5-IF_DOWN_LINK_FAILURE: Interface fc1/3 is down (link_failure)
2026-04-12T08:14:58 %PORT-5-IF_UP: Interface fc1/3 is up
2026-04-12T08:14:45 %PORT-5-IF_DOWN_LINK_FAILURE: Interface fc1/3 is down (link_failure)
2026-04-12T08:14:42 %PORT-5-IF_UP: Interface fc1/3 is up
2026-04-12T08:14:30 %PORT-5-IF_DOWN_LINK_FAILURE: Interface fc1/3 is down (link_failure)
2026-04-12T08:10:00 %PORT-5-IF_DOWN_LINK_FAILURE: Interface fc1/3 is down (link_failure)
2026-04-12T08:09:55 %PORT-5-IF_UP: Interface fc1/3 is up
2026-04-12T08:05:00 %ZONE-5-ACTIVATION_SUCCESS: VSAN 100 full zoneset activation successful
2026-04-12T07:55:00 %PORT-5-IF_DOWN_LINK_FAILURE: Interface fc1/3 is down (link_failure)
2026-04-12T07:54:50 %PORT-5-IF_UP: Interface fc1/3 is up
2026-04-12T07:50:00 %PORT-5-IF_DOWN_LINK_FAILURE: Interface fc1/3 is down (link_failure)
2026-04-12T07:30:00 %PORT-2-CRC_THRESHOLD: fc1/3 CRC error threshold exceeded (892 errors)
2026-04-12T07:00:00 %PORT-4-LINK_FAILURE_COUNT: fc1/3 link failure count 47 in last 24h
2026-04-12T06:30:00 %FSPF-5-NBRCHANGE: VSAN 100 FSPF neighbor lva1-mds02 changed to FULL state
""",
        "fspf": """
`show fspf database vsan 100`
FSPF Routing Database for VSAN 100
  Local Domain ID: 1 (lva1-mds01)
  SPF computation: 0 pending

Link ID  Remote Domain  Remote Switch     Interface       Cost  State
-------  -------------  ----------------  --------------  ----  -----
1        2              lva1-mds02        port-channel1   500   FULL
""",
        "port-channel": """
`show port-channel summary`
Group  Port-Channel  Type  Protocol  Member Ports
-----  ------------  ----  --------  ---------------------
1      Po1(SU)       TE    Active    Fc1/47(P)  Fc1/48(P)

`show port-channel database`
port-channel1
  Administrative channel mode is active
  Operational channel mode is active
  Last membership update: 2026-04-12T06:00:00Z
  2 ports in total, 2 ports up
  First operational port: fc1/47
  Member fc1/47: up (P — bundled, active)
  Member fc1/48: up (P — bundled, active)
""",
    },
}


@tool
def load_show_tech(hostname: str, section: str = "") -> dict:
    """Load show-tech-support data from pre-collected files on disk.

    TWO-STEP LOADING (critical for large files):
      Step 1: Call with hostname only → returns list of available sections
      Step 2: Call with hostname + section → returns that section's content

    Show-tech files are 10,000+ lines. NEVER load everything at once.

    In production, files are at: /data/show-tech/<hostname>/latest.txt
    For POC, synthetic data is used.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        section: Section to load (e.g. 'interfaces', 'flogi', 'vsan'). Omit to list sections.

    Returns:
        If no section: list of available sections.
        If section specified: content of that section.
    """
    host_data = SYNTHETIC_SHOW_TECH.get(hostname)
    if not host_data:
        return {"error": f"No show-tech data for '{hostname}'",
                "available_hosts": list(SYNTHETIC_SHOW_TECH.keys())}

    # Step 1: Return section list
    if not section:
        sections = list(host_data.keys())
        return {
            "hostname": hostname,
            "available_sections": sections,
            "total_sections": len(sections),
            "instruction": "Call load_show_tech again with a specific section name to load its content. "
                           "Load only the sections you need — these files are very large.",
        }

    # Step 2: Return specific section
    content = host_data.get(section)
    if not content:
        return {"error": f"Section '{section}' not found",
                "available_sections": list(host_data.keys())}

    return {
        "hostname": hostname,
        "section": section,
        "content": content.strip(),
        "note": "This is pre-collected data, not live. Check collection timestamp for freshness.",
    }
```

### `tools/skills.py`

```python
"""Skill search and loading tools — reads investigation procedures from markdown files."""

from pathlib import Path
from langchain_core.tools import tool

SKILLS_PATH = Path(__file__).parent.parent / "skills"
MAX_SKILL_CHARS = 20_000


@tool
def search_skills(query: str) -> str:
    """Search investigation skills by keyword. Returns matching skill names and descriptions.
    Skills are step-by-step investigation procedures that tell you WHAT to check and in WHAT ORDER.

    Args:
        query: Search query (e.g. 'interface flap', 'health check', 'slow drain')

    Returns:
        Matching skills with title and description.
    """
    results = []
    query_lower = query.lower()

    for md_file in sorted(SKILLS_PATH.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        score = 0

        for word in query_lower.split():
            if word in md_file.stem.lower():
                score += 3
            if word in content.lower():
                score += 1

        if score > 0:
            # Extract title from frontmatter or first heading
            title = md_file.stem
            for line in content.split("\n"):
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"')
                    break

            # Extract description
            description = ""
            for line in content.split("\n"):
                if line.startswith("description:"):
                    description = line.split(":", 1)[1].strip().strip('"')
                    break

            results.append({
                "title": title,
                "file": md_file.name,
                "description": description,
                "score": score,
            })

    results.sort(key=lambda r: r["score"], reverse=True)

    if not results:
        available = [f.name for f in SKILLS_PATH.glob("*.md")]
        return f"No skills found matching '{query}'. Available: {available}"

    lines = [f"Found {len(results)} matching skill(s):\n"]
    for r in results:
        lines.append(f"**{r['title']}** (`{r['file']}`, relevance={r['score']})")
        if r["description"]:
            lines.append(f"  {r['description'][:200]}\n")
    lines.append("\nUse `load_skill` with the filename to load the full investigation procedure.")
    return "\n".join(lines)


@tool
def load_skill(skill_name: str) -> str:
    """Load the full content of an investigation skill.
    Follow the steps in order — each step tells you which tool to call and what to look for.

    Args:
        skill_name: Skill filename (e.g. 'mds-interface-issues.md')

    Returns:
        Full skill content as markdown — follow it step by step.
    """
    if ".." in skill_name or "/" in skill_name or "\\" in skill_name:
        return "Error: Invalid skill name."

    target = SKILLS_PATH / skill_name
    if not target.exists():
        target = SKILLS_PATH / f"{skill_name}.md"

    if not target.exists():
        available = [f.name for f in SKILLS_PATH.glob("*.md")]
        return f"Skill '{skill_name}' not found. Available: {available}"

    content = target.read_text(encoding="utf-8")
    if len(content) > MAX_SKILL_CHARS:
        content = content[:MAX_SKILL_CHARS] + f"\n\n... [truncated at {MAX_SKILL_CHARS} chars]"
    return content
```

### `app/agent.py`

```python
"""LangGraph ReAct agent — follows skills to investigate MDS interface issues."""

from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from app.config import ANTHROPIC_API_KEY, MODEL_NAME, MAX_ITERATIONS
from tools import ALL_TOOLS


SYSTEM_PROMPT = """You are an MDS 9710 Interface Triage Agent.

You investigate Fibre Channel interface issues on Cisco MDS 9710 directors:
port flapping, CRC errors, link failures, signal loss, credit starvation, ISL disruption.

## Your Workflow

1. When a user reports an interface issue, FIRST search for the relevant skill:
   `search_skills("interface")` → find `mds-interface-issues.md`

2. Load the skill: `load_skill("mds-interface-issues.md")`

3. **Follow the skill step by step.** Each step tells you:
   - Which tool to call
   - What to look for in the result
   - How to classify the finding (OK / DEGRADED / CRITICAL)
   - What to do next

4. If a tool returns no data, use `load_show_tech` as a fallback:
   - First call: `load_show_tech(hostname)` → get section list
   - Second call: `load_show_tech(hostname, "interfaces")` → get specific section

5. After all steps, compile a HANDOFF report with all evidence.

## Data Sources

You have three tiers of data:
- **LIVE** (NX-API): `get_interface_status`, `get_interface_counters`, `get_flogi_database`, etc.
- **STREAMING** (syslog): `get_syslog_entries` — timestamped event history
- **OFFLINE** (show-tech files): `load_show_tech` — pre-collected, load by section

## Critical Rules

- NEVER guess interface state — always query tools first
- Use show-tech as FALLBACK only, not primary source (it may be stale)
- Be specific: interface names, WWPN, error counts, timestamps
- The skill drives the investigation — follow its steps in order
- ALL paths end at ESCALATION — you investigate and report, you do NOT fix
- You do NOT push config, shut/no-shut ports, replace SFPs, or modify zones
"""


def create_agent():
    """Create and return the LangGraph ReAct agent."""
    llm = ChatAnthropic(
        model=MODEL_NAME,
        api_key=ANTHROPIC_API_KEY,
        temperature=0,
        max_tokens=8192,
    )

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
"""Streamlit chat interface for MDS 9710 Interface Triage Agent."""

import uuid
import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.agent import create_agent

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="MDS Interface Triage Agent",
    page_icon="🔴",
    layout="wide",
)

st.title("MDS 9710 Interface Triage Agent")
st.caption("AI-powered Fibre Channel interface investigation — follows structured skills, collects evidence, escalates to human")

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
    if st.button("Triage fc1/3 on lva1-mds01"):
        st.session_state.quick_action = (
            "fc1/3 on lva1-mds01 is flapping — 47 flaps and CRC errors. "
            "Investigate using the interface triage skill and produce an escalation report."
        )
    if st.button("All port status — lva1-mds01"):
        st.session_state.quick_action = "Show me all interface status on lva1-mds01"
    if st.button("Check FLOGI database"):
        st.session_state.quick_action = "Show FLOGI database on lva1-mds01 — who is logged in?"
    if st.button("Device health check"):
        st.session_state.quick_action = "Run a full health check on lva1-mds01"
    if st.button("Check ISL port-channels"):
        st.session_state.quick_action = "Check ISL port-channel status on lva1-mds01"

    st.divider()
    if st.button("New Conversation"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.header("Tools — Live (NX-API)")
    st.markdown("""
    - `get_interface_status` — All ports overview
    - `get_interface_detail` — Single port deep dive
    - `get_interface_counters` — Error counters (CRC, link failures, credits)
    - `get_flogi_database` — Fabric Login entries
    - `get_fcns_database` — FC Name Server
    - `get_fspf_neighbors` — Fabric routing adjacency
    - `get_port_channel_summary` — ISL bundles
    - `get_vsan_status` — Virtual SAN state
    - `get_zone_status` — Active zoneset + members
    - `get_device_health` — CPU, memory, PSU, fans, temp
    - `get_module_status` — Linecards + supervisors
    """)
    st.header("Tools — Streaming")
    st.markdown("- `get_syslog_entries` — Timestamped events")
    st.header("Tools — Offline")
    st.markdown("- `load_show_tech` — Pre-collected show-tech (by section)")
    st.header("Skills")
    st.markdown("""
    - `search_skills` — Find investigation procedure
    - `load_skill` — Load full skill content
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
    user_input = st.chat_input("Describe the MDS interface issue...")

# ── Process user input ───────────────────────────────────────
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

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
                        if isinstance(message, AIMessage) and message.tool_calls:
                            for tc in message.tool_calls:
                                tool_name = tc["name"]
                                tool_args = tc.get("args", {})
                                tool_calls_made.append(tool_name)
                                status_placeholder.info(
                                    f"Calling **{tool_name}**"
                                    f"({', '.join(f'{k}={v!r}' for k, v in tool_args.items())})"
                                )

                        elif isinstance(message, ToolMessage):
                            st.session_state.messages.append({
                                "role": "tool",
                                "tool_name": message.name,
                                "content": str(message.content)[:2000],
                            })

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

### `tools/__init__.py` (already shown above)

### `tests/__init__.py`

```python
# Tests
```

### `tests/test_tools.py`

```python
"""Unit tests for all MDS tools — verifies synthetic data returns correctly."""

from tools.mds_live import (
    get_interface_status,
    get_interface_detail,
    get_interface_counters,
    get_flogi_database,
    get_fcns_database,
    get_fspf_neighbors,
    get_port_channel_summary,
    get_vsan_status,
    get_zone_status,
    get_device_health,
    get_module_status,
)
from tools.syslog import get_syslog_entries
from tools.show_tech import load_show_tech


class TestInterfaceTools:
    def test_get_all_interfaces(self):
        result = get_interface_status.invoke({"hostname": "lva1-mds01"})
        assert result["hostname"] == "lva1-mds01"
        assert result["summary"]["down"] >= 1
        assert any(i["oper_status"] == "down" for i in result["interfaces"])

    def test_get_interface_detail(self):
        result = get_interface_detail.invoke({"hostname": "lva1-mds01", "interface": "fc1/3"})
        assert result["interface"]["oper_status"] == "down"
        assert result["interface"]["port_mode"] == "F"

    def test_get_interface_detail_not_found(self):
        result = get_interface_detail.invoke({"hostname": "lva1-mds01", "interface": "fc99/99"})
        assert "error" in result

    def test_get_counters_with_errors(self):
        result = get_interface_counters.invoke({"hostname": "lva1-mds01", "interface": "fc1/3"})
        assert result["severity"] == "CRITICAL"
        assert result["counters"]["crc_errors"] == 892
        assert result["counters"]["link_failures"] == 47
        assert result["counters"]["signal_losses"] == 3

    def test_get_counters_healthy(self):
        result = get_interface_counters.invoke({"hostname": "lva1-mds01", "interface": "fc1/1"})
        assert result["severity"] == "OK"
        assert result["counters"]["crc_errors"] == 0

    def test_unknown_host(self):
        result = get_interface_status.invoke({"hostname": "unknown-switch"})
        assert "error" in result


class TestFabricDatabaseTools:
    def test_flogi(self):
        result = get_flogi_database.invoke({"hostname": "lva1-mds01"})
        assert result["flogi_count"] == 6
        # fc1/3 device should NOT be in FLOGI
        interfaces_with_flogi = [e["interface"] for e in result["entries"]]
        assert "fc1/3" not in interfaces_with_flogi

    def test_fcns(self):
        result = get_fcns_database.invoke({"hostname": "lva1-mds01"})
        assert result["initiators"] == 3
        assert result["targets"] == 3

    def test_fspf(self):
        result = get_fspf_neighbors.invoke({"hostname": "lva1-mds01"})
        assert result["all_full"] is True
        assert result["neighbors"][0]["neighbor_switch"] == "lva1-mds02"

    def test_port_channel(self):
        result = get_port_channel_summary.invoke({"hostname": "lva1-mds01"})
        pc = result["port_channels"][0]
        assert pc["active_members"] == 2
        assert len(result["alerts"]) == 0  # All members up


class TestVSANAndZoneTools:
    def test_vsan_status(self):
        result = get_vsan_status.invoke({"hostname": "lva1-mds01"})
        assert any(v["vsan_id"] == 100 for v in result["vsans"])
        assert len(result["alerts"]) == 0  # All VSANs active

    def test_zone_status(self):
        result = get_zone_status.invoke({"hostname": "lva1-mds01", "vsan": 100})
        assert result["active_zoneset"] == "zs_prod_lva1"
        assert result["zones_with_offline_members"] == 1
        assert len(result["alerts"]) >= 1


class TestHealthTools:
    def test_device_health(self):
        result = get_device_health.invoke({"hostname": "lva1-mds01"})
        assert result["verdict"] == "OK"
        assert result["cpu_1min"] < 60
        assert result["memory_used_percent"] < 75

    def test_module_status(self):
        result = get_module_status.invoke({"hostname": "lva1-mds01"})
        assert any(m["status"] == "active" for m in result["modules"])
        assert any(m["status"] == "ha-standby" for m in result["modules"])


class TestSyslogTool:
    def test_get_all_entries(self):
        result = get_syslog_entries.invoke({"hostname": "lva1-mds01"})
        assert result["count"] > 0

    def test_filter_by_keyword(self):
        result = get_syslog_entries.invoke({"hostname": "lva1-mds01", "keyword": "fc1/3"})
        assert result["count"] > 0
        for entry in result["entries"]:
            assert "fc1/3" in entry["message"].lower()


class TestShowTechTool:
    def test_list_sections(self):
        result = load_show_tech.invoke({"hostname": "lva1-mds01"})
        assert "available_sections" in result
        assert "interfaces" in result["available_sections"]
        assert "flogi" in result["available_sections"]

    def test_load_specific_section(self):
        result = load_show_tech.invoke({"hostname": "lva1-mds01", "section": "interfaces"})
        assert "content" in result
        assert "fc1/3" in result["content"]
        assert "892 CRC errors" in result["content"]

    def test_load_nonexistent_section(self):
        result = load_show_tech.invoke({"hostname": "lva1-mds01", "section": "nonexistent"})
        assert "error" in result
```

---

## 8. Skills — Investigation Procedures <a name="8-skills"></a>

Skills are markdown files in the `skills/` directory. They tell Claude WHAT to investigate and in WHAT ORDER. Each step references specific tools by name.

The two skills for this agent are:

### `skills/mds-interface-issues.md`

This is the main 10-step investigation skill. It's too large to embed here — see the full file in the `skills/` directory of this repo.

**Summary of the 10 steps:**

| Step | Phase | What It Does | Tools Called |
|------|-------|-------------|-------------|
| 1 | Blast Radius | Port type + topology + connected device | `get_interface_status`, `get_flogi_database`, `get_fspf_neighbors` |
| 2 | Blast Radius | Port-channel check (ISL only) | `get_port_channel_summary` |
| 3 | Triage | Current state — still down? | `get_interface_detail` |
| 4 | Triage | Flap history — how unstable? | `get_interface_counters`, `get_syslog_entries` |
| 5 | Triage | Physical errors — CRC, signal, credits | `get_interface_counters` |
| 6 | Triage | FLOGI/FCNS — device visible in fabric? | `get_flogi_database`, `get_fcns_database` |
| 7 | Triage | VSAN + zone impact | `get_vsan_status`, `get_zone_status` |
| 8 | Triage | Device health — CPU, memory, modules | `get_device_health` |
| 9 | Fill Gaps | Show-tech for any steps with no data | `load_show_tech` |
| 10 | Escalate | Compile HANDOFF report | (no tool — writes report) |

### `skills/mds-health-check.md`

Called from Step 8 when deeper health analysis is needed. Covers CPU, memory, supervisors, linecards, PSU, fans, temperature, VSAN, FSPF.

---

## 9. Worked Example — Full MDS Interface Triage <a name="9-worked-example"></a>

```
User: "fc1/3 on lva1-mds01 is flapping — 47 flaps and CRC errors. Investigate."

── STEP 1: Claude API call ──
Claude: "Interface issue. Let me load the investigation skill."
  Calls: search_skills("interface flap MDS")
  Calls: get_interface_status("lva1-mds01")

── STEP 2: Tools run locally ──
  search_skills → "mds-interface-issues.md (score 12)"
  get_interface_status → fc1/3 DOWN, F-port, VSAN 100, stor-lva1-array05-ct1-fc0

── STEP 3: Claude API call ──
Claude: "Found the skill. Loading it. fc1/3 is an F-port to storage."
  Calls: load_skill("mds-interface-issues.md")
  Calls: get_flogi_database("lva1-mds01")

── STEP 4: Tools run locally ──
  load_skill → full 10-step procedure
  get_flogi_database → 6 entries, fc1/3 MISSING (device not logged in)

── STEP 5: Claude API call ──
Claude: "Skill Step 1 done. F-port to storage, FLOGI missing. Step 3: check state."
  Calls: get_interface_detail("lva1-mds01", "fc1/3")
  Calls: get_interface_counters("lva1-mds01", "fc1/3")
  Calls: get_syslog_entries("lva1-mds01", "fc1/3", 1)

── STEP 6: Tools run locally ──
  interface_detail → down, link_failure
  counters → 892 CRC, 47 link_failures, 3 signal_losses, severity=CRITICAL
  syslog → 12 entries, rapid up/down cycling every 15-30 seconds

── STEP 7: Claude API call ──
Claude: "Steps 3-5 done. Physical layer — CRC + signal loss. Step 6-8."
  Calls: get_fcns_database("lva1-mds01")
  Calls: get_vsan_status("lva1-mds01")
  Calls: get_zone_status("lva1-mds01", 100)
  Calls: get_device_health("lva1-mds01")

── STEP 8: Tools run locally ──
  fcns → 6 entries, fc1/3 WWPN missing
  vsan → VSAN 100 active
  zones → z_array05ct1_host12 has offline member (21:00:00:24:ff:4a:12:03)
  health → OK (CPU 35%, memory 62%, all modules OK)

── STEP 9: Claude API call ──
Claude: "Step 9: show-tech for SFP details."
  Calls: load_show_tech("lva1-mds01", "interfaces")

── STEP 10: Tool runs locally ──
  show_tech → fc1/3 SFP info: Rx Power -14.8 dBm (threshold -15.0 dBm) *** NEAR THRESHOLD ***

── STEP 11: Claude API call (FINAL) ──
Claude compiles escalation report:

  HANDOFF:
    device:         lva1-mds01
    platform:       Cisco MDS 9710
    alert:          InterfaceFlapping + CRCErrors
    port:           fc1/3 (F-port)
    connected_to:   stor-lva1-array05-ct1-fc0 (WWPN 21:00:00:24:ff:4a:12:03)
    vsan:           100
    root_cause:     PHYSICAL — SFP Rx power at -14.8 dBm (threshold -15.0 dBm),
                    892 CRC errors, 3 signal losses confirm degraded optics
    blast_radius:   Single storage path — esxi-lva1-host12 lost one path to array05
                    via zone z_array05ct1_host12

    evidence:
      interface_state:    down (link_failure)
      link_failures_1hr:  47
      crc_errors:         892
      signal_losses:      3
      encoding_errors:    23
      flogi_status:       MISSING
      fcns_status:        MISSING
      vsan_state:         active
      zone_intact:        NO — z_array05ct1_host12 has offline member
      device_health:      OK
      sfp_rx_power:       -14.8 dBm (near -15.0 threshold)
      show_tech_used:     yes

    recommended:    Replace SFP on fc1/3. Clean fiber connectors.
                    After replacement verify FLOGI re-registers and
                    zone member comes back online.
    notify:         DC Technicians

DONE. 6 Claude API calls. 12 tool executions. ~30 seconds.
```

---

## 10. Running It <a name="10-running"></a>

```bash
pip install -e ".[dev]"
echo "ANTHROPIC_API_KEY=sk-ant-api03-YOUR_KEY" > .env
streamlit run app/main.py
# Open http://localhost:8501
```

### Test queries:

1. **"fc1/3 on lva1-mds01 is flapping — investigate"** — Full 10-step triage with escalation report
2. **"Show all interface status on lva1-mds01"** — Quick data query, no skill needed
3. **"Check FLOGI database on lva1-mds01"** — Data query
4. **"Run health check on lva1-mds01"** — Loads mds-health-check.md skill
5. **"What's the ISL status between lva1-mds01 and lva1-mds02?"** — Port-channel + FSPF
6. **"Show me syslog for fc1/3 on lva1-mds01"** — Syslog query
7. **"Load show-tech interfaces section for lva1-mds01"** — Offline data

---

## 11. Tests <a name="11-tests"></a>

```bash
pytest tests/ -v
pytest tests/test_tools.py -v -s  # with output
```

---

## 12. Graduating to Real APIs <a name="12-graduating"></a>

### NX-API (replace synthetic data with live switch queries)

```python
# Before (POC):
@tool
def get_interface_status(hostname: str) -> dict:
    return SWITCH_INTERFACES[hostname]  # synthetic dict

# After (production):
import httpx

@tool
def get_interface_status(hostname: str) -> dict:
    payload = {
        "ins_api": {
            "version": "1", "type": "cli_show", "chunk": "0",
            "sid": "1", "input": "show interface brief", "output_format": "json"
        }
    }
    response = httpx.post(
        f"https://{hostname}/ins",
        json=payload,
        auth=("admin", get_switch_password(hostname)),
        verify=False,  # or your CA cert
        timeout=10.0,
    )
    response.raise_for_status()
    return parse_nxapi_interface_brief(response.json())
```

### Syslog (replace synthetic with real syslog server query)

```python
# Splunk example:
@tool
def get_syslog_entries(hostname: str, keyword: str = "", hours: int = 1) -> dict:
    query = f'search host="{hostname}" earliest=-{hours}h'
    if keyword:
        query += f' "{keyword}"'
    response = httpx.get(
        "https://splunk.internal:8089/services/search/jobs/export",
        params={"search": query, "output_mode": "json"},
        auth=("svc_agent", SPLUNK_TOKEN),
    )
    return parse_splunk_results(response.json())
```

### Show-tech (already reading from disk — just change the path)

```python
# Change SHOW_TECH_PATH to your real collection directory:
SHOW_TECH_PATH = Path("/data/show-tech")
# And update the loader to read real files instead of synthetic dicts
```

### Priority order for graduation:

1. **NX-API** — biggest value, replaces all LIVE tools at once
2. **Syslog** — already flowing, just need to query it
3. **Show-tech** — already collected by cron, just point to real files

Same tool names. Same parameters. Same return shapes. Agent code doesn't change.

---

## Quick Reference

| Component | Technology | Purpose |
|-----------|-----------|---------|
| LLM | Claude (Anthropic API) | The brain — follows skills, reasons about evidence |
| Agent Framework | LangGraph | Manages the ReAct tool loop |
| LLM Wrapper | LangChain Anthropic | Translates between LangGraph and Claude API |
| Frontend | Streamlit | Chat UI |
| Tools (Live) | Python + NX-API | Real-time switch queries |
| Tools (Streaming) | Python + Syslog | Event history |
| Tools (Offline) | Python + file read | Pre-collected show-tech |
| Skills | Markdown files | Step-by-step investigation procedures |

**Total external dependencies: 1 (Anthropic API key)**

**Total tools: 15** (11 live NX-API + 1 syslog + 1 show-tech + 2 skill search/load)

**Total skills: 2** (interface issues + health check)

Hand this to Claude and say "Build this." Everything is here.

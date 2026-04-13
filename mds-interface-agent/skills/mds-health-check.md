---
title: "MDS 9710 — Full Health Check"
alert_names: [HighCPU, HighMemory, ModuleDown, PSUFailure, FanFailure, OverTemperature]
description: "Complete health assessment of a Cisco MDS 9710 director: CPU, memory, supervisor modules, linecards, power supplies, fans, and temperature. Called standalone or from other skills (Step 8 of mds-interface-issues.md)."
scope: san-fabric
platform: NX-OS (MDS)
ai_ready: true
version: "1.0"
---

## What This Check Covers

The MDS 9710 is a director-class chassis with dual supervisors, up to 8 linecards, redundant power supplies and fan trays. This health check verifies all major subsystems and returns a verdict: OK, DEGRADED, or CRITICAL.

---

## Fast Triage

> **Rules:** Agent-executable steps only. No SSH, no CLI, no physical intervention.

### Step 1 — Supervisor and CPU

```
get_device_health(
  hostname = '<device>'
)
```

Check supervisor module status and CPU utilization.

| Metric | OK | DEGRADED | CRITICAL |
|---|---|---|---|
| Active supervisor | `active` | — | `not present` or `failed` |
| Standby supervisor | `ha-standby` | `not present` (no HA) | `failed` |
| CPU (1 min avg) | < 60% | 60–85% | > 85% |
| CPU (5 min avg) | < 50% | 50–75% | > 75% |

| Result | Action |
|---|---|
| Both sups healthy + CPU OK | → Step 2 |
| Standby sup missing | Record — no HA failover available → Step 2 |
| CPU > 85% | Check process table for runaway process → Step 2 |
| Active sup failed | CRITICAL — immediate escalation → Step 6 |

---

### Step 2 — Memory

From the same `get_device_health()` output, check memory:

| Metric | OK | DEGRADED | CRITICAL |
|---|---|---|---|
| System memory used | < 75% | 75–90% | > 90% |
| Kernel memory | < 80% | 80–90% | > 90% |

| Result | Action |
|---|---|
| Memory OK | → Step 3 |
| Memory DEGRADED | Record — may affect new fabric logins → Step 3 |
| Memory CRITICAL | Fabric instability risk → Step 3 |

---

### Step 3 — Linecard modules

```
get_module_status(
  hostname = '<device>'
)
```

Check all installed linecards.

| Module State | Interpretation |
|---|---|
| `ok` | Normal operation |
| `powered-up` | Booting — may be recovering from issue |
| `powered-down` | Admin shut or detected failure |
| `err-disabled` | Hardware error detected |
| `failed` | Module failure |

| Result | Action |
|---|---|
| All modules `ok` | → Step 4 |
| One module `powered-down` | Record — ports on that module are down → Step 4 |
| Module `failed` or `err-disabled` | CRITICAL — record module number → Step 4 |

---

### Step 4 — Power and environment

From `get_device_health()` output:

| Component | OK | DEGRADED | CRITICAL |
|---|---|---|---|
| Power supplies | All OK | 1 PSU failed (N+1 covers) | 2+ PSU failed |
| Fan trays | All OK | 1 fan degraded | Fan failed (thermal risk) |
| Inlet temperature | < 40C | 40–50C | > 50C |
| Module temperature | < 55C | 55–70C | > 70C |

| Result | Action |
|---|---|
| All environmental OK | → Step 5 |
| PSU or fan degraded | Record — hardware replacement needed → Step 5 |
| Temperature CRITICAL | Thermal shutdown risk — urgent → Step 5 |

---

### Step 5 — Fabric services health

```
get_vsan_status(
  hostname = '<device>'
)
```

```
get_fspf_neighbors(
  hostname = '<device>'
)
```

Quick check that fabric services are running:

| Check | OK | Problem |
|---|---|---|
| VSANs | All configured VSANs `active` | Any VSAN `suspended` |
| FSPF | All neighbors in `FULL` state | Neighbor stuck in `INIT` or missing |
| Zone server | Active zoneset present | No active zoneset (all access blocked) |

---

### Step 6 — Verdict

Combine findings from Steps 1–5:

| Condition | Verdict |
|---|---|
| All steps OK | **OK** — device is healthy |
| Any single DEGRADED finding | **DEGRADED** — operational but needs attention |
| Any CRITICAL finding OR 2+ DEGRADED findings | **CRITICAL** — immediate action needed |

```
HEALTH_VERDICT:
  device:       <hostname>
  verdict:      <OK / DEGRADED / CRITICAL>
  details:
    cpu_1min:         <percent>
    cpu_5min:         <percent>
    memory_used:      <percent>
    sup_active:       <status>
    sup_standby:      <status>
    modules_ok:       <count>
    modules_failed:   <count>
    psu_status:       <all OK / degraded / critical>
    fan_status:       <all OK / degraded / critical>
    temperature:      <max inlet temp>
    vsans_active:     <count>
    vsans_suspended:  <count>
    fspf_neighbors:   <all FULL / issues>
```

---

## Appendix — Health Check Flow

```
================================================================
  MDS 9710 HEALTH CHECK — FLOW
================================================================

  STEP 1 ─── Supervisor + CPU
  │  ✓ OK         → Step 2
  │  ⚠ DEGRADED   → record → Step 2
  │  ✗ CRITICAL   → immediate escalation → Step 6
  │
  ▼
  STEP 2 ─── Memory
  │  ✓ OK         → Step 3
  │  ⚠ DEGRADED   → record → Step 3
  │  ✗ CRITICAL   → record → Step 3
  │
  ▼
  STEP 3 ─── Linecard modules
  │  ✓ All ok     → Step 4
  │  ✗ Failed     → record → Step 4
  │
  ▼
  STEP 4 ─── Power + Environment
  │  ✓ OK         → Step 5
  │  ⚠ PSU/fan    → record → Step 5
  │  ✗ Thermal    → record → Step 5
  │
  ▼
  STEP 5 ─── Fabric services (VSAN + FSPF + zones)
  │  ✓ All active → Step 6
  │  ✗ Suspended  → record → Step 6
  │
  ▼
  STEP 6 ─── Verdict: OK / DEGRADED / CRITICAL

================================================================
```

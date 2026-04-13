---
title: "MDS 9710 — Interface Issues: Down, Flapping, or Physical Errors"
alert_names: [InterfaceDown, InterfaceFlapping, LinkFailure, CRCErrors, CreditLoss, TimeoutDiscards]
description: "A Cisco MDS 9710 Fibre Channel interface is operationally down, flapping, or reporting physical errors (CRC, link failures, credit loss). Covers F-ports (host/storage), E-ports (ISL), and TE-ports (trunked ISL). Includes FSPF and zone database impact."
scope: san-fabric
platform: NX-OS (MDS)
ai_ready: true
version: "1.0"
---

## What This Alert Means

This alert fires when a Fibre Channel interface on an MDS 9710 director changes operational state — going down, flapping between up and down, or accumulating physical errors. Interface state is monitored via SNMP polling or NX-API telemetry. Blast radius depends on the port type: an ISL (E-port or TE-port) going down breaks the inter-switch fabric path, potentially isolating an entire VSAN across switches; an F-port going down isolates a single host HBA or storage array port. The topology check in Step 1 identifies port type and connected device. The five most common root causes are a bad SFP (wavelength mismatch or failing laser), a fiber cable fault (dirty connector or micro-bend), credit starvation from a slow-drain device, a VSAN or zone misconfiguration after a change window, or an FSPF reconvergence loop after a topology change.

Fabric path: `Host HBA → F-port → MDS Fabric (ISL/TE) → F-port → Storage Array`

---

## Fast Triage

> **Rules:** Agent-executable steps only. Every branch ends in: action / escalation / `load_skill()`.
> **Banned:** SSH to device, manual CLI, vendor TAC cases, physical intervention.

### PHASE 1 — BLAST RADIUS

### Step 1 — Port type, topology, and blast radius

**1a — Get device info and port type:**

```
get_interface_status(
  hostname = '<device>'
)
```

If no data / error:

```
load_show_tech(
  hostname = '<device>'
)
```

Load section list, then load `interfaces` section. Parse to determine port roles.

**1b — Classify the affected port:**

Extract the affected interface from the alert (e.g., `fc1/3`, `port-channel 2`). Determine port type:

| Port Mode | Connected To | Role |
|---|---|---|
| F | Host HBA or Storage Array port | Edge port — single device |
| E | Another MDS switch (ISL) | Fabric interconnect |
| TE | Another MDS switch (trunked ISL) | Fabric interconnect + VSAN trunking |
| NP | NPV proxy uplink | Fabric edge proxy |
| SD | SPAN destination | Monitoring — no traffic impact |

**1c — Determine blast radius:**

| Port Type | Blast Radius | Scope |
|---|---|---|
| F-port (host) | Single host loses SAN access | One server — check if clustered |
| F-port (storage) | Single storage port down — multipath should cover | One path — check MPIO status |
| E-port (single ISL) | Reduced fabric bandwidth, FSPF reconverges | Fabric segment — check remaining ISLs |
| E-port (last ISL in path) | VSAN isolation between switches — hosts lose storage | Entire VSAN across two switches |
| TE-port | Same as E-port, plus VSAN trunk disruption | All VSANs carried on that trunk |
| Port-channel member | Reduced bundle bandwidth, no outage if others up | Check port-channel health |

**For F-ports** — identify the connected device:

```
get_flogi_database(
  hostname = '<device>'
)
```

| Result | Interpretation | Action |
|---|---|---|
| FLOGI entry exists for port | Device logged in — may have recovered | Record WWPN, device name → continue |
| No FLOGI entry for port | Device not logged in — port or device is down | Record in evidence |
| no data / error | Tool unavailable | FAILSAFE: check show-tech flogi section |

**For E/TE-ports** — identify the remote switch:

```
get_fspf_neighbors(
  hostname = '<device>'
)
```

| Result | Interpretation | Action |
|---|---|---|
| Neighbor visible on ISL | Remote switch reachable via other path | Record neighbor, check remaining ISL count |
| Neighbor gone | Fabric partition possible | CRITICAL — check port-channel status |
| no data / error | FSPF data unavailable | FAILSAFE: load show-tech `fspf` section |

---

### Step 2 — Port-channel check (ISL ports only)

If the affected port is an E-port or TE-port, check if it's part of a port-channel:

```
get_port_channel_summary(
  hostname = '<device>'
)
```

| Result | Interpretation | Action |
|---|---|---|
| Port is in port-channel + other members UP | Redundancy exists — reduced bandwidth only | Record remaining members → Step 3 |
| Port is in port-channel + last active member | CRITICAL — port-channel is effectively down | Fabric partition risk → Step 3 |
| Port is standalone ISL | No bundle redundancy | Single ISL — full path depends on this link → Step 3 |
| Port is F-port | Not applicable | Skip → Step 3 |
| no data / error | Tool unavailable | FAILSAFE: assume no redundancy → Step 3 |

---

### PHASE 2 — TRIAGE

### Step 3 — Current interface state: is it still down?

```
get_interface_status(
  hostname  = '<device>',
  interface = '<affected_port>'
)
```

Parse the specific port's operational state.

| Result | Interpretation | Action |
|---|---|---|
| up (F/E/TE) | Flap settled, interface recovered | Record recovery time → Step 4 |
| down | Still down — active issue | Record → Step 4 |
| errDisabled | Port shut by switch due to errors | CRITICAL — needs admin intervention → Step 4 |
| initializing | Port trying to come up | May be negotiation issue → Step 4 |
| no data / error | Telemetry gap | FAILSAFE: treat as down → Step 4 |

---

### Step 4 — Flap history: how unstable is the link?

```
get_interface_counters(
  hostname  = '<device>',
  interface = '<affected_port>'
)
```

Check `link_failure_count` and `sync_loss_count` from the counters.

Also check recent syslog for flap events:

```
get_syslog_entries(
  hostname = '<device>',
  keyword  = '<affected_port>',
  hours    = 1
)
```

| Result | Interpretation | Action |
|---|---|---|
| > 5 link failures in 60 min | CRITICAL — sustained flapping, likely hardware | → Step 5 |
| 1–5 link failures | DEGRADED — intermittent, may stabilize | → Step 5 |
| 0 link failures but port is down | Single event — went down and stayed | → Step 5 |
| sync_loss_count incrementing | Signal integrity issue — bad SFP or fiber | → Step 5 |
| no data / error | Counter data unavailable | FAILSAFE: check show-tech → Step 5 |

---

### Step 5 — Physical errors: CRC, encoding, credit loss

```
get_interface_counters(
  hostname  = '<device>',
  interface = '<affected_port>'
)
```

Check these specific counters:

| Counter | What It Means | Threshold |
|---|---|---|
| `crc_errors` | Bad frames — SFP, cable, or dirty connector | > 0 is concern, > 100 is CRITICAL |
| `encoding_errors` | Signal encoding failures | > 0 is concern |
| `link_failures` | Physical link drop events | Already checked in Step 4 |
| `signal_losses` | Optical signal lost — fiber or SFP issue | > 0 is CRITICAL |
| `invalid_tx_words` | Transmission encoding issue | > 0 is concern |
| `credit_loss` | Remote device not returning buffer credits | > 0 means slow-drain or congestion |
| `timeout_discards` | Frames discarded due to credit timeout | > 0 means active slow-drain |

| Result | Interpretation | Action |
|---|---|---|
| CRC > 0 or signal_losses > 0 | Physical layer issue — SFP or fiber | Record counts → Step 6 |
| credit_loss > 0 or timeout_discards > 0 | Slow-drain device on this port or downstream | → load_skill('mds-slow-drain.md') then → Step 6 |
| encoding_errors > 0 | Signal integrity — likely SFP | Record → Step 6 |
| All counters = 0 | Not a physical error issue | → Step 6 |
| no data / error | Counter data unavailable | FAILSAFE: check show-tech counters section → Step 6 |

---

### Step 6 — FLOGI/FCNS: is the end device visible in the fabric?

```
get_flogi_database(
  hostname = '<device>'
)
```

Check if the device connected to the affected port still has a fabric login.

```
get_fcns_database(
  hostname = '<device>'
)
```

Check if the device's WWPN is registered in the FC Name Server.

| Result | Interpretation | Action |
|---|---|---|
| FLOGI + FCNS entry present | Device logged in, visible in fabric | → Step 7 |
| FLOGI present, FCNS missing | Login exists but name server stale — possible zone issue | → Step 7 |
| FLOGI missing | Device not logged into fabric — port or device down | → Step 7 |
| no data / error | Fabric database unavailable | FAILSAFE: check show-tech flogi section → Step 7 |

---

### Step 7 — VSAN and zone impact

```
get_vsan_status(
  hostname = '<device>'
)
```

Check if the affected port's VSAN is active and has other members.

```
get_zone_status(
  hostname = '<device>',
  vsan     = '<vsan_id>'
)
```

Check if the active zoneset is intact.

| Result | Interpretation | Action |
|---|---|---|
| VSAN active + zone intact | Fabric services normal — issue isolated to port | → Step 8 |
| VSAN active + zone members missing | Zone disrupted — devices can't see each other | Record missing members → Step 8 |
| VSAN suspended | Entire VSAN down — major outage | CRITICAL → Step 8 |
| no data / error | Zone/VSAN data unavailable | FAILSAFE: note gap → Step 8 |

---

### Step 8 — Device health check

```
get_device_health(
  hostname = '<device>'
)
```

Check CPU, memory, module status, power supply, fans, temperature.

| Metric | OK | DEGRADED | CRITICAL |
|---|---|---|---|
| CPU (supervisor) | < 60% | 60–85% | > 85% |
| Memory | < 75% | 75–90% | > 90% |
| Module status | All `ok` | One module `powered-down` | Module `failed` or `err-disabled` |
| Power supply | All OK | One PSU failed (redundancy covers) | Multiple PSU failures |
| Temperature | < 45C | 45–55C | > 55C (thermal shutdown risk) |

| Verdict | Interpretation | Action |
|---|---|---|
| OK | Device healthy — issue is isolated to this interface | → Step 9 |
| DEGRADED | Partially degraded — proceed with caution | → Step 9 |
| CRITICAL | Device-level issue — not just this interface | → Step 9 |

---

### Step 9 — Offline data deep dive (if live data had gaps)

If any step above returned "no data / error", pull from show-tech:

```
load_show_tech(
  hostname = '<device>'
)
```

Step 1: Get section list. Then load relevant sections:

| Gap in Step | Show-tech Section to Load |
|---|---|
| Step 3 (interface state) | `interfaces` |
| Step 4 (flap history) | `logging` |
| Step 5 (error counters) | `interfaces` → look for counter details |
| Step 6 (FLOGI/FCNS) | `flogi`, `fcns` |
| Step 7 (VSAN/zones) | `vsan`, `zoneset` |
| Step 8 (device health) | `hardware`, `environment` |

Update evidence with show-tech findings for any gaps.

---

### PHASE 3 — ESCALATE

### Step 10 — ESCALATE (human handoff)

> The agent collects all evidence from Steps 1–9 and hands off to a human for resolution.
> The agent does NOT replace SFPs, push config, shut/no-shut ports, or modify zones.

| Finding from steps above | Root Cause | HANDOFF to | Recommended action |
|---|---|---|---|
| CRC > 0 + FLOGI gone | Bad SFP or fiber cable | DC Technicians | Physical inspection, clean/replace SFP and fiber |
| CRC > 0 + FLOGI present | Degrading optics — failing but not dead yet | DC Technicians | Proactive SFP replacement during maintenance |
| signal_losses > 0 | Fiber break or severe SFP failure | DC Technicians | Replace fiber, test with known-good SFP |
| credit_loss > 0 + timeout_discards > 0 | Slow-drain device | Storage Admin | Identify slow device, check HBA queue depth, check storage array port |
| Flaps > 5 in 60 min | Sustained flapping — hardware failing | DC Technicians | Replace SFP + fiber proactively |
| Port in errDisabled | Switch auto-disabled port due to errors | Storage Network Engineer | Investigate root cause before re-enabling |
| VSAN suspended | VSAN-level failure | Storage Network Engineer (urgent) | Check merge conflicts, FSPF issues, zone DB |
| Zone members missing + FLOGI gone | Device lost from fabric + zone disrupted | Storage Admin + Network Engineer | Check device, check zone config |
| ISL down + last path | Fabric partition | Storage Network Engineer (urgent) | Restore ISL, check for fiber cut |
| Health = CRITICAL | Device-level issue | Storage Network Engineer (urgent) | Address device health first, may need drain |
| No live data (3+ steps) | Device may be unreachable | Storage Network Engineer (urgent) | Check management connectivity, console access |

```
HANDOFF:
  device:         <hostname>
  platform:       Cisco MDS 9710
  alert:          InterfaceDown / InterfaceFlapping / CRCErrors / CreditLoss
  port:           <affected interface — e.g., fc1/3>
  port_type:      <F / E / TE / NP — from Step 1>
  connected_to:   <WWPN or remote switch — from Step 1/6>
  vsan:           <VSAN ID for the affected port>
  root_cause:     <physical / slow-drain / config / device-health / unknown>
  blast_radius:   <single host / single path / fabric segment / VSAN isolation>
  evidence:
    interface_state:    <up / down / errDisabled / initializing — from Step 3>
    port_channel:       <member of po<N> / standalone / N/A — from Step 2>
    remaining_isls:     <count — from Step 2, ISL only>
    link_failures_1hr:  <count — from Step 4>
    sync_losses:        <count — from Step 4>
    crc_errors:         <count — from Step 5>
    signal_losses:      <count — from Step 5>
    credit_loss:        <count — from Step 5>
    timeout_discards:   <count — from Step 5>
    flogi_status:       <present / missing — from Step 6>
    fcns_status:        <present / missing — from Step 6>
    vsan_state:         <active / suspended — from Step 7>
    zone_intact:        <yes / no / members missing — from Step 7>
    device_health:      <OK / DEGRADED / CRITICAL — from Step 8>
    cpu_percent:        <value — from Step 8>
    data_gaps:          <list of steps with no data — from Step 9>
    show_tech_used:     <yes / no — from Step 9>
  recommended:    <specific action from escalation table above>
  notify:         <DC Technicians / Storage Admin / Storage Network Engineer>
```

---

## Deep Reference

> Each pointer describes what it contains and when to use it.

- `mds-health-check.md` — full MDS 9710 health check: CPU, memory, modules, PSU, fans, linecards (use for Step 8 deep dive or standalone health check)
- `mds-slow-drain.md` — slow-drain investigation: credit loss, timeout discards, B2B credit monitoring, queue depth tuning (use when Step 5 finds credit_loss or timeout_discards)
- `mds-zone-issues.md` — zone database troubleshooting: merge failures, zone conflicts, missing members, enhanced vs basic zoning (use when Step 7 finds zone disruption)
- `mds-isl-troubleshooting.md` — ISL/port-channel investigation: trunk negotiation, VSAN allowed lists, FSPF path calculation (use when Step 2 finds ISL issues)
- `storage-array-connectivity.md` — storage array port check: multipath status, target login, LUN mapping (use when F-port down on storage side)
- `esxi-hba-issues.md` — ESXi host HBA troubleshooting: driver, firmware, link speed, NPIV (use when F-port down on host side)

---

## Appendix — Triage Flow Summary

```
================================================================
  MDS 9710 INTERFACE ISSUES — TRIAGE FLOW
================================================================

  STEP 1 ─── get_interface_status() + get_flogi_database()
  │           Classify port type (F/E/TE), get connected device
  │
  │  F-port  → single host or storage port
  │  E/TE    → ISL, check fabric impact
  │  ⚠ No data → FAILSAFE: load show-tech interfaces
  │
  ▼
  STEP 2 ─── get_port_channel_summary() [ISL only]
  │
  │  ✓ Other members UP        → reduced bandwidth, no outage
  │  ✗ Last member             → CRITICAL — fabric partition risk
  │  - F-port                  → skip
  │  ⚠ No data                 → FAILSAFE: assume no redundancy
  │
  ▼
  STEP 3 ─── get_interface_status(interface) — still down?
  │
  │  ✓ UP                     → flap settled → Step 4
  │  ✗ DOWN                   → still down → Step 4
  │  ✗ errDisabled            → CRITICAL — auto-disabled → Step 4
  │  ⚠ No data                → FAILSAFE: treat as down → Step 4
  │
  ▼
  STEP 4 ─── get_interface_counters() + get_syslog_entries()
  │           link_failures, sync_losses in last 60 min
  │
  │  ✓ > 5 failures           → CRITICAL — sustained flapping
  │  ✓ 1–5 failures           → DEGRADED — intermittent
  │  ✗ 0 failures             → single event
  │  ⚠ No data                → FAILSAFE: check show-tech logs
  │
  ▼
  STEP 5 ─── get_interface_counters() — CRC, signal, credits
  │
  │  ✓ CRC/signal errors      → physical issue → Step 6
  │  ✓ credit_loss/timeout     → slow-drain → load mds-slow-drain.md
  │  ✗ All zero                → not physical → Step 6
  │  ⚠ No data                → FAILSAFE: check show-tech counters
  │
  ▼
  STEP 6 ─── get_flogi_database() + get_fcns_database()
  │
  │  ✓ Device visible          → logged in → Step 7
  │  ✗ Device gone             → not in fabric → Step 7
  │  ⚠ No data                → FAILSAFE: check show-tech flogi
  │
  ▼
  STEP 7 ─── get_vsan_status() + get_zone_status()
  │
  │  ✓ VSAN active + zone OK   → isolated to port → Step 8
  │  ✗ VSAN suspended          → CRITICAL
  │  ✗ Zone members missing    → disrupted → Step 8
  │  ⚠ No data                → FAILSAFE: check show-tech vsan
  │
  ▼
  STEP 8 ─── get_device_health() — CPU, memory, modules
  │
  │  ✓ OK                     → isolated to interface → Step 9
  │  ✗ DEGRADED               → caution → Step 9
  │  ✗ CRITICAL               → device issue → Step 9
  │
  ▼
  STEP 9 ─── load_show_tech() — fill gaps from Steps 1–8
  │
  │  Load sections matching any "no data" steps
  │  Update evidence
  │
  ▼
  STEP 10 ── ESCALATE (HANDOFF)

================================================================
  STEP 10: ALL PATHS END HERE
================================================================

  ┌─────────────────────────────────┬────────────────────────────┐
  │ Finding                         │ HANDOFF to                 │
  ├─────────────────────────────────┼────────────────────────────┤
  │ CRC/signal + FLOGI gone         │ DC Tech: replace SFP/fiber │
  │ CRC/signal + FLOGI present      │ DC Tech: proactive replace │
  │ Credit loss + timeout discards  │ Storage Admin: slow-drain  │
  │ Flaps > 5                       │ DC Tech: replace hardware  │
  │ Port errDisabled                │ Net Eng: investigate first  │
  │ VSAN suspended                  │ Net Eng: urgent            │
  │ ISL down + last path            │ Net Eng: fabric partition   │
  │ Zone members missing            │ Admin + Eng: check both    │
  │ Health CRITICAL                 │ Net Eng: drain device       │
  │ 3+ data gaps                    │ Net Eng: escalate urgently │
  └─────────────────────────────────┴────────────────────────────┘

  Legend:
  ★ EXIT  = path leaves this skill entirely (e.g., load mds-slow-drain.md)
  ⚠ FAILSAFE = tool failed, safe assumption made, show-tech used as backup
```

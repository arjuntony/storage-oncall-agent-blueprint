# How the Storage Oncall Agent Works — A Visual Story

---

## Chapter 1: The Big Picture

> You type a question. Claude thinks. Your tools fetch data. Claude thinks again. You get an answer.

```mermaid
flowchart TD
    YOU[YOU\nType a question]

    YOU -->|your message| APP[YOUR APP\nStreamlit Chat UI\non your laptop]

    APP -->|sends message| CLAUDE[CLAUDE API\napi.anthropic.com\nThe Brain]

    CLAUDE -->|I need port status\ncall mds_port_status| TOOLS[YOUR TOOLS\nPython functions\non your laptop]

    TOOLS -->|port data\nfc1/3 DOWN 47 flaps| CLAUDE

    CLAUDE -->|CRC errors = bad SFP\nHere is my report| APP

    APP -->|shows answer| YOU

    style YOU fill:#1a1a2e,stroke:#58a6ff,stroke-width:3px,color:#e6edf3
    style APP fill:#161b22,stroke:#bc8cff,stroke-width:2px,color:#e6edf3
    style CLAUDE fill:#1a3d5f,stroke:#58a6ff,stroke-width:3px,color:#e6edf3
    style TOOLS fill:#1a3d1f,stroke:#3fb950,stroke-width:3px,color:#e6edf3
```

**Three things. That's it.**
- **Claude** = the brain (thinks, decides which tool to call)
- **Tools** = the hands (fetch data from your infrastructure)
- **App** = the glue (passes messages back and forth)

---

## Chapter 2: The Two Things That Happen

> Only two things ever happen. They take turns. That's the whole system.

```mermaid
flowchart LR
    subgraph INTERNET["INTERNET — Claude API Call"]
        direction TB
        A1[Your app sends message\n+ previous tool results]
        A2[Claude THINKS\nWhat do I need next?]
        A3[Claude replies\nCall this tool OR Here is my answer]
        A1 --> A2 --> A3
    end

    subgraph LOCAL["YOUR LAPTOP — Tool Execution"]
        direction TB
        B1[Your app sees Claude\nwants a tool called]
        B2[Runs YOUR Python function\nNo internet. No Claude.]
        B3[Returns data\nports, alerts, errors etc]
        B1 --> B2 --> B3
    end

    INTERNET -->|tool call| LOCAL
    LOCAL -->|tool result| INTERNET

    style INTERNET fill:#0d1f3c,stroke:#58a6ff,stroke-width:2px,color:#e6edf3
    style LOCAL fill:#0d2b0d,stroke:#3fb950,stroke-width:2px,color:#e6edf3
```

**Rule 1:** Claude = brain. Runs on Anthropic's servers. Requires internet.

**Rule 2:** Tool = hands. Runs on YOUR machine. No internet needed.

**They alternate. That's it.**

---

## Chapter 3: The ReAct Loop — What Actually Happens Per Request

> Claude calls tools in a loop until it has enough info to answer.

```mermaid
sequenceDiagram
    actor User
    participant App as Your App
    participant Claude as Claude API (brain)
    participant Tools as Your Tools (hands)

    User->>App: triage MDS switch lva1-mds01

    Note over App,Claude: API Call 1
    App->>Claude: User question + tool definitions
    Claude->>Claude: I need port status first
    Claude->>App: Call mds_port_status lva1-mds01

    Note over App,Tools: Tool runs locally
    App->>Tools: mds_port_status lva1-mds01
    Tools->>App: fc1/3 DOWN, 47 flaps, 892 CRC errors

    Note over App,Claude: API Call 2
    App->>Claude: Here is the tool result
    Claude->>Claude: CRC errors — need the runbook
    Claude->>App: Call search_runbooks port flap

    Note over App,Tools: Tool runs locally
    App->>Tools: search_runbooks port flap
    Tools->>App: Found mds-port-flap.md

    Note over App,Claude: API Call 3
    App->>Claude: Here is the search result
    Claude->>Claude: Load that runbook
    Claude->>App: Call load_runbook mds-port-flap.md

    Note over App,Tools: Tool runs locally
    App->>Tools: load_runbook mds-port-flap.md
    Tools->>App: Full runbook text with fix steps

    Note over App,Claude: API Call 4
    App->>Claude: Here is the runbook
    Claude->>Claude: I have everything now
    Claude->>App: Root cause bad SFP on fc1/3. Replace SFP. 12 VMs affected.

    App->>User: Shows triage report

    Note over User,Tools: Done! 4 API calls + 3 tool runs
```

---

## Chapter 4: Tool vs Skill — When to Use Which

> **Tool** = gets data (what's happening?). **Skill** = investigation procedure (what should I do about it?)

```mermaid
flowchart TD
    Q[User asks a question]

    Q --> D{What kind\nof question?}

    D -->|Show me data\nList something\nCheck status| TOOL_ONLY[TOOL ONLY\nCall tool then format results\n2 API calls about 5 seconds]

    D -->|Investigate this\nTriage this incident\nWhy did this fail| BOTH[TOOL + SKILL\nLoad skill then follow steps\ncall tools at each step\ncompile report and escalate\n5 API calls about 20 seconds]

    TOOL_ONLY --> R1[Claude calls 1 tool\npresents the data]

    BOTH --> R2[Claude loads the skill\ncalls multiple tools\nfollows procedure\nwrites escalation report]

    style Q fill:#1a1a2e,stroke:#58a6ff,stroke-width:2px,color:#e6edf3
    style D fill:#2d1f00,stroke:#d29922,stroke-width:2px,color:#e6edf3
    style TOOL_ONLY fill:#0d2b0d,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style BOTH fill:#2d0d2d,stroke:#bc8cff,stroke-width:2px,color:#e6edf3
    style R1 fill:#161b22,stroke:#30363d,color:#e6edf3
    style R2 fill:#161b22,stroke:#30363d,color:#e6edf3
```

---

## Chapter 5: Example 1 — "Show me failed backups" (Data Query)

> Simple. One tool. No skill needed.

```mermaid
sequenceDiagram
    actor User
    participant Claude as Claude API
    participant Tool as get_backup_status

    User->>Claude: Show me all VMs with failed backups last 24h

    Note over Claude: Data query. I need backup status.
    Claude->>Tool: get_backup_status status=failed hours=24

    Note over Tool: Runs YOUR code locally
    Tool->>Claude: 4 VMs failed. prod-db-01 snapshot locked SLA VIOLATED. prod-app-03 disk full. prod-web-07 timeout SLA VIOLATED. staging-api-01 network error.

    Note over Claude: Got it. Format and present.
    Claude->>User: 4 failed backups. 2 SLA violations. prod-db-01 and prod-web-07 need immediate attention.

    Note over User,Tool: Done! 2 API calls. 1 tool. ~5 seconds.
```

---

## Chapter 6: Example 2 — "Investigate and escalate" (Skill-Driven)

> Complex. Skill guides the investigation. Multiple tools gather evidence. Human gets the report.

```mermaid
sequenceDiagram
    actor User
    participant Claude as Claude API
    participant Tools as Your Tools
    participant Skill as backup-failure.md

    User->>Claude: Backup failed on prod-db-01 investigate and escalate

    rect rgb(20, 40, 20)
    Note over Claude,Tools: Step 1 - Get failure data
    Claude->>Tools: get_backup_status vm=prod-db-01
    Tools->>Claude: snapshot_locked, SLA violated, 14-day-old snapshot
    end

    rect rgb(40, 20, 40)
    Note over Claude,Skill: Step 2 - Load investigation skill
    Claude->>Tools: search_runbooks backup failure
    Tools->>Claude: Found backup-failure.md
    Claude->>Tools: load_runbook backup-failure.md
    Tools->>Claude: Full investigation procedure
    end

    Note over Claude: Now FOLLOWS the skill step by step

    rect rgb(20, 40, 20)
    Note over Claude,Tools: Step 3 - Check storage (skill says to)
    Claude->>Tools: datastore_health ds-lva1-stor05
    Tools->>Claude: 5.4% free, write latency 45ms, 8 SCSI errors
    end

    rect rgb(20, 40, 20)
    Note over Claude,Tools: Step 4 - Check VM (skill says to)
    Claude->>Tools: esxi_vm_status prod-db-01
    Tools->>Claude: memory 92%, stale snapshot 80.5 GB
    end

    rect rgb(20, 40, 20)
    Note over Claude,Tools: Step 5 - Check array (skill says to)
    Claude->>Tools: array_health stor-lva1-array05
    Tools->>Claude: DEGRADED, 2 failed disks, rebuilding 43%
    end

    rect rgb(40, 30, 10)
    Note over Claude: Step 6 - Compile escalation report
    Claude->>User: ESCALATION REPORT. Root cause: 14-day locked snapshot + array rebuild. Blast radius: 47 VMs. Action: delete snapshot needs DB team approval. Escalate to database-infra. NO REMEDIATION ATTEMPTED.
    end

    Note over User,Skill: Done! 5 API calls. 6 tools. ~20 seconds.
```

---

## Chapter 7: What You Control vs What Claude Controls

```mermaid
flowchart LR
    subgraph YOU["YOU CONTROL"]
        direction TB
        Y1[Which tools exist\nPython functions]
        Y2[What each tool does\nCode inside the function]
        Y3[Which skills exist\nMarkdown files]
        Y4[What steps in each skill\nInvestigation procedure]
        Y5[System prompt\nAgent personality and rules]
    end

    subgraph CLAUDE["CLAUDE CONTROLS"]
        direction TB
        C1[Which tool to call\nPicks from your list]
        C2[What parameters to pass\nBased on user question]
        C3[What to do with results\nReasoning over data]
        C4[When to stop\nWhen it has enough info]
        C5[How to format the answer\nBased on your system prompt]
    end

    YOU ~~~ CLAUDE

    style YOU fill:#0d2b0d,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style CLAUDE fill:#0d1f3c,stroke:#58a6ff,stroke-width:2px,color:#e6edf3
```

---

## Chapter 8: The File Map

> 12 files. That's the whole project.

```mermaid
flowchart TD
    subgraph PROJECT["storage-oncall-agent/"]
        direction TB

        subgraph APP["app/ — The Glue"]
            M[main.py - Chat UI]
            AG[agent.py - Creates the ReAct loop]
            CF[config.py - API key + settings]
        end

        subgraph TOOLS["tools/ — The Hands get data"]
            T1[incidents.py]
            T2[mds.py]
            T3[esxi.py]
            T4[storage_array.py]
            T5[backup.py]
            T6[rv_tool.py]
            T7[fabric.py]
            T8[runbooks.py]
        end

        subgraph SKILLS["runbooks/ — The Procedures what to do"]
            S1[mds-port-flap.md]
            S2[disk-failure.md]
            S3[esxi-vm-hang.md]
            S4[backup-failure.md]
            S5[datastore-full.md]
            S6[rv-tool-errors.md]
        end
    end

    AG -->|creates agent with| TOOLS
    AG -->|system prompt references| SKILLS
    M -->|uses| AG
    T8 -->|reads files from| SKILLS

    style PROJECT fill:#0d1117,stroke:#30363d,color:#e6edf3
    style APP fill:#1a1a2e,stroke:#bc8cff,stroke-width:2px,color:#e6edf3
    style TOOLS fill:#0d2b0d,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style SKILLS fill:#2d1f00,stroke:#d29922,stroke-width:2px,color:#e6edf3
```

---

## Chapter 9: From POC to Production

```mermaid
flowchart LR
    P1[Phase 1 POC\nSynthetic data\nJust an API key\n1-2 days]
    P2[Phase 2\nReal Incidents\nConnect PagerDuty\n2-3 days]
    P3[Phase 3\nReal APIs\nMDS and vCenter\n1-2 weeks]
    P4[Phase 4\nSmart Routing\nTool filtering\n3-5 days]
    P5[Phase 5\nSlack + CLI\nOncall notifications\n1 week]

    P1 -->|replace synthetic data| P2
    P2 -->|add real infra APIs| P3
    P3 -->|add middleware| P4
    P4 -->|add integrations| P5

    style P1 fill:#1a3d1f,stroke:#3fb950,stroke-width:3px,color:#e6edf3
    style P2 fill:#1a3d1f,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style P3 fill:#1f3a5f,stroke:#58a6ff,stroke-width:2px,color:#e6edf3
    style P4 fill:#2d1f00,stroke:#d29922,stroke-width:2px,color:#e6edf3
    style P5 fill:#3d1f5f,stroke:#bc8cff,stroke-width:2px,color:#e6edf3
```

---

## Chapter 10: Real World — All Data Sources Working Together

> Your friend has live data (RV tool, syslog) AND offline data (show-tech files). Both are tools. Skills tell Claude when to use which.

### The Rule

```mermaid
flowchart LR
    subgraph DATA["ANY data = TOOL"]
        direction TB
        D1[Live API - RV tool]
        D2[Live logs - syslog]
        D3[Live metrics - Prometheus]
        D4[Offline file - show-tech]
        D5[Offline file - config backup]
        D6[Database - JIRA tickets]
    end

    subgraph PROCEDURE["HOW to investigate = SKILL"]
        direction TB
        P1[interface-flapping.md]
        P2[disk-failure.md]
        P3[backup-failure.md]
    end

    DATA -->|provides data to| CLAUDE[Claude reads data\ndecides next step]
    PROCEDURE -->|tells Claude\nwhat steps to follow| CLAUDE

    style DATA fill:#0d2b0d,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style PROCEDURE fill:#2d1f00,stroke:#d29922,stroke-width:2px,color:#e6edf3
    style CLAUDE fill:#1a3d5f,stroke:#58a6ff,stroke-width:3px,color:#e6edf3
```

Doesn't matter if data comes from a live API or a file on disk. Tool = data. Skill = steps.

---

### The Tools — All Data Sources

```mermaid
flowchart TD
    subgraph LIVE["LIVE DATA — real-time from infrastructure"]
        RV[get_rv_tool_data\nhostname\nSSH or API to RV tool\nreturns connectivity\nfirmware zoning status]

        SYSLOG[get_syslog_entries\nhostname keyword hours\nreads from syslog server\nreturns timestamped log entries]

        METRICS[get_metrics\nhostname metric_name\nqueries Prometheus\nreturns counters and gauges]
    end

    subgraph OFFLINE["OFFLINE DATA — files on disk"]
        SHOWTECH[load_show_tech\nhostname section\nreads show-tech file from disk\nreturns parsed section data\nHUGE files - load by section]

        CONFIG[load_device_config\nhostname\nreads config backup file\nreturns running config text]
    end

    subgraph EXTERNAL["EXTERNAL SYSTEMS"]
        JIRA[get_open_tickets\nhostname\nqueries JIRA API\nreturns open tickets for device]
    end

    LIVE --> CLAUDE{Claude\ndecides which\ntools to call}
    OFFLINE --> CLAUDE
    EXTERNAL --> CLAUDE

    style LIVE fill:#0d2b0d,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style OFFLINE fill:#1a2d1a,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style EXTERNAL fill:#0d1f3c,stroke:#58a6ff,stroke-width:2px,color:#e6edf3
    style CLAUDE fill:#2d1f00,stroke:#d29922,stroke-width:3px,color:#e6edf3
```

---

### Show-Tech — Why Two-Step Loading

> Show-tech files are 10,000+ lines. If you dump everything into Claude, it chokes. So load in two steps.

```mermaid
sequenceDiagram
    actor User
    participant Claude as Claude API
    participant Tool as load_show_tech

    User->>Claude: interface fc1/3 on lva1-mds01 is flapping

    Note over Claude: I need show-tech data for this switch

    Claude->>Tool: load_show_tech hostname=lva1-mds01
    Note over Tool: Returns section LIST only, not content
    Tool->>Claude: Available sections: interfaces, vsan, zoneset, flogi, fcns, hardware, logging

    Note over Claude: For flapping I need interfaces and flogi

    Claude->>Tool: load_show_tech hostname=lva1-mds01 section=interfaces
    Tool->>Claude: Interface table - fc1/3 DOWN, 47 flaps, 892 CRC errors

    Claude->>Tool: load_show_tech hostname=lva1-mds01 section=flogi
    Tool->>Claude: FLOGI table - device 21:00:00:24:ff:4a:12:03 NOT logged in

    Note over Claude: Got targeted data without loading 10K lines
    Claude->>User: fc1/3 is down with CRC errors. FLOGI shows device logged out. Likely bad SFP.
```

---

### Full Investigation — Live + Offline + Skill Together

> User says: "interface fc1/3 on lva1-mds01 is flapping, investigate"

> Claude loads the skill, then calls live tools AND offline tools as the skill directs.

```mermaid
sequenceDiagram
    actor User
    participant Claude as Claude API
    participant Live as Live Tools
    participant Offline as Offline Tools
    participant Skill as interface-flapping.md

    User->>Claude: interface fc1/3 on lva1-mds01 is flapping, investigate

    Note over Claude: Need failure data + investigation skill

    rect rgb(40, 20, 40)
    Note over Claude,Skill: Load the investigation skill
    Claude->>Live: search_runbooks interface flapping
    Live->>Claude: Found interface-flapping.md
    Claude->>Live: load_runbook interface-flapping.md
    Live->>Claude: Full skill with steps
    end

    Note over Claude: Skill Step 1 says check syslog

    rect rgb(20, 40, 20)
    Note over Claude,Live: Step 1 - Live syslog data
    Claude->>Live: get_syslog_entries lva1-mds01 flap 24
    Live->>Claude: 47 flap events, last one 10 min ago
    Claude->>Live: get_syslog_entries lva1-mds01 CRC 24
    Live->>Claude: 892 CRC errors on fc1/3
    end

    Note over Claude: Skill Step 2 says check RV tool

    rect rgb(20, 40, 20)
    Note over Claude,Live: Step 2 - Live RV tool data
    Claude->>Live: get_rv_tool_data lva1-mds01
    Live->>Claude: connectivity 1 path down, firmware current
    end

    Note over Claude: Skill Step 3 says check show-tech

    rect rgb(20, 30, 40)
    Note over Claude,Offline: Step 3 - Offline show-tech data
    Claude->>Offline: load_show_tech lva1-mds01
    Offline->>Claude: Available sections: interfaces, flogi, hardware...
    Claude->>Offline: load_show_tech lva1-mds01 section=interfaces
    Offline->>Claude: fc1/3 error counters confirm CRC trend
    Claude->>Offline: load_show_tech lva1-mds01 section=flogi
    Offline->>Claude: Device 21:00:00:24:ff:4a:12:03 NOT logged in
    end

    Note over Claude: Skill Step 4 says correlate

    rect rgb(40, 30, 10)
    Note over Claude: Step 4 - Correlate and compile report
    Claude->>Claude: CRC errors in syslog + show-tech confirm bad SFP
    Claude->>Claude: FLOGI shows device logged out
    Claude->>Claude: RV tool shows 1 path down
    Claude->>User: ESCALATION REPORT\nRoot cause: bad SFP on fc1/3\nEvidence: 892 CRC errors in syslog, confirmed in show-tech,\nFLOGI shows device logged out, RV tool shows path down\nBlast radius: stor-lva1-array05 lost 1 path\nAction: replace SFP on fc1/3\nEscalate to: storage-infra for SFP swap
    end

    Note over User,Offline: 6 API calls. 7 tools used. Live + offline data correlated.
```

---

### The Skill That Drove This Investigation

This is what `interface-flapping.md` looks like — it names exact tools and exact parameters:

```
# Skill: Interface Flapping Investigation

Step 1: Check syslog (LIVE)
  - get_syslog_entries(hostname, "flap", 24) → count flap events
  - get_syslog_entries(hostname, "CRC", 24) → CRC errors present?

Step 2: Check RV tool (LIVE)
  - get_rv_tool_data(hostname) → connectivity and firmware

Step 3: Check show-tech (OFFLINE)
  - load_show_tech(hostname) → list available sections
  - load_show_tech(hostname, "interfaces") → error counters
  - load_show_tech(hostname, "flogi") → device login status

Step 4: Correlate and report
  - CRC in syslog + CRC in show-tech → physical layer issue (bad SFP/cable)
  - No CRC anywhere → host HBA issue or firmware bug
  - FLOGI device not logged in → confirms link is fully down
  - Compile escalation report. DO NOT remediate.
```

Claude follows this like a checklist. The more specific the tool names and parameters, the better Claude follows them.

---

### Summary — All Data Sources

```mermaid
flowchart TD
    USER[User asks about\ninterface flapping] --> CLAUDE[Claude loads skill\nfollows steps]

    CLAUDE --> STEP1[Step 1: LIVE syslog\nget_syslog_entries]
    CLAUDE --> STEP2[Step 2: LIVE RV tool\nget_rv_tool_data]
    CLAUDE --> STEP3[Step 3: OFFLINE show-tech\nload_show_tech]
    CLAUDE --> STEP4[Step 4: Correlate all data\nwrite escalation report]

    STEP1 -->|47 flaps, 892 CRC| EVIDENCE[All evidence\ncollected]
    STEP2 -->|1 path down, firmware OK| EVIDENCE
    STEP3 -->|counters confirm CRC\ndevice not logged in| EVIDENCE

    EVIDENCE --> STEP4
    STEP4 --> REPORT[Escalation report\nfor human to act on]

    style USER fill:#1a1a2e,stroke:#58a6ff,stroke-width:2px,color:#e6edf3
    style CLAUDE fill:#1a3d5f,stroke:#58a6ff,stroke-width:3px,color:#e6edf3
    style STEP1 fill:#0d2b0d,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style STEP2 fill:#0d2b0d,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style STEP3 fill:#1a2d1a,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style STEP4 fill:#2d1f00,stroke:#d29922,stroke-width:2px,color:#e6edf3
    style EVIDENCE fill:#161b22,stroke:#30363d,color:#e6edf3
    style REPORT fill:#2d0d0d,stroke:#f85149,stroke-width:2px,color:#e6edf3
```

**Live data + offline data + skills = full investigation. Claude correlates everything. Human gets the report.**

---

---

## Chapter 11: MDS 9710 Interface Triage — The Full Skill in Action

> This is the real use case. An MDS switch interface goes down. The skill drives a 10-step investigation. Claude follows it step by step, calling tools, collecting evidence, and handing off to a human.

### The Scenario

```
ALERT: InterfaceFlapping — lva1-mds01 fc1/3 — 47 flaps in 24h, 892 CRC errors
```

### How the Skill Drives the Agent

```mermaid
sequenceDiagram
    actor Oncall as Storage Oncall
    participant Agent as Claude Agent
    participant Skill as mds-interface-issues.md
    participant Tools as Python Tools
    participant ShowTech as Show-Tech Files

    Oncall->>Agent: triage lva1-mds01 fc1/3 flapping

    Note over Agent: Load the skill first
    Agent->>Skill: load_skill(mds-interface-issues.md)
    Skill-->>Agent: 10-step investigation procedure

    rect rgb(13, 43, 13)
        Note over Agent,Tools: PHASE 1 - BLAST RADIUS
        Agent->>Tools: get_interface_status(lva1-mds01)
        Tools-->>Agent: fc1/3 is F-port, connected to storage array, VSAN 100
        Note over Agent: F-port to storage = single path affected

        Agent->>Tools: get_flogi_database(lva1-mds01)
        Tools-->>Agent: WWPN 21:00:00:24:ff:4a:12:03 - NOT logged in
        Note over Agent: Device lost from fabric
    end

    rect rgb(26, 26, 46)
        Note over Agent,ShowTech: PHASE 2 - TRIAGE
        Agent->>Tools: get_interface_status(lva1-mds01, fc1/3)
        Tools-->>Agent: Status: down, reason: link_failure

        Agent->>Tools: get_interface_counters(lva1-mds01, fc1/3)
        Tools-->>Agent: 47 link failures, 892 CRC, 3 signal losses

        Agent->>Tools: get_syslog_entries(lva1-mds01, fc1/3, 1)
        Tools-->>Agent: 47 flap events in last hour

        Note over Agent: CRC + signal loss = physical layer issue

        Agent->>Tools: get_flogi_database(lva1-mds01)
        Tools-->>Agent: fc1/3 FLOGI missing

        Agent->>Tools: get_vsan_status(lva1-mds01)
        Tools-->>Agent: VSAN 100 active, zone member missing

        Agent->>Tools: get_device_health(lva1-mds01)
        Tools-->>Agent: CPU 35%, memory 62%, modules OK
    end

    rect rgb(45, 31, 0)
        Note over Agent,ShowTech: PHASE 3 - FILL GAPS WITH OFFLINE DATA
        Agent->>ShowTech: load_show_tech(lva1-mds01)
        ShowTech-->>Agent: Sections: interfaces, flogi, vsan, hardware, logging

        Agent->>ShowTech: load_show_tech(lva1-mds01, interfaces)
        ShowTech-->>Agent: fc1/3 counter detail confirms CRC trend
    end

    rect rgb(45, 13, 13)
        Note over Agent: PHASE 4 - ESCALATE
        Note over Agent: Evidence compiled from 10 steps
        Agent-->>Oncall: HANDOFF REPORT
    end
```

### The Escalation Report Claude Produces

```
HANDOFF:
  device:         lva1-mds01
  platform:       Cisco MDS 9710
  alert:          InterfaceFlapping + CRCErrors
  port:           fc1/3
  port_type:      F-port (storage array)
  connected_to:   WWPN 21:00:00:24:ff:4a:12:03 (stor-lva1-array05-hba3)
  vsan:           100
  root_cause:     PHYSICAL — bad SFP or fiber cable
  blast_radius:   Single storage path — check multipath on connected hosts

  evidence:
    interface_state:    down (link_failure)
    link_failures_1hr:  47
    crc_errors:         892
    signal_losses:      3
    flogi_status:       missing (device not in fabric)
    vsan_state:         active
    zone_intact:        no — member missing from z_array05_host12
    device_health:      OK (CPU 35%, mem 62%, modules OK)
    show_tech_used:     yes — confirmed CRC trend in counter history

  recommended:    Replace SFP and fiber on fc1/3. Clean connectors.
                  After replacement, verify FLOGI re-registers.
  notify:         DC Technicians
```

### The Investigation Flow — All 10 Steps

```mermaid
flowchart TD
    ALERT[ALERT: fc1/3 flapping\n47 flaps, 892 CRC] --> S1

    subgraph P1["PHASE 1: BLAST RADIUS"]
        S1[Step 1: Port type + topology\nget_interface_status\nget_flogi_database\nget_fspf_neighbors]
        S2[Step 2: Port-channel check\nget_port_channel_summary\nISL ports only]
    end

    subgraph P2["PHASE 2: TRIAGE"]
        S3[Step 3: Still down?\nget_interface_status interface]
        S4[Step 4: Flap count\nget_interface_counters\nget_syslog_entries]
        S5[Step 5: Physical errors\nCRC signal credit\nget_interface_counters]
        S6[Step 6: FLOGI + FCNS\nDevice in fabric?\nget_flogi_database]
        S7[Step 7: VSAN + zone\nget_vsan_status\nget_zone_status]
        S8[Step 8: Device health\nget_device_health\nCPU mem modules PSU]
    end

    subgraph P3["PHASE 3: FILL GAPS"]
        S9[Step 9: Show-tech\nload_show_tech\nFill any no-data gaps]
    end

    subgraph P4["PHASE 4: ESCALATE"]
        S10[Step 10: HANDOFF\nCompile all evidence\nRoot cause + action + notify]
    end

    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> S5
    S5 --> S6
    S6 --> S7
    S7 --> S8
    S8 --> S9
    S9 --> S10

    S5 -.->|credit_loss detected| SLOW[load_skill\nmds-slow-drain.md]
    S8 -.->|CRITICAL health| HEALTH[load_skill\nmds-health-check.md]

    style ALERT fill:#2d0d0d,stroke:#f85149,stroke-width:2px,color:#e6edf3
    style P1 fill:#0d2b0d,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style P2 fill:#1a1a2e,stroke:#58a6ff,stroke-width:2px,color:#e6edf3
    style P3 fill:#2d1f00,stroke:#d29922,stroke-width:2px,color:#e6edf3
    style P4 fill:#2d0d0d,stroke:#f85149,stroke-width:2px,color:#e6edf3
    style SLOW fill:#2d1f00,stroke:#d29922,stroke-width:1px,color:#e6edf3
    style HEALTH fill:#2d1f00,stroke:#d29922,stroke-width:1px,color:#e6edf3
```

### Decision Logic at Each Step

```mermaid
flowchart TD
    S5{Step 5: What errors?}

    S5 -->|CRC > 0\nsignal_losses > 0| PHY[Physical layer\nBad SFP or fiber]
    S5 -->|credit_loss > 0\ntimeout_discards > 0| SLOW[Slow-drain\nHBA queue depth issue]
    S5 -->|All counters = 0| CLEAN[Not physical\nCheck config or remote]

    PHY --> S6A{Step 6: FLOGI?}
    SLOW --> DRAIN[load_skill\nmds-slow-drain.md]
    CLEAN --> S6B{Step 6: FLOGI?}

    S6A -->|Gone| DEAD[SFP/cable dead\nDevice lost from fabric]
    S6A -->|Present| DYING[SFP degrading\nStill works intermittently]

    S6B -->|Gone| CONFIG[Check remote device\nMay be powered off]
    S6B -->|Present| ZONE[Check zone config\nMay be misconfigured]

    DEAD --> ESC1[DC Tech: replace SFP + fiber]
    DYING --> ESC2[DC Tech: proactive replacement]
    CONFIG --> ESC3[Storage Admin: check device]
    ZONE --> ESC4[Net Eng: check zone config]
    DRAIN --> ESC5[Storage Admin: check HBA queue depth]

    style S5 fill:#1a3d5f,stroke:#58a6ff,stroke-width:2px,color:#e6edf3
    style PHY fill:#2d0d0d,stroke:#f85149,color:#e6edf3
    style SLOW fill:#2d1f00,stroke:#d29922,color:#e6edf3
    style CLEAN fill:#0d2b0d,stroke:#3fb950,color:#e6edf3
    style DRAIN fill:#2d1f00,stroke:#d29922,color:#e6edf3
    style DEAD fill:#2d0d0d,stroke:#f85149,color:#e6edf3
    style DYING fill:#2d1f00,stroke:#d29922,color:#e6edf3
    style CONFIG fill:#1a1a2e,stroke:#58a6ff,color:#e6edf3
    style ZONE fill:#1a1a2e,stroke:#58a6ff,color:#e6edf3
    style ESC1 fill:#161b22,stroke:#f85149,color:#e6edf3
    style ESC2 fill:#161b22,stroke:#d29922,color:#e6edf3
    style ESC3 fill:#161b22,stroke:#58a6ff,color:#e6edf3
    style ESC4 fill:#161b22,stroke:#58a6ff,color:#e6edf3
    style ESC5 fill:#161b22,stroke:#d29922,color:#e6edf3
```

### What the Agent DOES vs DOES NOT Do

```mermaid
flowchart LR
    subgraph DOES["AGENT DOES"]
        D1[Collect evidence\nfrom all data sources]
        D2[Follow the skill\nstep by step]
        D3[Correlate findings\nacross tools]
        D4[Determine root cause\nfrom evidence]
        D5[Compile structured\nhandoff report]
    end

    subgraph DOESNT["AGENT DOES NOT"]
        N1[Replace SFP\nor fiber cable]
        N2[Push config\nto switch]
        N3[Shut or no-shut\nports]
        N4[Modify zones\nor VSANs]
        N5[File change\nmanagement tickets]
    end

    DOES --> HANDOFF[Human gets report\nHuman takes action]
    DOESNT -.->|These require\nhuman judgment| HANDOFF

    style DOES fill:#0d2b0d,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style DOESNT fill:#2d0d0d,stroke:#f85149,stroke-width:2px,color:#e6edf3
    style HANDOFF fill:#1a3d5f,stroke:#58a6ff,stroke-width:3px,color:#e6edf3
```

### File Structure — Skills + Tools

```
storage-oncall-agent/
├── skills/                              # Investigation procedures
│   ├── mds-interface-issues.md          # THIS skill — 10-step interface triage
│   ├── mds-health-check.md              # Device health assessment
│   ├── mds-slow-drain.md                # Credit loss investigation
│   ├── mds-zone-issues.md               # Zone database troubleshooting
│   ├── storage-array-connectivity.md    # Array port + multipath check
│   └── esxi-hba-issues.md              # Host HBA troubleshooting
│
├── tools/                               # Data sources (Python functions)
│   ├── mds.py                           # get_interface_status, get_interface_counters
│   │                                    # get_flogi_database, get_fspf_neighbors
│   │                                    # get_port_channel_summary, get_vsan_status
│   │                                    # get_zone_status, get_device_health
│   ├── syslog.py                        # get_syslog_entries
│   ├── show_tech.py                     # load_show_tech (two-step: list then load)
│   ├── esxi.py                          # esxi_vm_status, datastore_health
│   ├── storage_array.py                 # array_health, disk_failures
│   ├── rv_tool.py                       # rv_tool_check
│   └── skills.py                        # search_skills, load_skill
│
└── app/
    ├── agent.py                         # LangGraph ReAct loop
    └── main.py                          # Streamlit UI
```

---

## The One-Sentence Summary

> **You define the tools (data from anywhere — APIs, syslog, files on disk) and skills (step-by-step procedures). Claude decides when to call them and synthesizes everything into a human-readable answer.**

That's it. That's the whole thing.

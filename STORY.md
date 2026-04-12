# How the Storage Oncall Agent Works — A Visual Story

---

## Chapter 1: The Big Picture

> You type a question. Claude thinks. Your tools fetch data. Claude thinks again. You get an answer.

```mermaid
flowchart TD
    YOU["<b>YOU</b><br/>Type: 'check MDS switch lva1-mds01'"]
    
    YOU -->|your message| APP["<b>YOUR APP</b><br/>Streamlit Chat UI<br/>running on your laptop"]
    
    APP -->|sends message| CLAUDE["<b>CLAUDE API</b><br/>api.anthropic.com<br/>The Brain - thinks & decides"]
    
    CLAUDE -->|'I need port status'<br/>call mds_port_status| TOOLS["<b>YOUR TOOLS</b><br/>Python functions<br/>running on your laptop"]
    
    TOOLS -->|port data:<br/>fc1/3 DOWN, 47 flaps| CLAUDE
    
    CLAUDE -->|'CRC errors = bad SFP.<br/>Here is my report.'| APP
    
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
    subgraph INTERNET["  INTERNET — Claude API Call  "]
        direction TB
        A1["Your app sends message +<br/>previous tool results"]
        A2["Claude THINKS:<br/>'What do I need next?'"]
        A3["Claude replies:<br/>'Call this tool' OR 'Here is my answer'"]
        A1 --> A2 --> A3
    end

    subgraph LOCAL["  YOUR LAPTOP — Tool Execution  "]
        direction TB
        B1["Your app sees Claude<br/>wants a tool called"]
        B2["Runs YOUR Python function<br/>No internet. No Claude."]
        B3["Returns data:<br/>{ports: [...], alerts: [...]}"]
        B1 --> B2 --> B3
    end

    INTERNET -->|"tool call"| LOCAL
    LOCAL -->|"tool result"| INTERNET

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
    participant Claude as Claude API<br/>(brain)
    participant Tools as Your Tools<br/>(hands)

    User->>App: "triage MDS switch lva1-mds01"
    
    Note over App,Claude: 🔵 API Call #1
    App->>Claude: Here's the user's question + tool definitions
    Claude->>Claude: Thinks: "I need port status first"
    Claude->>App: Call mds_port_status("lva1-mds01")
    
    Note over App,Tools: 🟢 Tool runs locally
    App->>Tools: mds_port_status("lva1-mds01")
    Tools->>App: {fc1/3: DOWN, 47 flaps, 892 CRC errors}

    Note over App,Claude: 🔵 API Call #2
    App->>Claude: Here's what the tool returned
    Claude->>Claude: Thinks: "CRC errors — need the runbook"
    Claude->>App: Call search_runbooks("port flap")

    Note over App,Tools: 🟢 Tool runs locally
    App->>Tools: search_runbooks("port flap")
    Tools->>App: Found: mds-port-flap.md

    Note over App,Claude: 🔵 API Call #3
    App->>Claude: Here's the search result
    Claude->>Claude: Thinks: "Load that runbook"
    Claude->>App: Call load_runbook("mds-port-flap.md")

    Note over App,Tools: 🟢 Tool runs locally
    App->>Tools: load_runbook("mds-port-flap.md")
    Tools->>App: Full runbook text with fix steps

    Note over App,Claude: 🔵 API Call #4
    App->>Claude: Here's the runbook content
    Claude->>Claude: Thinks: "I have everything now"
    Claude->>App: "Root cause: bad SFP on fc1/3.<br/>Action: replace SFP.<br/>Blast radius: 12 VMs."
    
    App->>User: Shows triage report
    
    Note over User,Tools: Done! 4 API calls + 3 tool runs = ~15 seconds
```

---

## Chapter 4: Tool vs Skill — When to Use Which

> **Tool** = gets data (what's happening?). **Skill** = investigation procedure (what should I do about it?)

```mermaid
flowchart TD
    Q["User asks a question"]
    
    Q --> D{"What kind<br/>of question?"}
    
    D -->|"Show me data"<br/>"List failed backups"<br/>"Check port status"| TOOL_ONLY["<b>Tool Only</b><br/>Call tool → format results → done<br/><i>2 API calls, ~5 seconds</i>"]
    
    D -->|"Investigate this"<br/>"Triage this incident"<br/>"Why did this fail?"| BOTH["<b>Tool + Skill</b><br/>Load skill → follow steps →<br/>call tools at each step →<br/>compile report → escalate<br/><i>5 API calls, ~20 seconds</i>"]
    
    TOOL_ONLY --> R1["Claude calls <b>1 tool</b>,<br/>presents the data"]
    
    BOTH --> R2["Claude loads the <b>skill</b>,<br/>calls <b>multiple tools</b>,<br/>follows procedure,<br/>writes escalation report"]

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
    participant Tool as get_backup_status()

    User->>Claude: "Show me all VMs with failed backups last 24h"
    
    Note over Claude: Thinks: "Data query. I need backup status."
    Claude->>Tool: get_backup_status(status="failed", hours=24)
    
    Note over Tool: Runs YOUR code locally.<br/>Returns synthetic/real data.
    Tool->>Claude: 4 VMs failed:<br/>prod-db-01 (snapshot locked, SLA VIOLATED)<br/>prod-app-03 (disk full)<br/>prod-web-07 (timeout, SLA VIOLATED)<br/>staging-api-01 (network error)
    
    Note over Claude: Thinks: "Got it. Format and present."
    Claude->>User: "4 failed backups. 2 SLA violations.<br/>prod-db-01 and prod-web-07 need<br/>immediate attention."

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

    User->>Claude: "Backup failed on prod-db-01, investigate and escalate"
    
    rect rgb(20, 40, 20)
    Note over Claude,Tools: Step 1: Get failure data
    Claude->>Tools: get_backup_status(vm="prod-db-01")
    Tools->>Claude: snapshot_locked, SLA violated, 14-day-old snapshot
    end

    rect rgb(40, 20, 40)
    Note over Claude,Skill: Step 2: Load investigation skill
    Claude->>Tools: search_runbooks("backup failure")
    Tools->>Claude: Found: backup-failure.md
    Claude->>Tools: load_runbook("backup-failure.md")
    Tools->>Claude: Full investigation procedure
    end

    Note over Claude: Now FOLLOWS the skill step by step

    rect rgb(20, 40, 20)
    Note over Claude,Tools: Step 3: Check storage (skill says to)
    Claude->>Tools: datastore_health("ds-lva1-stor05")
    Tools->>Claude: 5.4% free, write latency 45ms, 8 SCSI errors
    end

    rect rgb(20, 40, 20)
    Note over Claude,Tools: Step 4: Check VM (skill says to)
    Claude->>Tools: esxi_vm_status("prod-db-01")
    Tools->>Claude: memory 92%, stale snapshot 80.5 GB
    end

    rect rgb(20, 40, 20)
    Note over Claude,Tools: Step 5: Check array (skill says to)
    Claude->>Tools: array_health("stor-lva1-array05")
    Tools->>Claude: DEGRADED, 2 failed disks, rebuilding 43%
    end

    rect rgb(40, 30, 10)
    Note over Claude: Step 6: Compile escalation report (skill template)
    Claude->>User: ESCALATION REPORT:<br/>Root cause: 14-day locked snapshot<br/>+ array rebuild causing latency<br/>Blast radius: 47 VMs<br/>Action: delete snapshot (need DB team approval)<br/>Escalate to: database-infra (SLA violated)<br/><br/>⚠️ NO REMEDIATION ATTEMPTED
    end

    Note over User,Skill: Done! 5 API calls. 6 tools. ~20 seconds.<br/>Human decides what to fix.
```

---

## Chapter 7: What You Control vs What Claude Controls

```mermaid
flowchart LR
    subgraph YOU["  🔧 YOU CONTROL  "]
        direction TB
        Y1["Which tools exist<br/><i>Python functions with @tool</i>"]
        Y2["What each tool does<br/><i>Code inside the function</i>"]
        Y3["Which skills exist<br/><i>Markdown files in runbooks/</i>"]
        Y4["What steps are in each skill<br/><i>Investigation procedure</i>"]
        Y5["System prompt<br/><i>Agent's personality & rules</i>"]
    end

    subgraph CLAUDE["  🧠 CLAUDE CONTROLS  "]
        direction TB
        C1["Which tool to call<br/><i>Picks from your list</i>"]
        C2["What parameters to pass<br/><i>Based on user's question</i>"]
        C3["What to do with results<br/><i>Reasoning over data</i>"]
        C4["When to stop<br/><i>When it has enough info</i>"]
        C5["How to format the answer<br/><i>Based on your system prompt</i>"]
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
            M["main.py<br/><i>Chat UI (Streamlit)</i>"]
            AG["agent.py<br/><i>Creates the ReAct loop</i>"]
            CF["config.py<br/><i>API key + settings</i>"]
        end

        subgraph TOOLS["tools/ — The Hands (get data)"]
            T1["incidents.py — active incidents"]
            T2["mds.py — MDS switch ports & zones"]
            T3["esxi.py — VMs & datastores"]
            T4["storage_array.py — array & disk health"]
            T5["backup.py — backup status"]
            T6["rv_tool.py — RV checks"]
            T7["fabric.py — FC fabric topology"]
            T8["runbooks.py — search & load skills"]
        end

        subgraph SKILLS["runbooks/ — The Procedures (what to do)"]
            S1["mds-port-flap.md"]
            S2["disk-failure.md"]
            S3["esxi-vm-hang.md"]
            S4["backup-failure.md"]
            S5["datastore-full.md"]
            S6["rv-tool-errors.md"]
        end
    end

    AG -->|creates agent with| TOOLS
    AG -->|system prompt tells Claude about| SKILLS
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
    P1["<b>Phase 1: POC</b><br/>Synthetic data<br/>Just an API key<br/><i>1-2 days</i>"]
    P2["<b>Phase 2: Real Incidents</b><br/>Connect PagerDuty/<br/>OpsGenie<br/><i>2-3 days</i>"]
    P3["<b>Phase 3: Real APIs</b><br/>MDS NX-API<br/>vCenter REST<br/><i>1-2 weeks</i>"]
    P4["<b>Phase 4: Smart Routing</b><br/>Tool filtering<br/>Model switching<br/><i>3-5 days</i>"]
    P5["<b>Phase 5: Slack + CLI</b><br/>Oncall notifications<br/>Terminal triage<br/><i>1 week</i>"]

    P1 -->|"replace synthetic data"| P2
    P2 -->|"add real infra APIs"| P3
    P3 -->|"add middleware"| P4
    P4 -->|"add integrations"| P5

    style P1 fill:#1a3d1f,stroke:#3fb950,stroke-width:3px,color:#e6edf3
    style P2 fill:#1a3d1f,stroke:#3fb950,stroke-width:2px,color:#e6edf3
    style P3 fill:#1f3a5f,stroke:#58a6ff,stroke-width:2px,color:#e6edf3
    style P4 fill:#2d1f00,stroke:#d29922,stroke-width:2px,color:#e6edf3
    style P5 fill:#3d1f5f,stroke:#bc8cff,stroke-width:2px,color:#e6edf3
```

---

## The One-Sentence Summary

> **You define the tools (data) and skills (procedures). Claude decides when to call them and synthesizes everything into a human-readable answer.**

That's it. That's the whole thing.

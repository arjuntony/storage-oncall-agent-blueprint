# How It Works — Agent Flow Explained

A simple guide to how the MDS Interface Triage Agent works, and why **skills** matter.

---

## 1. The Big Picture — All Components

```mermaid
flowchart TD
    subgraph USER["User"]
        U[Oncall Engineer]
    end

    subgraph AGENT["Agent Engine - LangGraph ReAct Loop"]
        LLM["LLM Brain\n Claude / GPT"]
    end

    subgraph SKILLS["Skills - Investigation Procedures"]
        S1[mds-interface-issues.md]
        S2[mds-health-check.md]
        S3[future: mds-zone-issues.md]
        S4[future: mds-isl-issues.md]
    end

    subgraph TOOLS["Tools - Data Sources"]
        direction LR
        subgraph LIVE["Live - NX-API"]
            T1[get_interface_status]
            T2[get_interface_detail]
            T3[get_interface_counters]
            T4[get_flogi_database]
            T5[get_fcns_database]
            T6[get_fspf_neighbors]
            T7[get_port_channel_summary]
            T8[get_vsan_status]
            T9[get_zone_status]
            T10[get_device_health]
            T11[get_module_status]
        end
        subgraph STREAM["Streaming"]
            T12[get_syslog_entries]
        end
        subgraph OFFLINE["Offline"]
            T13[load_show_tech]
        end
        subgraph SKILL_TOOLS["Skill Loader"]
            T14[search_skills]
            T15[load_skill]
        end
    end

    subgraph SWITCH["MDS 9710 Switch"]
        SW[NX-API REST endpoint]
    end

    U -->|reports issue| LLM
    LLM -->|searches and loads| SKILLS
    LLM -->|calls| TOOLS
    LIVE -->|REST API| SW
    LLM -->|delivers report| U

    style U fill:#4A90D9,color:#fff
    style LLM fill:#F5A623,color:#fff
    style S1 fill:#2ECC71,color:#fff
    style S2 fill:#2ECC71,color:#fff
    style S3 fill:#95A5A6,color:#fff
    style S4 fill:#95A5A6,color:#fff
    style SW fill:#E74C3C,color:#fff
```

> **15 tools**, **2 skills** (extensible), **1 LLM brain**, all orchestrated by the LangGraph ReAct loop. Skills tell the LLM *what to investigate*. Tools give it *live data*. The loop keeps going until the investigation is complete.

---

## 2. The Flow — "fc1/3 is flapping on lva1-mds01"

Here's exactly what happens when a user reports an interface issue:

```mermaid
sequenceDiagram
    participant User as Oncall Engineer
    participant LLM as LLM Brain
    participant SK as search_skills + load_skill
    participant T as 13 Data Tools
    participant MDS as MDS 9710

    User->>LLM: fc1/3 is flapping on lva1-mds01

    Note over LLM: Recognizes interface issue

    LLM->>SK: search_skills("interface")
    SK-->>LLM: Found: mds-interface-issues.md

    LLM->>SK: load_skill("mds-interface-issues.md")
    SK-->>LLM: 10-step investigation procedure

    Note over LLM: Now following the skill step by step

    rect rgb(230, 240, 255)
        Note over LLM,MDS: Phase 1 - Blast Radius
        LLM->>T: get_interface_status(lva1-mds01)
        T->>MDS: NX-API call
        MDS-->>T: 48 ports, 1 down
        T-->>LLM: fc1/3 down, rest healthy

        LLM->>T: get_flogi_database(lva1-mds01)
        T-->>LLM: fc1/3 missing from FLOGI

        LLM->>T: get_port_channel_summary(lva1-mds01)
        T-->>LLM: ISL healthy, 2/2 members up
    end

    rect rgb(255, 240, 230)
        Note over LLM,MDS: Phase 2 - Deep Triage
        LLM->>T: get_interface_detail(lva1-mds01, fc1/3)
        T-->>LLM: down, SFP present, 47 flaps

        LLM->>T: get_interface_counters(lva1-mds01, fc1/3)
        T-->>LLM: 892 CRC, 47 link failures, 3 signal losses

        LLM->>T: get_syslog_entries(lva1-mds01, fc1/3)
        T-->>LLM: 15 events - flap, CRC, link down

        LLM->>T: get_fcns_database(lva1-mds01)
        T-->>LLM: fc1/3 device missing from name server

        LLM->>T: get_vsan_status(lva1-mds01)
        T-->>LLM: VSAN 100 active

        LLM->>T: get_zone_status(lva1-mds01, vsan 100)
        T-->>LLM: 1 zone with offline member

        LLM->>T: get_device_health(lva1-mds01)
        T-->>LLM: CPU 12%, Memory 45%, healthy
    end

    rect rgb(230, 255, 230)
        Note over LLM,MDS: Phase 3 - Evidence + Report
        LLM->>T: load_show_tech(lva1-mds01, interfaces)
        T-->>LLM: SFP Rx Power -14.8 dBm NEAR THRESHOLD

        Note over LLM: Compiles all evidence
        LLM->>User: ESCALATION REPORT
    end

    Note over User: Root cause: Degraded SFP optics
    Note over User: Action: Replace SFP, clean fiber
    Note over User: Priority: P2, single path lost
```

**12 tool calls. 3 phases. 1 complete answer.** Every time, same investigation, same thoroughness.

---

## 3. With Skill vs Without Skill

```mermaid
flowchart LR
    subgraph WITH["With Skill"]
        direction TB
        W1[User: fc1/3 flapping] --> W2[Loads skill]
        W2 --> W3[Step 1: Blast radius\n3 tools called]
        W3 --> W4[Step 2-8: Deep triage\n8 tools called]
        W4 --> W5[Step 9: Show-tech\n1 tool called]
        W5 --> W6[Step 10: Full report\nroot cause + evidence]
    end

    subgraph WITHOUT["Without Skill"]
        direction TB
        N1[User: fc1/3 flapping] --> N2[LLM guesses]
        N2 --> N3[Checks interface status]
        N3 --> N4[Maybe checks counters]
        N4 --> N5[Partial answer\nno root cause]
    end

    style W1 fill:#4A90D9,color:#fff
    style W2 fill:#2ECC71,color:#fff
    style W3 fill:#7B68EE,color:#fff
    style W4 fill:#7B68EE,color:#fff
    style W5 fill:#7B68EE,color:#fff
    style W6 fill:#50C878,color:#fff

    style N1 fill:#4A90D9,color:#fff
    style N2 fill:#E74C3C,color:#fff
    style N3 fill:#E0E0E0,color:#333
    style N4 fill:#E0E0E0,color:#333
    style N5 fill:#E74C3C,color:#fff
```

| | With Skill | Without Skill |
|---|---|---|
| **Tools called** | 12 (all relevant) | 1-2 (random pick) |
| **Blast radius** | Always checked first | Skipped |
| **Root cause** | Identified with evidence | Guessed or missed |
| **SFP optics** | Checked via show-tech | Never looked |
| **FLOGI/Zone** | Verified fabric state | Skipped |
| **Report** | Structured escalation handoff | Partial text answer |
| **Consistency** | Same every time | Different every run |

---

## 3. Without Skill — LLM Wings It

```mermaid
flowchart TD
    A[User: fc1/3 is flapping] --> B[LLM guesses what to check]
    B --> C[Maybe checks interface status]
    C --> D[Maybe checks counters]
    D --> E[Gives partial answer]

    style A fill:#4A90D9,color:#fff
    style B fill:#E74C3C,color:#fff
    style C fill:#E0E0E0,color:#333
    style D fill:#E0E0E0,color:#333
    style E fill:#E74C3C,color:#fff
```

**What happens:**
- LLM has tools but **no procedure to follow**
- Picks 1-2 tools based on its training — random, not systematic
- **Skips:** FLOGI check, ISL impact, zone status, SFP optics, syslog correlation
- Gives a surface-level answer — misses root cause

**Result:** Incomplete, inconsistent. Different every time. Misses critical evidence.

---

## Side-by-Side Comparison

| | With Skill | Without Skill |
|---|---|---|
| **Tools called** | 10+ (all relevant) | 1-2 (random pick) |
| **Blast radius** | Always checked first | Skipped |
| **Root cause** | Identified with evidence | Guessed or missed |
| **Report** | Structured escalation handoff | Partial text answer |
| **Consistency** | Same every time | Different every run |
| **Oncall trust** | High — follows the procedure | Low — depends on luck |

---

## Key Concept

```
Skill = The investigation procedure (what to check, in what order)
Tool  = The data source (gets live data from the switch)
LLM   = The brain (reasons about results, follows the skill)

Skill tells the LLM WHAT to do.
Tools give the LLM DATA to work with.
Without a skill, the LLM has data but no plan.
```

---

*This agent is built for MDS 9710 interface issues. The same pattern works for any domain — write a skill, wire up tools, let the LLM follow the procedure.*

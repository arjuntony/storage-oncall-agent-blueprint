# How It Works — Agent Flow Explained

A simple guide to how the MDS Interface Triage Agent works, and why **skills** matter.

---

## 1. The Big Picture

```mermaid
flowchart LR
    A[User reports issue] --> B[LLM reasons about it]
    B --> C[Calls a tool]
    C --> D[Reads the result]
    D --> B
    B --> E[Delivers answer]

    style A fill:#4A90D9,color:#fff
    style B fill:#F5A623,color:#fff
    style C fill:#7B68EE,color:#fff
    style D fill:#7B68EE,color:#fff
    style E fill:#50C878,color:#fff
```

> **This is the ReAct loop.** The LLM *reasons* about what to do, *acts* by calling a tool, reads the result, and repeats until it has enough evidence to answer. LangGraph manages this loop.

---

## 2. With Skill — Structured Investigation

```mermaid
flowchart TD
    A[User: fc1/3 is flapping] --> B[LLM loads skill]
    B --> C[Follows Step 1: Blast radius]
    C --> D[Follows Step 2: ISL check]
    D --> E[Follows Step 3-8: Deep triage]
    E --> F[Follows Step 9: Show-tech fallback]
    F --> G[Step 10: Complete escalation report]

    style A fill:#4A90D9,color:#fff
    style B fill:#F5A623,color:#fff
    style C fill:#7B68EE,color:#fff
    style D fill:#7B68EE,color:#fff
    style E fill:#7B68EE,color:#fff
    style F fill:#7B68EE,color:#fff
    style G fill:#50C878,color:#fff
```

**What happens:**
- LLM searches for and loads the right skill (a step-by-step procedure)
- Follows **every step in order** — blast radius, triage, evidence collection
- Calls **10+ tools** systematically — nothing skipped
- Produces a **complete escalation report** with root cause, evidence, and recommended actions

**Result:** Same thorough investigation every time, regardless of who runs it or which LLM model is used.

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

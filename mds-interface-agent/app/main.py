"""Streamlit chat interface for MDS 9710 Interface Triage Agent."""

import json
import time
import uuid

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from app.config import DEMO_MODE, LLM_PROVIDER, MODEL_NAME

st.set_page_config(page_title="MDS Interface Triage Agent", page_icon="🔴", layout="wide")

st.title("MDS 9710 Interface Triage Agent")

if DEMO_MODE:
    st.caption("DEMO MODE — running tools locally, no Claude API needed. Add ANTHROPIC_API_KEY to .env for full agent mode.")
else:
    st.caption("AGENT MODE — Claude follows investigation skills autonomously")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

# Only create agent in non-demo mode
if not DEMO_MODE and "agent" not in st.session_state:
    from app.agent import create_agent
    st.session_state.agent = create_agent()

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    if DEMO_MODE:
        st.warning("DEMO MODE — No API key")
    else:
        provider = "OpenAI" if LLM_PROVIDER == "openai" else "Anthropic"
        st.success(f"AGENT MODE — {provider}\n\nModel: `{MODEL_NAME}`")

    st.header("Quick Actions")
    if st.button("🔥 Triage fc1/3 on lva1-mds01"):
        st.session_state.quick_action = "triage_fc1_3"
    if st.button("📊 All port status — lva1-mds01"):
        st.session_state.quick_action = "port_status"
    if st.button("🔍 Check FLOGI database"):
        st.session_state.quick_action = "flogi"
    if st.button("💚 Device health check"):
        st.session_state.quick_action = "health"
    if st.button("🔗 ISL port-channels"):
        st.session_state.quick_action = "isl"
    if st.button("📜 Syslog for fc1/3"):
        st.session_state.quick_action = "syslog"
    if st.button("📁 Show-tech sections"):
        st.session_state.quick_action = "showtech"

    st.divider()
    if st.button("🗑 New Conversation"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.header("Tools (15)")
    st.markdown("""
    **Live (NX-API):** `get_interface_status`, `get_interface_detail`,
    `get_interface_counters`, `get_flogi_database`, `get_fcns_database`,
    `get_fspf_neighbors`, `get_port_channel_summary`, `get_vsan_status`,
    `get_zone_status`, `get_device_health`, `get_module_status`

    **Streaming:** `get_syslog_entries`

    **Offline:** `load_show_tech`

    **Skills:** `search_skills`, `load_skill`
    """)

# ── Chat history display ────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    elif msg["role"] == "assistant":
        with st.chat_message("assistant"):
            st.markdown(msg["content"])
    elif msg["role"] == "tool":
        with st.chat_message("assistant", avatar="🔧"):
            st.caption(f"Tool: {msg.get('tool_name', 'unknown')}")
            with st.expander("Tool result", expanded=False):
                st.code(msg["content"][:3000], language="json")

def _run_demo(quick, user_input):
    """Demo mode — run tools directly, no Claude."""
    from tools.mds_live import (
        get_interface_status, get_interface_detail, get_interface_counters,
        get_flogi_database, get_fcns_database, get_fspf_neighbors,
        get_port_channel_summary, get_vsan_status, get_zone_status,
        get_device_health, get_module_status,
    )
    from tools.syslog import get_syslog_entries
    from tools.show_tech import load_show_tech

    hostname = "lva1-mds01"

    if quick == "triage_fc1_3":
        label = f"Triage fc1/3 on {hostname} — full 10-step investigation"
    elif quick == "port_status":
        label = f"Show all interface status on {hostname}"
    elif quick == "flogi":
        label = f"Show FLOGI database on {hostname}"
    elif quick == "health":
        label = f"Run health check on {hostname}"
    elif quick == "isl":
        label = f"Check ISL port-channels on {hostname}"
    elif quick == "syslog":
        label = f"Show syslog for fc1/3 on {hostname}"
    elif quick == "showtech":
        label = f"Show available show-tech sections for {hostname}"
    else:
        label = user_input or "Unknown query"

    st.session_state.messages.append({"role": "user", "content": label})
    with st.chat_message("user"):
        st.write(label)

    with st.chat_message("assistant"):
        status = st.empty()

        if quick == "triage_fc1_3":
            # Full 10-step investigation
            from app.demo import run_demo_triage

            def on_step(step_name, tool_name):
                status.info(f"🔧 **{step_name}** → calling `{tool_name}`")
                time.sleep(0.3)

            steps, report = run_demo_triage(hostname, "fc1/3", status_callback=on_step)

            status.empty()

            # Show tool calls
            for s in steps:
                st.session_state.messages.append({
                    "role": "tool",
                    "tool_name": s["tool"],
                    "content": json.dumps(s["result"], indent=2, default=str)[:3000],
                })

            st.markdown(report)
            st.session_state.messages.append({"role": "assistant", "content": report})
            st.caption(f"Tools used: {', '.join(s['tool'] for s in steps)}")

        elif quick == "port_status":
            status.info("🔧 Calling `get_interface_status`...")
            result = get_interface_status.invoke({"hostname": hostname})
            status.empty()
            _show_tool_result("get_interface_status", result)
            _format_interface_table(result)

        elif quick == "flogi":
            status.info("🔧 Calling `get_flogi_database`...")
            result = get_flogi_database.invoke({"hostname": hostname})
            status.empty()
            _show_tool_result("get_flogi_database", result)
            md = f"**FLOGI Database — {hostname}** ({result['flogi_count']} entries)\n\n"
            md += "| Interface | VSAN | FCID | Port WWN | Device Alias |\n"
            md += "|-----------|------|------|----------|-------------|\n"
            for e in result["entries"]:
                md += f"| {e['interface']} | {e['vsan']} | {e['fcid']} | {e['port_wwn']} | {e['device_alias']} |\n"
            md += f"\n⚠ **Note:** fc1/3 has NO FLOGI entry — device not logged into fabric."
            st.markdown(md)
            st.session_state.messages.append({"role": "assistant", "content": md})

        elif quick == "health":
            status.info("🔧 Calling `get_device_health`...")
            result = get_device_health.invoke({"hostname": hostname})
            status.empty()
            _show_tool_result("get_device_health", result)
            md = f"**Device Health — {hostname}**\n\n"
            md += f"| Metric | Value | Status |\n|--------|-------|--------|\n"
            md += f"| CPU (1-min) | {result['cpu_1min']}% | {'OK' if result['cpu_1min'] < 60 else 'HIGH'} |\n"
            md += f"| CPU (5-min) | {result['cpu_5min']}% | {'OK' if result['cpu_5min'] < 50 else 'HIGH'} |\n"
            md += f"| Memory | {result['memory_used_percent']}% | {'OK' if result['memory_used_percent'] < 75 else 'HIGH'} |\n"
            md += f"| Uptime | {result['uptime_days']} days | — |\n"
            md += f"\n**Verdict: {result['verdict']}**\n"
            for f in result["findings"]:
                md += f"\n- {f}"
            st.markdown(md)
            st.session_state.messages.append({"role": "assistant", "content": md})

        elif quick == "isl":
            status.info("🔧 Calling `get_port_channel_summary`...")
            result = get_port_channel_summary.invoke({"hostname": hostname})
            status.empty()
            _show_tool_result("get_port_channel_summary", result)
            pc = result["port_channels"][0]
            md = f"**ISL Port-Channel — {hostname}**\n\n"
            md += f"- **{pc['port_channel']}**: {pc['oper_status']}, {pc['speed']}\n"
            md += f"- Peer: {pc['peer_switch']}\n"
            md += f"- VSAN trunking: {pc['vsan_trunking']}\n"
            md += f"- Members: {pc['active_members']}/{pc['total_members']} active\n\n"
            for m in pc["members"]:
                md += f"  - {m['interface']}: {m['status']} ({m['speed']})\n"
            if result["alerts"]:
                md += f"\n⚠ Alerts: {', '.join(result['alerts'])}"
            else:
                md += "\n✓ All ISL members healthy"
            st.markdown(md)
            st.session_state.messages.append({"role": "assistant", "content": md})

        elif quick == "syslog":
            status.info("🔧 Calling `get_syslog_entries`...")
            result = get_syslog_entries.invoke({"hostname": hostname, "keyword": "fc1/3", "hours": 1})
            status.empty()
            _show_tool_result("get_syslog_entries", result)
            md = f"**Syslog — {hostname} — fc1/3** ({result['count']} entries)\n\n"
            md += "| Time | Severity | Message |\n|------|----------|--------|\n"
            for e in result["entries"][:15]:
                md += f"| {e['timestamp']} | {e['severity']} | {e['message'][:80]} |\n"
            st.markdown(md)
            st.session_state.messages.append({"role": "assistant", "content": md})

        elif quick == "showtech":
            status.info("🔧 Calling `load_show_tech`...")
            result = load_show_tech.invoke({"hostname": hostname})
            status.empty()
            _show_tool_result("load_show_tech", result)
            md = f"**Show-Tech Sections — {hostname}**\n\n"
            for s in result["available_sections"]:
                md += f"- `{s}`\n"
            md += f"\n{result['total_sections']} sections available. Click a quick action or ask to load a specific section."
            st.markdown(md)
            st.session_state.messages.append({"role": "assistant", "content": md})

        else:
            st.info("In demo mode, use the Quick Action buttons on the left. For free-text queries, add an ANTHROPIC_API_KEY to .env.")
            st.session_state.messages.append({"role": "assistant", "content": "Use Quick Action buttons for demo mode."})


def _show_tool_result(tool_name, result):
    """Add tool result to session and show expandable."""
    content = json.dumps(result, indent=2, default=str)[:3000]
    st.session_state.messages.append({"role": "tool", "tool_name": tool_name, "content": content})


def _format_interface_table(result):
    """Format interface status as a nice table."""
    md = f"**Interface Status — {result['hostname']}** ({result['model']}, {result['firmware']})\n\n"
    md += f"Ports: {result['summary']['up']} up / {result['summary']['down']} down / {result['summary']['total']} total\n\n"
    md += "| Interface | Status | Mode | Speed | VSAN | Connected Device |\n"
    md += "|-----------|--------|------|-------|------|------------------|\n"
    for i in result["interfaces"]:
        status_icon = "🟢" if i["oper_status"] == "up" else "🔴"
        md += (f"| {i['interface']} | {status_icon} {i['oper_status']} | {i['port_mode']} | "
               f"{i['speed']} | {i['vsan']} | {i['connected_device']} |\n")
    if result["alerts"]:
        md += "\n**Alerts:**\n"
        for a in result["alerts"]:
            md += f"- ⚠ {a}\n"
    st.markdown(md)
    st.session_state.messages.append({"role": "assistant", "content": md})


def _run_agent(quick, user_input):
    """Agent mode — Claude follows skills autonomously."""
    action_map = {
        "triage_fc1_3": "fc1/3 on lva1-mds01 is flapping — 47 flaps and CRC errors. Investigate using the interface triage skill and produce an escalation report.",
        "port_status": "Show me all interface status on lva1-mds01",
        "flogi": "Show FLOGI database on lva1-mds01",
        "health": "Run a full health check on lva1-mds01",
        "isl": "Check ISL port-channel status on lva1-mds01",
        "syslog": "Show syslog entries for fc1/3 on lva1-mds01 last 1 hour",
        "showtech": "List show-tech sections available for lva1-mds01",
    }

    text = action_map.get(quick, user_input or "")
    if not text:
        return

    st.session_state.messages.append({"role": "user", "content": text})
    with st.chat_message("user"):
        st.write(text)

    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        response_placeholder = st.empty()
        full_response = ""
        tool_calls_made = []

        try:
            for event in st.session_state.agent.stream(
                {"messages": [HumanMessage(content=text)]},
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
                                "role": "tool", "tool_name": message.name,
                                "content": str(message.content)[:3000],
                            })
                        elif isinstance(message, AIMessage) and message.content and not message.tool_calls:
                            full_response = message.content

            status_placeholder.empty()
            if full_response:
                response_placeholder.markdown(full_response)
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            if tool_calls_made:
                st.caption(f"Tools used: {', '.join(tool_calls_made)}")

        except Exception as e:
            st.error(f"Error: {e}")


# ── Handle input (must be after function definitions) ────────
quick = st.session_state.pop("quick_action", None)
user_input = st.chat_input("Describe the MDS interface issue...")

if quick or user_input:
    if DEMO_MODE:
        _run_demo(quick, user_input)
    else:
        _run_agent(quick, user_input)

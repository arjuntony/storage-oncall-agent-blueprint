"""Syslog query tool — synthetic data for POC.

In production, this queries your syslog server (Splunk, ELK, rsyslog)
via API or file read. MDS sends syslog automatically on every event.
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
         "message": "fc1/3: Link failure count 47 in last 24 hours"},
        {"timestamp": "2026-04-12T06:30:00Z", "facility": "FSPF",
         "severity": "INFO", "message": "VSAN 100: FSPF neighbor lva1-mds02 is FULL"},
    ],
}


@tool
def get_syslog_entries(hostname: str, keyword: str = "", hours: int = 1) -> dict:
    """Get syslog entries for an MDS switch — filtered by keyword and time window.

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        keyword: Filter keyword in message (e.g. fc1/3, link_failure). Empty = all.
        hours: Lookback window in hours (default 1)
    """
    entries = SYNTHETIC_SYSLOG.get(hostname, [])
    if not entries:
        return {"error": f"No syslog data for '{hostname}'"}
    if keyword:
        keyword_lower = keyword.lower()
        entries = [e for e in entries if keyword_lower in e["message"].lower()]
    return {"hostname": hostname, "filter": {"keyword": keyword or "(none)", "hours": hours},
            "entries": entries, "count": len(entries)}

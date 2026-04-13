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
    # LIVE: MDS NX-API tools
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
    # STREAMING: Syslog
    get_syslog_entries,
    # OFFLINE: Show-tech files
    load_show_tech,
    # SKILLS: Investigation procedures
    search_skills,
    load_skill,
]

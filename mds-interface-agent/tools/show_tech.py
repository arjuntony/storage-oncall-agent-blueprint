"""Show-tech-support loader — reads pre-collected files from disk.

TWO-STEP LOADING:
  1. load_show_tech(hostname) -> section list only
  2. load_show_tech(hostname, "interfaces") -> one section content
"""

from pathlib import Path
from langchain_core.tools import tool

SYNTHETIC_SHOW_TECH = {
    "lva1-mds01": {
        "interfaces": """
`show interface fc1/1`
fc1/1 is up
  Hardware is Fibre Channel, SFP is short wave laser
  Port WWN is 20:01:00:0d:ec:6a:30:01
  Port mode is F, FCID is 0x610001, Port vsan is 100
  Speed is 32 Gbps
  Transmit B2B Credit is 16, Receive B2B Credit is 16
    48523019 frames input, 32105890234 bytes
    51203847 frames output, 34201290112 bytes
    0 CRC errors, 0 link failures, 0 sync losses, 0 signal losses

`show interface fc1/3`
fc1/3 is down (link_failure)
  Hardware is Fibre Channel, SFP is short wave laser
  Port WWN is 20:03:00:0d:ec:6a:30:01
  Port mode is F, Port vsan is 100
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
""",
        "vsan": """
`show vsan`
vsan 1 information
  name: default, state: active
  interoperability mode: default

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
  PS1: ok, 3000W AC    PS2: ok, 3000W AC
  PS3: ok, 3000W AC    PS4: ok, 3000W AC
Fan:
  Fan1: ok, 4200 RPM   Fan2: ok, 4150 RPM   Fan3: ok, 4180 RPM
Temperature:
  Inlet: 28.5C   Sup1: 42.0C   Sup2: 41.5C   Module3: 48.2C

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
2026-04-12T07:30:00 %PORT-2-CRC_THRESHOLD: fc1/3 CRC error threshold exceeded (892 errors)
2026-04-12T07:00:00 %PORT-4-LINK_FAILURE_COUNT: fc1/3 link failure count 47 in last 24h
2026-04-12T06:30:00 %FSPF-5-NBRCHANGE: VSAN 100 FSPF neighbor lva1-mds02 changed to FULL state
""",
        "fspf": """
`show fspf database vsan 100`
FSPF Routing Database for VSAN 100
  Local Domain ID: 1 (lva1-mds01)
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
  2 ports in total, 2 ports up
  Member fc1/47: up (P — bundled, active)
  Member fc1/48: up (P — bundled, active)
""",
    },
}


@tool
def load_show_tech(hostname: str, section: str = "") -> dict:
    """Load show-tech-support data from pre-collected files on disk.

    TWO-STEP LOADING:
      Step 1: Call with hostname only -> returns list of available sections
      Step 2: Call with hostname + section -> returns that section's content

    Args:
        hostname: MDS switch hostname (e.g. lva1-mds01)
        section: Section to load (e.g. 'interfaces', 'flogi'). Omit to list sections.
    """
    host_data = SYNTHETIC_SHOW_TECH.get(hostname)
    if not host_data:
        return {"error": f"No show-tech data for '{hostname}'",
                "available_hosts": list(SYNTHETIC_SHOW_TECH.keys())}

    if not section:
        return {
            "hostname": hostname,
            "available_sections": list(host_data.keys()),
            "total_sections": len(host_data),
            "instruction": "Call load_show_tech again with a specific section name to load its content.",
        }

    content = host_data.get(section)
    if not content:
        return {"error": f"Section '{section}' not found",
                "available_sections": list(host_data.keys())}

    return {"hostname": hostname, "section": section, "content": content.strip()}

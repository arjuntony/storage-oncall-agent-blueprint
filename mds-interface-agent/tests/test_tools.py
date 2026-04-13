"""Unit tests for all MDS tools."""

from tools.mds_live import (
    get_interface_status, get_interface_detail, get_interface_counters,
    get_flogi_database, get_fcns_database, get_fspf_neighbors,
    get_port_channel_summary, get_vsan_status, get_zone_status,
    get_device_health, get_module_status,
)
from tools.syslog import get_syslog_entries
from tools.show_tech import load_show_tech


class TestInterfaceTools:
    def test_get_all_interfaces(self):
        result = get_interface_status.invoke({"hostname": "lva1-mds01"})
        assert result["hostname"] == "lva1-mds01"
        assert result["summary"]["down"] >= 1

    def test_get_interface_detail(self):
        result = get_interface_detail.invoke({"hostname": "lva1-mds01", "interface": "fc1/3"})
        assert result["interface"]["oper_status"] == "down"

    def test_get_counters_critical(self):
        result = get_interface_counters.invoke({"hostname": "lva1-mds01", "interface": "fc1/3"})
        assert result["severity"] == "CRITICAL"
        assert result["counters"]["crc_errors"] == 892

    def test_get_counters_healthy(self):
        result = get_interface_counters.invoke({"hostname": "lva1-mds01", "interface": "fc1/1"})
        assert result["severity"] == "OK"

    def test_unknown_host(self):
        result = get_interface_status.invoke({"hostname": "unknown"})
        assert "error" in result


class TestFabricTools:
    def test_flogi_missing_fc1_3(self):
        result = get_flogi_database.invoke({"hostname": "lva1-mds01"})
        interfaces = [e["interface"] for e in result["entries"]]
        assert "fc1/3" not in interfaces

    def test_fcns(self):
        result = get_fcns_database.invoke({"hostname": "lva1-mds01"})
        assert result["initiators"] == 3
        assert result["targets"] == 3

    def test_fspf_full(self):
        result = get_fspf_neighbors.invoke({"hostname": "lva1-mds01"})
        assert result["all_full"] is True

    def test_port_channel_healthy(self):
        result = get_port_channel_summary.invoke({"hostname": "lva1-mds01"})
        assert result["port_channels"][0]["active_members"] == 2


class TestVSANZoneTools:
    def test_vsan_active(self):
        result = get_vsan_status.invoke({"hostname": "lva1-mds01"})
        assert len(result["alerts"]) == 0

    def test_zone_offline_member(self):
        result = get_zone_status.invoke({"hostname": "lva1-mds01", "vsan": 100})
        assert result["zones_with_offline_members"] == 1


class TestHealthTools:
    def test_health_not_critical(self):
        result = get_device_health.invoke({"hostname": "lva1-mds01"})
        assert result["verdict"] in ("OK", "DEGRADED")
        assert result["cpu_1min"] < 60

    def test_modules(self):
        result = get_module_status.invoke({"hostname": "lva1-mds01"})
        assert any(m["status"] == "active" for m in result["modules"])


class TestSyslog:
    def test_filter_fc1_3(self):
        result = get_syslog_entries.invoke({"hostname": "lva1-mds01", "keyword": "fc1/3"})
        assert result["count"] > 0


class TestShowTech:
    def test_list_sections(self):
        result = load_show_tech.invoke({"hostname": "lva1-mds01"})
        assert "interfaces" in result["available_sections"]

    def test_load_section(self):
        result = load_show_tech.invoke({"hostname": "lva1-mds01", "section": "interfaces"})
        assert "892 CRC errors" in result["content"]

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from pathlib import Path

from analyzer.analyzer import analyze_config, summarize_network_state
from analyzer.parser import detect_vendor, parse_device_text
from analyzer.report import build_html_report, build_text_report
from analyzer.visualize import build_topology, draw_topology


HUAWEI_SAMPLE = """
# Huawei configuration
bgp 65001
 peer 10.0.0.2 as-number 65002
 peer 10.0.0.3
quit
interface GigabitEthernet0/0/1
 description Uplink-Core
 ip address 192.168.1.1 255.255.255.0
 ospf enable
 vrrp vrid 1 virtual-ip 192.168.1.254 priority 120 preempt-mode
quit
interface GigabitEthernet0/0/2
 ip address 10.10.10.1 255.255.255.0
 shutdown
 vrrp vrid 2 priority 300
quit
ospf 1
 area 0.0.0.0
 network 192.168.1.0 0.0.0.255
quit
BGP neighbor 10.0.0.2 state Established uptime 3d
OSPF neighbor 2.2.2.2 state Full uptime 12h
Interface GigabitEthernet0/0/1 line-protocol up
Total routes: 200 Direct: 50 Static: 40 BGP: 80 OSPF: 30
"""


CISCO_SAMPLE = """
show running-config
router bgp 65100
 neighbor 172.16.0.2 remote-as 65200
exit
router ospf 10
 network 172.16.0.0 0.0.0.255 area 0
exit
interface GigabitEthernet0/1
 description TO-CORE
 ip address 172.16.0.1 255.255.255.0
 no shutdown
 vrrp 1 ip 172.16.0.254
 vrrp 1 priority 110
 ip ospf 10 area 0
exit
BGP neighbor 172.16.0.2 state Idle uptime 0
OSPF neighbor 3.3.3.3 state Init uptime 2m
Interface GigabitEthernet0/1 line-protocol down
Total routes: 120 Direct: 30 Static: 20 BGP: 50 OSPF: 20
"""


def test_huawei_full_pipeline() -> None:
    parsed = parse_device_text(HUAWEI_SAMPLE, "Station-R1")
    findings = analyze_config(parsed)
    topology = build_topology(parsed)
    summary = summarize_network_state(parsed)

    assert parsed.vendor == "huawei"
    assert parsed.local_as == 65001
    assert len(parsed.bgp_neighbors) == 2
    assert summary["routing"]["total"] == 200

    finding_types = {f["type"] for f in findings}
    assert "bgp_missing_remote_as" in finding_types
    assert "interface_shutdown_with_ip" in finding_types
    assert "vrrp_invalid_priority" in finding_types
    assert "vrrp_missing_virtual_ip" in finding_types

    assert topology["nodes"]
    assert any(l["relation"] == "bgp_neighbor" for l in topology["links"])


def test_cisco_pipeline_and_runtime_state() -> None:
    parsed = parse_device_text(CISCO_SAMPLE, "Station-R2")
    findings = analyze_config(parsed)
    summary = summarize_network_state(parsed)

    assert parsed.vendor == "cisco"
    assert parsed.local_as == 65100
    assert parsed.bgp_neighbors[0]["state"] == "idle"
    assert summary["protocol"]["bgp"]["abnormal"] == 1

    finding_types = {f["type"] for f in findings}
    assert "bgp_neighbor_not_established" in finding_types
    assert "ospf_neighbor_abnormal" in finding_types
    assert "interface_protocol_down" in finding_types


def test_detect_vendor() -> None:
    assert detect_vendor("display current-configuration\ninterface Vlanif10") == "huawei"
    assert detect_vendor("show running-config\nrouter bgp 65000") == "cisco"
    assert detect_vendor("system-view\ninterface Vlan-interface10") == "h3c"


def test_html_report_contains_sections() -> None:
    parsed = parse_device_text(HUAWEI_SAMPLE, "Station-R1")
    payload = {
        "parsed": {
            "device_name": parsed.device_name,
            "vendor": parsed.vendor,
            "local_as": parsed.local_as,
        },
        "summary": summarize_network_state(parsed),
        "findings": analyze_config(parsed),
        "topology": build_topology(parsed),
    }
    html = build_html_report(payload)
    assert "站场网络配置智能分析报告" in html
    assert "综合状态" in html
    assert "异常与非标准化提示" in html


def test_cli_generates_json_and_html(tmp_path: Path) -> None:
    cfg = tmp_path / "sample.txt"
    out_json = tmp_path / "result.json"
    out_html = tmp_path / "report.html"
    cfg.write_text(CISCO_SAMPLE, encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "main.py",
            "--device-name",
            "Station-R2",
            "--config-file",
            str(cfg),
            "--output",
            str(out_json),
            "--report-html",
            str(out_html),
            "--vendor",
            "auto",
        ],
        check=True,
    )

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["parsed"]["vendor"] == "cisco"
    assert out_html.exists()
    assert "站场网络配置智能分析报告" in out_html.read_text(encoding="utf-8")


def test_text_report_and_topology_image(tmp_path: Path) -> None:
    parsed = parse_device_text(HUAWEI_SAMPLE, "Station-R1")
    payload = {
        "parsed": {
            "device_name": parsed.device_name,
            "vendor": parsed.vendor,
            "local_as": parsed.local_as,
        },
        "summary": summarize_network_state(parsed),
        "findings": analyze_config(parsed),
        "topology": build_topology(parsed),
    }

    txt = build_text_report(payload)
    assert "网络配置智能分析报告" in txt

    out_png = tmp_path / "topology.png"
    try:
        saved = draw_topology(parsed, output_path=out_png, show=False)
    except RuntimeError:
        pytest.skip("matplotlib/networkx not installed in test environment")
    assert saved is not None
    assert out_png.exists()

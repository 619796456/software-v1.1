from __future__ import annotations

from analyzer.analyzer import analyze_config, summarize_network_state
from analyzer.parser import parse_device_text
from analyzer.visualize import build_topology


def run_pipeline(text: str, device_name: str, vendor: str | None = None) -> dict:
    parsed = parse_device_text(text=text, device_name=device_name, vendor=vendor)
    findings = analyze_config(parsed)
    topology = build_topology(parsed)
    summary = summarize_network_state(parsed)

    return {
        "parsed": {
            "device_name": parsed.device_name,
            "vendor": parsed.vendor,
            "local_as": parsed.local_as,
            "interfaces": {
                k: {
                    "description": v.description,
                    "ip_address": v.ip_address,
                    "vlan": v.vlan,
                    "shutdown": v.shutdown,
                    "line_protocol_up": v.line_protocol_up,
                    "ospf_enabled": v.ospf_enabled,
                    "vrrp_groups": v.vrrp_groups,
                }
                for k, v in parsed.interfaces.items()
            },
            "bgp_neighbors": parsed.bgp_neighbors,
            "ospf_processes": parsed.ospf_processes,
            "ospf_neighbors": parsed.ospf_neighbors,
            "route_stats": parsed.route_stats,
        },
        "summary": summary,
        "findings": findings,
        "topology": topology,
    }

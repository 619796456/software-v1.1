from __future__ import annotations

from analyzer.parser import ParsedConfig


def _route_stats(parsed: ParsedConfig) -> dict:
    stats = dict(parsed.route_stats)
    stats.setdefault("total", 0)
    stats.setdefault("direct", 0)
    stats.setdefault("static", 0)
    stats.setdefault("bgp", 0)
    stats.setdefault("ospf", 0)
    return stats


def summarize_network_state(parsed: ParsedConfig) -> dict:
    interface_total = len(parsed.interfaces)
    shutdown_count = sum(1 for i in parsed.interfaces.values() if i.shutdown)
    line_down_count = sum(1 for i in parsed.interfaces.values() if i.line_protocol_up is False)
    down_or_shutdown = shutdown_count + line_down_count

    bgp_total = len(parsed.bgp_neighbors)
    bgp_established = sum(1 for n in parsed.bgp_neighbors if n.get("state") == "established")

    ospf_total = len(parsed.ospf_neighbors)
    ospf_full = sum(1 for n in parsed.ospf_neighbors if n.get("state") in {"full", "2-way"})

    # 兼容旧结构(interface) + 新结构(basic/interfaces)，避免GUI/报告不一致
    return {
        "vendor": parsed.vendor,
        "basic": {"interface_count": interface_total},
        "interfaces": {
            "total": interface_total,
            "shutdown": shutdown_count,
            "line_protocol_down": line_down_count,
            "down_or_shutdown": down_or_shutdown,
            "up": max(interface_total - max(shutdown_count, line_down_count), 0),
        },
        "interface": {
            "total": interface_total,
            "shutdown": shutdown_count,
            "line_protocol_down": line_down_count,
            "up": max(interface_total - max(shutdown_count, line_down_count), 0),
        },
        "protocol": {
            "bgp": {"total": bgp_total, "established": bgp_established, "abnormal": max(bgp_total - bgp_established, 0)},
            "ospf": {"total": ospf_total, "healthy": ospf_full, "abnormal": max(ospf_total - ospf_full, 0)},
        },
        "routing": _route_stats(parsed),
    }


def analyze_config(parsed: ParsedConfig) -> list[dict]:
    findings: list[dict] = []

    for intf in parsed.interfaces.values():
        if intf.ip_address and intf.shutdown:
            findings.append(
                {
                    "severity": "high",
                    "type": "interface_shutdown_with_ip",
                    "message": f"接口 {intf.name} 配置了 IP({intf.ip_address}) 但处于 shutdown 状态",
                }
            )

        if intf.line_protocol_up is False and not intf.shutdown:
            findings.append(
                {
                    "severity": "medium",
                    "type": "interface_protocol_down",
                    "message": f"接口 {intf.name} 管理状态 up，但协议状态 down",
                }
            )

        if not intf.description:
            findings.append(
                {
                    "severity": "low",
                    "type": "interface_missing_description",
                    "message": f"接口 {intf.name} 缺少 description，建议补充链路用途",
                }
            )

        for vrrp in intf.vrrp_groups:
            if not vrrp.get("virtual_ip"):
                findings.append(
                    {
                        "severity": "high",
                        "type": "vrrp_missing_virtual_ip",
                        "message": f"接口 {intf.name} 的 VRRP 组 {vrrp.get('vrid')} 缺少 virtual-ip",
                    }
                )
            pri = vrrp.get("priority", 100)
            if not isinstance(pri, int) or pri < 1 or pri > 254:
                findings.append(
                    {
                        "severity": "medium",
                        "type": "vrrp_invalid_priority",
                        "message": f"接口 {intf.name} 的 VRRP 组 {vrrp.get('vrid')} 优先级异常: {pri}",
                    }
                )
            if vrrp.get("state") in {"initialize", "fault", "down"}:
                findings.append(
                    {
                        "severity": "medium",
                        "type": "vrrp_abnormal_state",
                        "message": f"接口 {intf.name} 的 VRRP 组 {vrrp.get('vrid')} 状态异常: {vrrp.get('state')}",
                    }
                )

    for n in parsed.bgp_neighbors:
        if n["remote_as"] is None:
            findings.append(
                {
                    "severity": "high",
                    "type": "bgp_missing_remote_as",
                    "message": f"BGP 邻居 {n['peer_ip']} 缺失 remote-as",
                }
            )
        if not n["enabled"]:
            findings.append(
                {
                    "severity": "medium",
                    "type": "bgp_neighbor_not_enabled",
                    "message": f"BGP 邻居 {n['peer_ip']} 未启用",
                }
            )
        if n.get("state") not in {"established", "unknown"}:
            findings.append(
                {
                    "severity": "high",
                    "type": "bgp_neighbor_not_established",
                    "message": f"BGP 邻居 {n['peer_ip']} 状态异常: {n.get('state')}, uptime={n.get('uptime')}",
                }
            )

    for n in parsed.ospf_neighbors:
        if n.get("state") not in {"full", "2-way"}:
            findings.append(
                {
                    "severity": "medium",
                    "type": "ospf_neighbor_abnormal",
                    "message": f"OSPF 邻居 {n.get('neighbor_id')} 状态异常: {n.get('state')}, uptime={n.get('uptime')}",
                }
            )

    if parsed.local_as is None:
        findings.append(
            {
                "severity": "high",
                "type": "bgp_local_as_missing",
                "message": "未识别到本地 BGP AS 号",
            }
        )

    return findings

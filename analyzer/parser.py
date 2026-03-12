from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field


@dataclass
class InterfaceConfig:
    name: str
    description: str | None = None
    ip_address: str | None = None
    vlan: int | None = None
    shutdown: bool = False
    line_protocol_up: bool | None = None
    ospf_enabled: bool = False
    vrrp_groups: list[dict] = field(default_factory=list)


@dataclass
class ParsedConfig:
    device_name: str
    vendor: str
    local_as: int | None = None
    interfaces: dict[str, InterfaceConfig] = field(default_factory=dict)
    bgp_neighbors: list[dict] = field(default_factory=list)
    ospf_processes: list[dict] = field(default_factory=list)
    ospf_neighbors: list[dict] = field(default_factory=list)
    route_stats: dict[str, int] = field(default_factory=dict)


def detect_vendor(text: str) -> str:
    lower = text.lower()
    if "huawei" in lower or "display current-configuration" in lower:
        return "huawei"
    if "h3c" in lower or "system-view" in lower:
        return "h3c"
    if "cisco" in lower or "show running-config" in lower or "router bgp" in lower:
        return "cisco"

    if "router bgp" in lower or "ip ospf" in lower:
        return "cisco"
    if "vrrp vrid" in lower or "undo shutdown" in lower:
        return "huawei"
    if "vlan-interface" in lower:
        return "h3c"
    return "unknown"


def _normalize_valid_ip_neighbors(neighbors: list[dict]) -> list[dict]:
    valid = []
    for n in neighbors:
        try:
            ipaddress.ip_address(n["peer_ip"])
            valid.append(n)
        except ValueError:
            continue
    return valid


def _parse_route_summary(line: str, parsed: ParsedConfig) -> None:
    # 支持多种设备摘要表达
    candidates = {
        "total": [r"total routes?\s*[:=]\s*(\d+)", r"ip routing table\s*.*?(\d+)\s+routes"],
        "direct": [r"direct(?:ly connected)?\s*[:=]\s*(\d+)"],
        "static": [r"static\s*[:=]\s*(\d+)"],
        "bgp": [r"bgp\s*[:=]\s*(\d+)"],
        "ospf": [r"ospf\s*[:=]\s*(\d+)"],
    }
    lower = line.lower()
    for key, patterns in candidates.items():
        for p in patterns:
            m = re.search(p, lower)
            if m:
                parsed.route_stats[key] = int(m.group(1))


def _parse_huawei_h3c(text: str, device_name: str, vendor: str) -> ParsedConfig:
    parsed = ParsedConfig(device_name=device_name, vendor=vendor)
    section: str | None = None
    current_intf: InterfaceConfig | None = None
    current_ospf: dict | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        _parse_route_summary(line, parsed)

        if line.startswith("interface "):
            section = "interface"
            name = line.split(maxsplit=1)[1]
            current_intf = InterfaceConfig(name=name)
            parsed.interfaces[name] = current_intf
            continue

        if line.startswith("bgp "):
            section = "bgp"
            try:
                parsed.local_as = int(line.split()[1])
            except (ValueError, IndexError):
                parsed.local_as = None
            continue

        if line.startswith("ospf "):
            section = "ospf"
            pid = line.split()[1] if len(line.split()) > 1 else "1"
            current_ospf = {"process_id": int(pid) if pid.isdigit() else pid, "areas": [], "networks": []}
            parsed.ospf_processes.append(current_ospf)
            continue

        if line in {"quit", "return"}:
            section = None
            current_intf = None
            current_ospf = None
            continue

        if section == "interface" and current_intf:
            if line.startswith("description "):
                current_intf.description = line.removeprefix("description ").strip()
            elif line.startswith("ip address "):
                parts = line.split()
                if len(parts) >= 3:
                    current_intf.ip_address = parts[2]
            elif line.startswith("port default vlan "):
                try:
                    current_intf.vlan = int(line.split()[-1])
                except ValueError:
                    pass
            elif line == "shutdown":
                current_intf.shutdown = True
            elif line == "undo shutdown":
                current_intf.shutdown = False
            elif line.startswith("ospf enable"):
                current_intf.ospf_enabled = True
            elif line.startswith("vrrp vrid"):
                parts = line.split()
                group = {"vrid": None, "virtual_ip": None, "priority": 100, "state": "unknown", "preempt": False}
                if len(parts) > 2 and parts[2].isdigit():
                    group["vrid"] = int(parts[2])
                if "virtual-ip" in parts:
                    idx = parts.index("virtual-ip")
                    if idx + 1 < len(parts):
                        group["virtual_ip"] = parts[idx + 1]
                if "priority" in parts:
                    idx = parts.index("priority")
                    if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                        group["priority"] = int(parts[idx + 1])
                if "state" in parts:
                    idx = parts.index("state")
                    if idx + 1 < len(parts):
                        group["state"] = parts[idx + 1].lower()
                group["preempt"] = "preempt-mode" in parts
                current_intf.vrrp_groups.append(group)

        elif section == "bgp":
            m = re.match(r"^peer\s+(\S+)\s+as-number\s+(\d+)", line)
            if m:
                parsed.bgp_neighbors.append(
                    {
                        "peer_ip": m.group(1),
                        "remote_as": int(m.group(2)),
                        "enabled": True,
                        "state": "unknown",
                        "uptime": None,
                    }
                )
            elif line.startswith("peer ") and "as-number" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    parsed.bgp_neighbors.append(
                        {
                            "peer_ip": parts[1],
                            "remote_as": None,
                            "enabled": False,
                            "state": "idle",
                            "uptime": None,
                        }
                    )

        elif section == "ospf" and current_ospf:
            if line.startswith("area "):
                current_ospf["areas"].append(line.split()[1])
            elif line.startswith("network "):
                current_ospf["networks"].append(" ".join(line.split()[1:]))

        # 运行态文本混合解析
        bgp_state = re.search(r"bgp\s+neighbor\s+(\S+)\s+state\s+(\S+)(?:\s+uptime\s+(\S+))?", line, re.I)
        if bgp_state:
            peer_ip, state, uptime = bgp_state.group(1), bgp_state.group(2).lower(), bgp_state.group(3)
            for n in parsed.bgp_neighbors:
                if n["peer_ip"] == peer_ip:
                    n["state"] = state
                    n["uptime"] = uptime
                    break

        ospf_neighbor = re.search(r"ospf\s+neighbor\s+(\S+)\s+state\s+(\S+)(?:\s+uptime\s+(\S+))?", line, re.I)
        if ospf_neighbor:
            parsed.ospf_neighbors.append(
                {
                    "neighbor_id": ospf_neighbor.group(1),
                    "state": ospf_neighbor.group(2).lower(),
                    "uptime": ospf_neighbor.group(3),
                }
            )

        intf_state = re.search(r"interface\s+(\S+)\s+line-protocol\s+(up|down)", line, re.I)
        if intf_state:
            name, state = intf_state.group(1), intf_state.group(2).lower()
            intf = parsed.interfaces.get(name)
            if intf:
                intf.line_protocol_up = state == "up"

    parsed.bgp_neighbors = _normalize_valid_ip_neighbors(parsed.bgp_neighbors)
    return parsed


def _parse_cisco(text: str, device_name: str) -> ParsedConfig:
    parsed = ParsedConfig(device_name=device_name, vendor="cisco")
    section: str | None = None
    current_intf: InterfaceConfig | None = None
    current_ospf: dict | None = None

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue

        _parse_route_summary(stripped, parsed)

        if stripped.startswith("interface "):
            section = "interface"
            name = stripped.split(maxsplit=1)[1]
            current_intf = InterfaceConfig(name=name)
            parsed.interfaces[name] = current_intf
            continue

        if stripped.startswith("router bgp "):
            section = "bgp"
            try:
                parsed.local_as = int(stripped.split()[2])
            except (ValueError, IndexError):
                parsed.local_as = None
            continue

        if stripped.startswith("router ospf "):
            section = "ospf"
            pid = stripped.split()[2]
            current_ospf = {"process_id": int(pid) if pid.isdigit() else pid, "areas": [], "networks": []}
            parsed.ospf_processes.append(current_ospf)
            continue

        if stripped == "exit":
            section = None
            current_intf = None
            current_ospf = None
            continue

        if section == "interface" and current_intf:
            if stripped.startswith("description "):
                current_intf.description = stripped.removeprefix("description ").strip()
            elif stripped.startswith("ip address "):
                parts = stripped.split()
                if len(parts) >= 3:
                    current_intf.ip_address = parts[2]
            elif stripped == "shutdown":
                current_intf.shutdown = True
            elif stripped == "no shutdown":
                current_intf.shutdown = False
            elif stripped.startswith("vrrp "):
                # vrrp 1 ip 10.0.0.254 / vrrp 1 priority 120
                parts = stripped.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    vrid = int(parts[1])
                    group = next((g for g in current_intf.vrrp_groups if g.get("vrid") == vrid), None)
                    if group is None:
                        group = {"vrid": vrid, "virtual_ip": None, "priority": 100, "state": "unknown", "preempt": False}
                        current_intf.vrrp_groups.append(group)
                    if len(parts) >= 4 and parts[2] == "ip":
                        group["virtual_ip"] = parts[3]
                    if len(parts) >= 4 and parts[2] == "priority" and parts[3].isdigit():
                        group["priority"] = int(parts[3])
            elif stripped.startswith("ip ospf "):
                current_intf.ospf_enabled = True

        elif section == "bgp":
            m = re.match(r"^neighbor\s+(\S+)\s+remote-as\s+(\d+)", stripped)
            if m:
                parsed.bgp_neighbors.append(
                    {
                        "peer_ip": m.group(1),
                        "remote_as": int(m.group(2)),
                        "enabled": True,
                        "state": "unknown",
                        "uptime": None,
                    }
                )

        elif section == "ospf" and current_ospf:
            m = re.match(r"^network\s+(.+)\s+area\s+(\S+)", stripped)
            if m:
                current_ospf["networks"].append(m.group(1))
                current_ospf["areas"].append(m.group(2))

        bgp_state = re.search(r"bgp\s+neighbor\s+(\S+)\s+state\s+(\S+)(?:\s+uptime\s+(\S+))?", stripped, re.I)
        if bgp_state:
            for n in parsed.bgp_neighbors:
                if n["peer_ip"] == bgp_state.group(1):
                    n["state"] = bgp_state.group(2).lower()
                    n["uptime"] = bgp_state.group(3)
                    break

        ospf_neighbor = re.search(r"ospf\s+neighbor\s+(\S+)\s+state\s+(\S+)(?:\s+uptime\s+(\S+))?", stripped, re.I)
        if ospf_neighbor:
            parsed.ospf_neighbors.append(
                {
                    "neighbor_id": ospf_neighbor.group(1),
                    "state": ospf_neighbor.group(2).lower(),
                    "uptime": ospf_neighbor.group(3),
                }
            )

        intf_state = re.search(r"interface\s+(\S+)\s+line-protocol\s+(up|down)", stripped, re.I)
        if intf_state and intf_state.group(1) in parsed.interfaces:
            parsed.interfaces[intf_state.group(1)].line_protocol_up = intf_state.group(2).lower() == "up"

    parsed.bgp_neighbors = _normalize_valid_ip_neighbors(parsed.bgp_neighbors)
    return parsed


def parse_device_text(text: str, device_name: str, vendor: str | None = None) -> ParsedConfig:
    selected_vendor = vendor or detect_vendor(text)
    if selected_vendor in {"huawei", "h3c", "unknown"}:
        return _parse_huawei_h3c(text=text, device_name=device_name, vendor=selected_vendor)
    if selected_vendor == "cisco":
        return _parse_cisco(text=text, device_name=device_name)
    return _parse_huawei_h3c(text=text, device_name=device_name, vendor="unknown")

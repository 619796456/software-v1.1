from __future__ import annotations

from analyzer.parser import ParsedConfig


def build_topology(parsed: ParsedConfig) -> dict:
    nodes = [
        {
            "id": parsed.device_name,
            "type": "device",
            "label": parsed.device_name,
            "vendor": parsed.vendor,
        }
    ]
    links = []

    for intf in parsed.interfaces.values():
        node_id = f"{parsed.device_name}:{intf.name}"
        nodes.append(
            {
                "id": node_id,
                "type": "interface",
                "label": intf.name,
                "ip": intf.ip_address,
                "shutdown": intf.shutdown,
                "line_protocol_up": intf.line_protocol_up,
            }
        )
        links.append({"source": parsed.device_name, "target": node_id, "relation": "has_interface"})

    for n in parsed.bgp_neighbors:
        peer_node = f"BGP:{n['peer_ip']}"
        nodes.append(
            {
                "id": peer_node,
                "type": "bgp_peer",
                "label": n["peer_ip"],
                "as": n["remote_as"],
                "state": n.get("state"),
            }
        )
        links.append(
            {
                "source": parsed.device_name,
                "target": peer_node,
                "relation": "bgp_neighbor",
                "enabled": n["enabled"],
                "state": n.get("state"),
            }
        )

    for n in parsed.ospf_neighbors:
        peer_node = f"OSPF:{n['neighbor_id']}"
        nodes.append({"id": peer_node, "type": "ospf_peer", "label": n["neighbor_id"], "state": n.get("state")})
        links.append(
            {
                "source": parsed.device_name,
                "target": peer_node,
                "relation": "ospf_neighbor",
                "state": n.get("state"),
            }
        )

    return {"nodes": nodes, "links": links}

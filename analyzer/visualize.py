from __future__ import annotations

from pathlib import Path


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


def draw_topology(parsed: ParsedConfig, output_path: str | Path | None = None, show: bool = True) -> str | None:
    """基于解析结果绘制拓扑图（中文标识+接口+IP+状态颜色）。"""

    try:
        import matplotlib.pyplot as plt
        import networkx as nx
    except ModuleNotFoundError as exc:
        raise RuntimeError("绘制拓扑需要安装 matplotlib 和 networkx") from exc

    graph = nx.Graph()

    graph.add_node(parsed.device_name, label=f"设备\n{parsed.device_name}", color="#4caf50")
    for intf in parsed.interfaces.values():
        node_id = f"{parsed.device_name}:{intf.name}"
        state_ok = (not intf.shutdown) and (intf.line_protocol_up is not False)
        color = "#66bb6a" if state_ok else "#ef5350"
        ip_text = intf.ip_address or "无IP"
        graph.add_node(node_id, label=f"接口\n{intf.name}\n{ip_text}", color=color)
        graph.add_edge(parsed.device_name, node_id)

    for n in parsed.bgp_neighbors:
        node_id = f"BGP:{n['peer_ip']}"
        state_ok = n.get("state") in {"established", "unknown"}
        color = "#42a5f5" if state_ok else "#ef5350"
        graph.add_node(node_id, label=f"BGP邻居\n{n['peer_ip']}", color=color)
        graph.add_edge(parsed.device_name, node_id)

    for n in parsed.ospf_neighbors:
        node_id = f"OSPF:{n['neighbor_id']}"
        state_ok = n.get("state") in {"full", "2-way"}
        color = "#7e57c2" if state_ok else "#ef5350"
        graph.add_node(node_id, label=f"OSPF邻居\n{n['neighbor_id']}", color=color)
        graph.add_edge(parsed.device_name, node_id)

    if not graph.nodes:
        return None

    plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111)
    ax.set_title(f"网络拓扑图 - {parsed.device_name}")

    pos = nx.spring_layout(graph, seed=42)
    colors = [graph.nodes[node].get("color", "#90a4ae") for node in graph.nodes]
    labels = {node: graph.nodes[node].get("label", node) for node in graph.nodes}

    nx.draw_networkx_nodes(graph, pos, node_color=colors, node_size=1800, ax=ax)
    nx.draw_networkx_edges(graph, pos, edge_color="#90a4ae", width=1.6, ax=ax)
    nx.draw_networkx_labels(graph, pos, labels=labels, font_size=9, ax=ax)
    ax.axis("off")
    fig.tight_layout()

    saved_path: str | None = None
    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, dpi=150)
        saved_path = str(output)

    if show:
        plt.show()
    else:
        plt.close(fig)

    return saved_path

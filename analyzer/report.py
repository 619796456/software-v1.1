from __future__ import annotations

from pathlib import Path


def _finding_badge_class(severity: str) -> str:
    return {
        "high": "badge-high",
        "medium": "badge-medium",
        "low": "badge-low",
    }.get(severity, "badge-low")


def _summary_blocks(summary: dict) -> tuple[dict, dict, dict, dict]:
    basic = summary.get("basic", {})
    interfaces = summary.get("interfaces", {})
    interface_legacy = summary.get("interface", {})

    if not basic and interface_legacy:
        basic = {"interface_count": interface_legacy.get("total", 0)}
    if not interfaces and interface_legacy:
        interfaces = {
            "total": interface_legacy.get("total", 0),
            "shutdown": interface_legacy.get("shutdown", 0),
            "line_protocol_down": interface_legacy.get("line_protocol_down", 0),
            "down_or_shutdown": interface_legacy.get("shutdown", 0) + interface_legacy.get("line_protocol_down", 0),
            "up": interface_legacy.get("up", 0),
        }

    protocol = summary.get("protocol", {})
    routing = summary.get("routing", {})
    return basic, interfaces, protocol, routing


def build_html_report(payload: dict) -> str:
    parsed = payload.get("parsed", {})
    summary = payload.get("summary", {})
    findings = payload.get("findings", [])
    topology = payload.get("topology", {})

    basic, interfaces, protocol, routing = _summary_blocks(summary)
    basic = summary.get("basic", {})
    interfaces = summary.get("interfaces", {})
    protocol = summary.get("protocol", {})
    routing = summary.get("routing", {})

    finding_rows = "\n".join(
        f"""
        <tr>
          <td><span class='badge {_finding_badge_class(f.get('severity', 'low'))}'>{f.get('severity', 'low')}</span></td>
          <td>{f.get('type', '-')}</td>
          <td>{f.get('message', '-')}</td>
        </tr>
        """
        for f in findings
    ) or "<tr><td colspan='3'>未发现异常。</td></tr>"

    return f"""
<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='UTF-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1.0' />
  <title>站场网络配置智能分析报告</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans CJK SC', 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif; margin: 0; background: #f5f7fb; color: #1f2d3d; }}
    .container {{ max-width: 1080px; margin: 24px auto; padding: 0 16px 40px; }}
    .header {{ background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 4px 18px rgba(0,0,0,0.06); }}
    h1 {{ margin: 0 0 8px; font-size: 24px; }}
    h2 {{ margin: 24px 0 12px; font-size: 20px; }}
    .muted {{ color: #61738a; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .card {{ background: #fff; border-radius: 10px; padding: 14px; box-shadow: 0 3px 14px rgba(0,0,0,0.05); }}
    .label {{ font-size: 12px; color: #6c7a89; margin-bottom: 6px; }}
    .value {{ font-size: 20px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 3px 14px rgba(0,0,0,0.05); }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid #edf1f7; font-size: 14px; text-align: left; }}
    th {{ background: #f8fafc; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; color: #fff; }}
    .badge-high {{ background: #e53935; }}
    .badge-medium {{ background: #fb8c00; }}
    .badge-low {{ background: #43a047; }}
  </style>
</head>
<body>
  <div class='container'>
    <div class='header'>
      <h1>站场网络配置智能分析报告（离线）</h1>
      <div class='muted'>设备：{parsed.get('device_name', '-') } ｜ 厂商：{parsed.get('vendor', '-') } ｜ 本地AS：{parsed.get('local_as', '-')}</div>
    </div>

    <h2>综合状态</h2>
    <div class='grid'>
      <div class='card'><div class='label'>接口总数</div><div class='value'>{basic.get('interface_count', 0)}</div></div>
      <div class='card'><div class='label'>接口异常数</div><div class='value'>{interfaces.get('down_or_shutdown', 0)}</div></div>
      <div class='card'><div class='label'>BGP 邻居 (总/正常/异常)</div><div class='value'>{protocol.get('bgp', {}).get('total', 0)} / {protocol.get('bgp', {}).get('established', 0)} / {protocol.get('bgp', {}).get('abnormal', 0)}</div></div>
      <div class='card'><div class='label'>OSPF 邻居 (总/正常/异常)</div><div class='value'>{protocol.get('ospf', {}).get('total', 0)} / {protocol.get('ospf', {}).get('healthy', 0)} / {protocol.get('ospf', {}).get('abnormal', 0)}</div></div>
      <div class='card'><div class='label'>路由统计 (总/直连/静态/BGP/OSPF)</div><div class='value'>{routing.get('total', 0)} / {routing.get('direct', 0)} / {routing.get('static', 0)} / {routing.get('bgp', 0)} / {routing.get('ospf', 0)}</div></div>
    </div>

    <h2>异常与非标准化提示</h2>
    <table>
      <thead><tr><th>级别</th><th>类型</th><th>说明</th></tr></thead>
      <tbody>
        {finding_rows}
      </tbody>
    </table>

    <h2>拓扑摘要</h2>
    <div class='card'>
      <div class='muted'>节点数: {len(topology.get('nodes', []))} ｜ 链路数: {len(topology.get('links', []))}</div>
      <div class='muted' style='margin-top:6px'>提示：完整拓扑明细请查看 JSON 输出中的 <code>topology.nodes</code> 与 <code>topology.links</code>。</div>
    </div>
  </div>
</body>
</html>
"""


def build_text_report(payload: dict) -> str:
    parsed = payload.get("parsed", {})
    summary = payload.get("summary", {})
    findings = payload.get("findings", [])

    basic, interfaces, protocol, routing = _summary_blocks(summary)

    lines = [
        "站场网络配置智能分析报告（离线）",
        "=" * 40,
        f"设备: {parsed.get('device_name', '-')}",
        f"厂商: {parsed.get('vendor', '-')}",
        f"本地AS: {parsed.get('local_as', '-')}",
        "",
        "[接口与协议统计]",
        f"接口总数: {basic.get('interface_count', 0)}",
        f"接口异常数: {interfaces.get('down_or_shutdown', 0)}",
        f"BGP 邻居: {protocol.get('bgp', {})}",
        f"OSPF 邻居: {protocol.get('ospf', {})}",
        f"路由统计: {routing}",
        f"接口总数: {summary.get('basic', {}).get('interface_count', 0)}",
        f"接口异常数: {summary.get('interfaces', {}).get('down_or_shutdown', 0)}",
        f"BGP 邻居: {summary.get('protocol', {}).get('bgp', {})}",
        f"OSPF 邻居: {summary.get('protocol', {}).get('ospf', {})}",
        f"路由统计: {summary.get('routing', {})}",
        "",
        "[异常与非标准化提示]",
    ]
    if findings:
        for i, finding in enumerate(findings, start=1):
            lines.append(f"{i}. [{finding.get('severity', 'low')}] {finding.get('type')}: {finding.get('message')}")
    else:
        lines.append("无异常")
    return "\n".join(lines)


def write_html_report(payload: dict, output_path: str | Path) -> None:
    Path(output_path).write_text(build_html_report(payload), encoding="utf-8")


def write_text_report(payload: dict, output_path: str | Path) -> None:
    Path(output_path).write_text(build_text_report(payload), encoding="utf-8")

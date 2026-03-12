from __future__ import annotations

import html
from pathlib import Path


def _badge(text: str, color: str) -> str:
    return (
        f"<span style='display:inline-block;padding:2px 10px;border-radius:999px;"
        f"background:{color};color:#fff;font-size:12px'>{html.escape(text)}</span>"
    )


def _finding_color(severity: str) -> str:
    return {
        "high": "#dc2626",
        "medium": "#d97706",
        "low": "#2563eb",
    }.get(severity, "#475569")


def build_html_report(payload: dict) -> str:
    parsed = payload.get("parsed", {})
    summary = payload.get("summary", {})
    findings = payload.get("findings", [])
    topology = payload.get("topology", {})

    iface = summary.get("interface", {})
    protocol = summary.get("protocol", {})
    routing = summary.get("routing", {})

    finding_rows = "".join(
        (
            "<tr>"
            f"<td>{_badge(f.get('severity', 'unknown'), _finding_color(f.get('severity', 'unknown')))}</td>"
            f"<td>{html.escape(str(f.get('type', '')))}</td>"
            f"<td>{html.escape(str(f.get('message', '')))}</td>"
            "</tr>"
        )
        for f in findings
    ) or "<tr><td colspan='3'>未发现异常</td></tr>"

    return f"""
<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>网络配置智能分析报告 - {html.escape(str(parsed.get('device_name', 'Unknown')))}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }}
    .container {{ max-width: 1080px; margin: 24px auto; padding: 0 16px; }}
    .header {{ background: linear-gradient(135deg,#2563eb,#0ea5e9); color: #fff; border-radius: 16px; padding: 20px; box-shadow: 0 8px 24px rgba(37,99,235,.25); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap: 12px; margin-top: 16px; }}
    .card {{ background: #fff; border-radius: 12px; padding: 14px; border: 1px solid #e2e8f0; }}
    .label {{ color: #64748b; font-size: 13px; }}
    .value {{ font-size: 22px; font-weight: 700; margin-top: 4px; }}
    h2 {{ margin: 22px 0 10px; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
    th {{ background: #f1f5f9; }}
    .muted {{ color: #64748b; }}
  </style>
</head>
<body>
  <div class='container'>
    <div class='header'>
      <h1 style='margin:0'>站场网络配置智能分析报告</h1>
      <p style='margin:8px 0 0'>设备: <b>{html.escape(str(parsed.get('device_name', '-')))}</b> ｜ 厂商: <b>{html.escape(str(parsed.get('vendor', '-')))}</b> ｜ 本地AS: <b>{html.escape(str(parsed.get('local_as', '-')))}</b></p>
    </div>

    <h2>综合状态</h2>
    <div class='grid'>
      <div class='card'><div class='label'>接口总数 / Up / Shutdown</div><div class='value'>{iface.get('total', 0)} / {iface.get('up', 0)} / {iface.get('shutdown', 0)}</div></div>
      <div class='card'><div class='label'>BGP 邻居 (总 / 正常 / 异常)</div><div class='value'>{protocol.get('bgp', {}).get('total', 0)} / {protocol.get('bgp', {}).get('established', 0)} / {protocol.get('bgp', {}).get('abnormal', 0)}</div></div>
      <div class='card'><div class='label'>OSPF 邻居 (总 / 正常 / 异常)</div><div class='value'>{protocol.get('ospf', {}).get('total', 0)} / {protocol.get('ospf', {}).get('healthy', 0)} / {protocol.get('ospf', {}).get('abnormal', 0)}</div></div>
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


def write_html_report(payload: dict, output_path: str | Path) -> None:
    Path(output_path).write_text(build_html_report(payload), encoding="utf-8")

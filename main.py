from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyzer.analyzer import analyze_config, summarize_network_state
from analyzer.parser import parse_device_text
from analyzer.report import write_html_report, write_text_report
from analyzer.visualize import build_topology
from gui_app import run_gui


def build_payload(device_name: str, text: str, vendor: str | None = None) -> dict:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-vendor network config/state analyzer")
    parser.add_argument("--device-name", help="设备名称")
    parser.add_argument("--config-file", help="配置/运行信息文件路径")
    parser.add_argument("--output", help="输出 JSON 路径")
    parser.add_argument("--vendor", default="auto", choices=["auto", "huawei", "h3c", "cisco"], help="设备厂商")
    parser.add_argument("--report-html", default=None, help="可选：输出HTML报告路径")
    parser.add_argument("--report-txt", default=None, help="可选：输出TXT报告路径")
    parser.add_argument("--gui", action="store_true", help="启动图形界面")
    args = parser.parse_args()

    if args.gui or (not args.device_name and not args.config_file and not args.output):
        run_gui()
        return

    if not args.device_name or not args.config_file or not args.output:
        raise SystemExit("CLI 模式下必须提供 --device-name --config-file --output")

    text = Path(args.config_file).read_text(encoding="utf-8")
    vendor = None if args.vendor == "auto" else args.vendor
    payload = build_payload(device_name=args.device_name, text=text, vendor=vendor)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.report_html:
        write_html_report(payload, args.report_html)
    if args.report_txt:
        write_text_report(payload, args.report_txt)


if __name__ == "__main__":
    main()

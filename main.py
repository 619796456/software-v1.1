from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyzer.pipeline import run_pipeline
from analyzer.report import write_html_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-vendor network config/state analyzer")
    parser.add_argument("--device-name", required=True, help="设备名称")
    parser.add_argument("--config-file", required=True, help="配置/运行信息文件路径")
    parser.add_argument("--output", default=None, help="输出 JSON 路径（默认: 桌面/<设备名>_analysis.json）")
    parser.add_argument("--vendor", default="auto", choices=["auto", "huawei", "h3c", "cisco"], help="设备厂商")
    parser.add_argument("--report-html", default=None, help="可选：输出整洁HTML报告路径")
    args = parser.parse_args()

    text = Path(args.config_file).read_text(encoding="utf-8")
    vendor = None if args.vendor == "auto" else args.vendor
    payload = run_pipeline(text=text, device_name=args.device_name, vendor=vendor)

    desktop = Path.home() / "Desktop"
    default_dir = desktop if desktop.exists() else Path.cwd()
    output_path = Path(args.output) if args.output else default_dir / f"{args.device_name}_analysis.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.report_html:
        write_html_report(payload, args.report_html)


if __name__ == "__main__":
    main()

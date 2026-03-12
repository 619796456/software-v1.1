from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ModuleNotFoundError:  # 可选依赖
    DND_FILES = None
    TkinterDnD = None
from tkinter.scrolledtext import ScrolledText

from analyzer.analyzer import analyze_config, summarize_network_state
from analyzer.parser import parse_device_text
from analyzer.report import write_html_report, write_text_report
from analyzer.visualize import build_topology, draw_topology


class NetworkAnalyzerGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("网络配置智能分析与可视化工具")
        self.root.geometry("1200x860")
        self.root.geometry("1050x740")

        self.current_file: Path | None = None
        self.last_payload: dict | None = None
        self.last_parsed = None

        self.device_var = tk.StringVar(value="设备-1")
        self.detected_vendor_var = tk.StringVar(value="未识别")
        self.report_dir_var = tk.StringVar(value=str(Path.home() / "Desktop"))

        self.kpi_interface_var = tk.StringVar(value="0")
        self.kpi_bgp_var = tk.StringVar(value="0/0")
        self.kpi_ospf_var = tk.StringVar(value="0/0")
        self.kpi_route_var = tk.StringVar(value="0")
        self.kpi_finding_var = tk.StringVar(value="0")

        self._build_ui()

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.configure("Card.TLabelframe", background="#ffffff")

        self.vendor_var = tk.StringVar(value="auto")
        self.report_dir_var = tk.StringVar(value=str(Path.home() / "Desktop"))

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="设备名:").grid(row=0, column=0, sticky=tk.W, padx=4)
        ttk.Entry(top, textvariable=self.device_var, width=20).grid(row=0, column=1, sticky=tk.W, padx=4)
        ttk.Label(top, text="识别厂商:").grid(row=0, column=2, sticky=tk.W, padx=4)
        ttk.Label(top, textvariable=self.detected_vendor_var, foreground="#1565c0").grid(row=0, column=3, sticky=tk.W, padx=4)

        ttk.Label(top, text="报告路径:").grid(row=0, column=4, sticky=tk.W, padx=4)
        ttk.Entry(top, textvariable=self.report_dir_var, width=48).grid(row=0, column=5, sticky=tk.W, padx=4)
        ttk.Entry(top, textvariable=self.device_var, width=22).grid(row=0, column=1, sticky=tk.W, padx=4)

        ttk.Label(top, text="厂商:").grid(row=0, column=2, sticky=tk.W, padx=4)
        ttk.Combobox(top, textvariable=self.vendor_var, values=["auto", "huawei", "h3c", "cisco"], width=10).grid(
            row=0, column=3, sticky=tk.W, padx=4
        )

        ttk.Label(top, text="报告路径:").grid(row=0, column=4, sticky=tk.W, padx=4)
        ttk.Entry(top, textvariable=self.report_dir_var, width=40).grid(row=0, column=5, sticky=tk.W, padx=4)
        ttk.Button(top, text="选择目录", command=self.choose_report_dir).grid(row=0, column=6, padx=4)

        btns = ttk.Frame(self.root, padding=(10, 0))
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="上传TXT", command=self.upload_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="解析分析", command=self.analyze_text).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="生成报告(TXT+HTML)", command=self.export_report).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="显示拓扑", command=self.show_topology).pack(side=tk.LEFT, padx=4)

        kpi = ttk.Frame(self.root, padding=(10, 6))
        kpi.pack(fill=tk.X)
        self._build_kpi(kpi, "接口总数", self.kpi_interface_var).pack(side=tk.LEFT, padx=4)
        self._build_kpi(kpi, "BGP(总/正常)", self.kpi_bgp_var).pack(side=tk.LEFT, padx=4)
        self._build_kpi(kpi, "OSPF(总/正常)", self.kpi_ospf_var).pack(side=tk.LEFT, padx=4)
        self._build_kpi(kpi, "总路由", self.kpi_route_var).pack(side=tk.LEFT, padx=4)
        self._build_kpi(kpi, "异常条目", self.kpi_finding_var).pack(side=tk.LEFT, padx=4)

        paned = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        io_frame = ttk.LabelFrame(paned, text="配置文本输入（可粘贴 / 拖拽txt / 点击上传）", padding=8)
        io_frame = ttk.LabelFrame(self.root, text="配置文本（可直接粘贴）", padding=8)
        io_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self.input_text = ScrolledText(io_frame, wrap=tk.WORD, height=14, font=("Consolas", 10))
        self.input_text.pack(fill=tk.BOTH, expand=True)
        if DND_FILES and hasattr(self.input_text, "drop_target_register"):
            self.input_text.drop_target_register(DND_FILES)
            self.input_text.dnd_bind("<<Drop>>", self._on_drop_file)
        paned.add(io_frame, weight=1)

        output_frame = ttk.LabelFrame(paned, text="本地分析结果（结构化展示）", padding=8)
        self.output_tabs = ttk.Notebook(output_frame)
        self.output_tabs.pack(fill=tk.BOTH, expand=True)

        self.overview_text = ScrolledText(self.output_tabs, wrap=tk.WORD, height=10, font=("Consolas", 10))
        self.overview_text.tag_configure("title", foreground="#0d47a1", font=("Microsoft YaHei", 11, "bold"))
        self.overview_text.tag_configure("ok", foreground="#2e7d32")
        self.overview_text.tag_configure("warn", foreground="#ef6c00")
        self.overview_text.tag_configure("bad", foreground="#c62828")
        self.output_tabs.add(self.overview_text, text="综合总览")

        self.interface_tree = self._build_tree(
            self.output_tabs,
            columns=("name", "ip", "admin", "protocol", "ospf", "vrrp", "desc"),
            headings=("接口", "IP", "管理状态", "协议状态", "OSPF", "VRRP", "描述"),
        )
        self.output_tabs.add(self.interface_tree.master, text="接口状态")

        self.neighbor_tree = self._build_tree(
            self.output_tabs,
            columns=("proto", "peer", "state", "uptime", "extra"),
            headings=("协议", "邻居", "状态", "建立时长", "附加信息"),
        )
        self.output_tabs.add(self.neighbor_tree.master, text="协议邻居")

        self.finding_tree = self._build_tree(
            self.output_tabs,
            columns=("severity", "type", "message"),
            headings=("级别", "类型", "说明"),
        )
        self.output_tabs.add(self.finding_tree.master, text="异常提示")

        paned.add(output_frame, weight=1)

        result_frame = ttk.LabelFrame(self.root, text="分析结果", padding=8)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.result_text = ScrolledText(result_frame, wrap=tk.WORD, height=14, font=("Consolas", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True)

        hint = "安全声明：本工具仅本地解析文本，不执行配置、不调用外部命令、不访问网络。"
        ttk.Label(self.root, text=hint, foreground="#1565c0").pack(anchor=tk.W, padx=12, pady=(0, 8))

    def _build_tree(self, parent, columns: tuple[str, ...], headings: tuple[str, ...]) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=12)
        for col, head in zip(columns, headings):
            tree.heading(col, text=head)
            tree.column(col, width=140, anchor=tk.W)
        y_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=y_scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        return tree

    def _build_kpi(self, parent: ttk.Frame, title: str, value_var: tk.StringVar) -> ttk.Frame:
        frame = ttk.LabelFrame(parent, text=title, padding=(8, 4))
        ttk.Label(frame, textvariable=value_var, foreground="#1b5e20", font=("Microsoft YaHei", 12, "bold")).pack()
        return frame

    def choose_report_dir(self) -> None:
        selected = filedialog.askdirectory(title="选择报告保存路径")
        if selected:
            self.report_dir_var.set(selected)

    def upload_file(self) -> None:
        file_path = filedialog.askopenfilename(title="选择配置文件", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not file_path:
            return
        self._load_file(Path(file_path))

    def _load_file(self, path: Path) -> None:
        self.current_file = path
        content = path.read_text(encoding="utf-8", errors="ignore")
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert(tk.END, content)

    def _on_drop_file(self, event) -> None:
        dropped_raw = event.data.strip()
        candidates = [part.strip("{}") for part in dropped_raw.split() if part.strip()]
        for item in candidates:
            path = Path(item)
            if path.exists() and path.is_file() and path.suffix.lower() in {".txt", ".log", ".cfg", ".conf"}:
                self._load_file(path)
                return
        self.current_file = Path(file_path)
        content = self.current_file.read_text(encoding="utf-8", errors="ignore")
        self.input_text.delete("1.0", tk.END)
        self.input_text.insert(tk.END, content)
        messagebox.showinfo("上传成功", f"已加载文件：{self.current_file}")


    def _on_drop_file(self, event) -> None:
        # TkDND 传值可能包含花括号/空格路径
        dropped = event.data.strip().strip("{}")
        path = Path(dropped)
        if path.exists() and path.is_file():
            self.current_file = path
            content = path.read_text(encoding="utf-8", errors="ignore")
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert(tk.END, content)

    def _build_payload(self) -> dict:
        text = self.input_text.get("1.0", tk.END).strip()
        if not text:
            raise ValueError("请先粘贴配置文本或上传 txt 文件")

        # GUI中不要求用户手选厂商，统一自动识别
        parsed = parse_device_text(text=text, device_name=self.device_var.get().strip() or "设备-1", vendor=None)
        vendor = None if self.vendor_var.get() == "auto" else self.vendor_var.get()
        parsed = parse_device_text(text=text, device_name=self.device_var.get().strip() or "设备-1", vendor=vendor)
        findings = analyze_config(parsed)
        summary = summarize_network_state(parsed)
        topology = build_topology(parsed)

        payload = {
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
        self.last_parsed = parsed
        self.last_payload = payload
        self.detected_vendor_var.set(parsed.vendor)
        return payload

    def _refresh_tables(self, payload: dict) -> None:
        for tree in (self.interface_tree, self.neighbor_tree, self.finding_tree):
            for item in tree.get_children():
                tree.delete(item)

        parsed = payload["parsed"]
        summary = payload["summary"]

        for name, info in parsed["interfaces"].items():
            admin = "down(shutdown)" if info.get("shutdown") else "up"
            protocol_up = info.get("line_protocol_up")
            protocol = "unknown" if protocol_up is None else ("up" if protocol_up else "down")
            ospf = "enabled" if info.get("ospf_enabled") else "-"
            vrrp = f"{len(info.get('vrrp_groups', []))}组" if info.get("vrrp_groups") else "-"
            self.interface_tree.insert(
                "",
                tk.END,
                values=(
                    name,
                    info.get("ip_address") or "-",
                    admin,
                    protocol,
                    ospf,
                    vrrp,
                    info.get("description") or "-",
                ),
            )

        for bgp in parsed["bgp_neighbors"]:
            extra = f"remote-as={bgp.get('remote_as')}"
            self.neighbor_tree.insert(
                "",
                tk.END,
                values=("BGP", bgp.get("peer_ip"), bgp.get("state"), bgp.get("uptime") or "-", extra),
            )
        for ospf in parsed["ospf_neighbors"]:
            self.neighbor_tree.insert(
                "",
                tk.END,
                values=("OSPF", ospf.get("neighbor_id"), ospf.get("state"), ospf.get("uptime") or "-", "-"),
            )

        for finding in payload["findings"]:
            self.finding_tree.insert(
                "",
                tk.END,
                values=(finding.get("severity"), finding.get("type"), finding.get("message")),
            )

        self.kpi_interface_var.set(str(summary.get("interfaces", {}).get("total", 0)))
        self.kpi_bgp_var.set(
            f"{summary.get('protocol', {}).get('bgp', {}).get('total', 0)}/"
            f"{summary.get('protocol', {}).get('bgp', {}).get('established', 0)}"
        )
        self.kpi_ospf_var.set(
            f"{summary.get('protocol', {}).get('ospf', {}).get('total', 0)}/"
            f"{summary.get('protocol', {}).get('ospf', {}).get('healthy', 0)}"
        )
        self.kpi_route_var.set(str(summary.get("routing", {}).get("total", 0)))
        self.kpi_finding_var.set(str(len(payload.get("findings", []))))

    def _render_overview(self, payload: dict) -> None:
        parsed = payload["parsed"]
        summary = payload["summary"]
        findings = payload["findings"]

        self.overview_text.delete("1.0", tk.END)
        self.overview_text.insert(tk.END, "设备配置关键摘要\n", "title")
        self.overview_text.insert(
            tk.END,
            f"设备名称: {parsed['device_name']}\n"
            f"识别厂商: {parsed['vendor']}\n"
            f"本地AS: {parsed.get('local_as')}\n"
            f"接口总数: {summary['interfaces']['total']}，异常接口: {summary['interfaces']['down_or_shutdown']}\n"
            f"BGP: 总{summary['protocol']['bgp']['total']} / 正常{summary['protocol']['bgp']['established']} / 异常{summary['protocol']['bgp']['abnormal']}\n"
            f"OSPF: 总{summary['protocol']['ospf']['total']} / 正常{summary['protocol']['ospf']['healthy']} / 异常{summary['protocol']['ospf']['abnormal']}\n"
            f"路由统计: {json.dumps(summary['routing'], ensure_ascii=False)}\n\n",
        )

        self.overview_text.insert(tk.END, "异常与非标准化提示\n", "title")
        if not findings:
            self.overview_text.insert(tk.END, "未发现异常。\n", "ok")
            return

        for idx, finding in enumerate(findings, start=1):
            tag = "bad" if finding["severity"] == "high" else ("warn" if finding["severity"] == "medium" else "ok")
            self.overview_text.insert(
                tk.END,
                f"{idx:02d}. [{finding['severity']}] {finding['type']} - {finding['message']}\n",
                tag,
            )

        return payload

    def analyze_text(self) -> None:
        try:
            payload = self._build_payload()
        except Exception as exc:
            messagebox.showerror("解析失败", str(exc))
            return

        self._refresh_tables(payload)
        self._render_overview(payload)

        if payload["findings"]:
            messagebox.showwarning("分析完成", f"识别厂商: {payload['parsed']['vendor']}，发现 {len(payload['findings'])} 条异常/提示。")
        else:
            messagebox.showinfo("分析完成", f"识别厂商: {payload['parsed']['vendor']}，未发现异常。")
        output = {
            "设备": payload["parsed"]["device_name"],
            "厂商": payload["parsed"]["vendor"],
            "状态汇总": payload["summary"],
            "异常提示": payload["findings"],
        }
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, json.dumps(output, ensure_ascii=False, indent=2))

        if payload["findings"]:
            messagebox.showwarning("分析完成", f"发现 {len(payload['findings'])} 条异常/非标准化提示，已高亮输出。")
        else:
            messagebox.showinfo("分析完成", "未发现异常。")

    def export_report(self) -> None:
        try:
            payload = self.last_payload or self._build_payload()
        except Exception as exc:
            messagebox.showerror("导出失败", str(exc))
            return

        report_dir = Path(self.report_dir_var.get()).expanduser()
        report_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"{payload['parsed']['device_name']}_network_report"
        txt_path = report_dir / f"{base_name}.txt"
        html_path = report_dir / f"{base_name}.html"

        write_text_report(payload, txt_path)
        write_html_report(payload, html_path)
        messagebox.showinfo("导出成功", f"TXT: {txt_path}\nHTML: {html_path}")

    def show_topology(self) -> None:
        if self.last_parsed is None:
            try:
                self._build_payload()
            except Exception as exc:
                messagebox.showerror("拓扑绘制失败", str(exc))
                return

        try:
            draw_topology(self.last_parsed, show=True)
        except RuntimeError as exc:
            messagebox.showerror("拓扑绘制失败", f"{exc}\n请在本地安装: pip install matplotlib networkx")
        except Exception as exc:  # 防止点击无反应
            messagebox.showerror("拓扑绘制失败", f"发生异常: {exc}")
        draw_topology(self.last_parsed, show=True)


def run_gui() -> None:
    root = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
    app = NetworkAnalyzerGUI(root)
    _ = app
    root.mainloop()

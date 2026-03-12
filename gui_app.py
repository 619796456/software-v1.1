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
        self.root.geometry("1050x740")

        self.current_file: Path | None = None
        self.last_payload: dict | None = None
        self.last_parsed = None

        self.device_var = tk.StringVar(value="设备-1")
        self.vendor_var = tk.StringVar(value="auto")
        self.report_dir_var = tk.StringVar(value=str(Path.home() / "Desktop"))

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="设备名:").grid(row=0, column=0, sticky=tk.W, padx=4)
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

        io_frame = ttk.LabelFrame(self.root, text="配置文本（可直接粘贴）", padding=8)
        io_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        self.input_text = ScrolledText(io_frame, wrap=tk.WORD, height=14, font=("Consolas", 10))
        self.input_text.pack(fill=tk.BOTH, expand=True)
        if DND_FILES and hasattr(self.input_text, "drop_target_register"):
            self.input_text.drop_target_register(DND_FILES)
            self.input_text.dnd_bind("<<Drop>>", self._on_drop_file)

        result_frame = ttk.LabelFrame(self.root, text="分析结果", padding=8)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.result_text = ScrolledText(result_frame, wrap=tk.WORD, height=14, font=("Consolas", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True)

        hint = "安全声明：本工具仅本地解析文本，不执行配置、不调用外部命令、不访问网络。"
        ttk.Label(self.root, text=hint, foreground="#1565c0").pack(anchor=tk.W, padx=12, pady=(0, 8))

    def choose_report_dir(self) -> None:
        selected = filedialog.askdirectory(title="选择报告保存路径")
        if selected:
            self.report_dir_var.set(selected)

    def upload_file(self) -> None:
        file_path = filedialog.askopenfilename(title="选择配置文件", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not file_path:
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
        return payload

    def analyze_text(self) -> None:
        try:
            payload = self._build_payload()
        except Exception as exc:
            messagebox.showerror("解析失败", str(exc))
            return

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

        draw_topology(self.last_parsed, show=True)


def run_gui() -> None:
    root = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
    app = NetworkAnalyzerGUI(root)
    _ = app
    root.mainloop()

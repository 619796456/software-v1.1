# 站场网络配置智能分析与可视化工具（离线版）

本项目是一个**可本地部署、数据自主可控**的站场网络配置与运行状态智能分析小工具，支持华为、H3C、思科（Cisco）等主流设备配置文本与运行输出的统一解析。

## 你能直接用它做什么

- 上传/读取设备配置与运行状态文本，自动识别厂商并结构化解析
- 自动识别 BGP/OSPF/VRRP/接口状态异常
- 输出路由统计（总路由、直连、静态、BGP、OSPF）
- 自动生成拓扑数据（`nodes/links`）
- 生成**整洁美观的 HTML 分析报告**（离线可打开）

## 项目结构

```text
.
├── analyzer
│   ├── parser.py       # 多厂商配置+运行态解析、厂商识别
│   ├── analyzer.py     # 协议状态/接口状态/标准化规则分析 + 汇总
│   ├── visualize.py    # 拓扑 JSON 生成
│   └── report.py       # HTML 可视化报告生成
├── tests
│   └── test_pipeline.py
└── main.py             # CLI 入口
```

## 快速开始

### 1) 运行分析并导出 JSON + HTML 报告

```bash
python main.py \
  --device-name Station-R1 \
  --config-file sample.txt \
  --output result.json \
  --report-html report.html \
  --vendor auto
```

参数说明：
- `--vendor auto`：自动识别（也可手动指定 `huawei|h3c|cisco`）
- `--config-file`：可放配置文本，或配置+运行状态输出混合文本
- `--output`：结构化 JSON 输出
- `--report-html`：可选，输出整洁 HTML 报告

### 2) 查看报告

直接双击 `report.html` 或在浏览器打开，即可看到综合状态卡片、异常提示表格、拓扑摘要。

## 输出结构

`result.json` 包含：
- `parsed`：结构化配置与运行态
- `summary`：接口/协议/路由汇总统计
- `findings`：异常与非标准化提示
- `topology`：可视化拓扑数据

## 测试

在你的 Python 环境运行：

```bash
pytest -q
```

已覆盖：
- 华为/思科配置解析和运行态识别
- 厂商自动识别
- 规则分析与摘要统计
- HTML 报告生成
- CLI 端到端（JSON + HTML 输出）

## 后续建议

- 扩展更多 show/display 命令模板（BFD、ISIS、MPLS）
- 增加跨设备拓扑自动拼接能力
- 增加 Web UI 综合看板（颜色告警、风险等级、报告导出）

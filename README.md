# 网络配置智能分析与可视化工具（离线本地版）

本项目是一个**纯本地运行**的网络配置智能分析工具，支持华为、H3C、思科（Cisco）配置与运行状态文本解析，提供异常提示、拓扑可视化（`networkx + matplotlib`）与报告导出。

## 安全特性

- 全部解析在本地完成，不访问网络
- 不执行配置内容，不调用上传文本中的任何命令
- 仅做文本解析、规则匹配、图形绘制与本地文件保存

## 功能概览

- 配置输入：
  - 图形界面粘贴文本
  - 选择上传 `.txt` 文件
- 多厂商解析：华为 / H3C / Cisco（支持自动识别）
- 提取信息：
  - 接口状态（物理管理状态、协议状态、端口信息）
  - BGP / OSPF 邻居状态与 uptime
  - VRRP 主备与优先级
  - 路由统计（总路由、直连、静态、BGP、OSPF）
- 智能分析：自动检测协议异常、链路异常、非标准化配置提示
- 可视化：拓扑图中文标签（节点、接口、IP、邻居状态）
- 报告：导出 TXT + HTML 报告，默认目录可设为桌面

## 运行方式

### 1) GUI 模式（推荐）

```bash
python main.py --gui
```

若不传任何 CLI 参数，也会默认启动 GUI：

```bash
python main.py
```

### 2) CLI 模式

```bash
python main.py \
  --device-name Station-R1 \
  --config-file sample.txt \
  --output result.json \
  --report-html report.html \
  --report-txt report.txt \
  --vendor auto
```

## 测试

```bash
pytest -q
```

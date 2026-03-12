from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from analyzer.pipeline import run_pipeline
from analyzer.report import write_html_report

CONFIG_PATH = Path('.tool_config.json')


def get_default_output_dir() -> Path:
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            p = Path(cfg.get('output_dir', '')).expanduser()
            if p.exists() and p.is_dir():
                return p
        except (json.JSONDecodeError, OSError):
            pass
    desktop = Path.home() / 'Desktop'
    return desktop if desktop.exists() else Path.cwd()


def set_default_output_dir(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({'output_dir': str(p)}, ensure_ascii=False, indent=2), encoding='utf-8')
    return p


HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>站场网络配置智能分析小工具</title>
<style>
body { font-family: Arial, sans-serif; margin:0; background:#f3f6fb; color:#1f2937; }
.wrap{ max-width:1100px; margin:20px auto; padding:0 16px; }
.h{ background:linear-gradient(135deg,#2563eb,#06b6d4); color:#fff; padding:16px; border-radius:12px; }
.row{ display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:14px; }
.card{ background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:12px; }
label{ font-weight:600; display:block; margin-bottom:6px; }
input, select, textarea, button{ width:100%; box-sizing:border-box; border:1px solid #d1d5db; border-radius:8px; padding:8px; }
textarea{ min-height:220px; }
button{ background:#2563eb; color:white; font-weight:700; cursor:pointer; }
.dropzone{ border:2px dashed #60a5fa; border-radius:10px; padding:16px; text-align:center; background:#eff6ff; }
.muted{ color:#6b7280; font-size:12px; }
pre{ background:#0b1020; color:#d1fae5; padding:12px; border-radius:8px; overflow:auto; max-height:300px; }
.kpis{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
.kpi{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:10px; }
.badge{ display:inline-block; border-radius:999px; padding:2px 8px; color:#fff; font-size:12px; }
</style>
</head>
<body>
<div class="wrap">
  <div class="h"><h2 style="margin:0">站场网络配置智能分析小工具</h2><div>支持粘贴文本或拖拽/点击上传 txt 文件</div></div>
  <div class="row">
    <div class="card">
      <label>设备名称</label><input id="device" value="Station-R1" />
      <label style="margin-top:8px">厂商</label>
      <select id="vendor"><option value="auto">auto</option><option>huawei</option><option>h3c</option><option>cisco</option></select>
      <label style="margin-top:8px">默认输出目录（首次默认桌面）</label>
      <input id="outdir" />
      <div class="muted" style="margin:6px 0 10px">可在这里修改默认输出路径</div>

      <label>方式1：直接粘贴配置/运行态文本</label>
      <textarea id="text" placeholder="把配置文本粘贴到这里..."></textarea>

      <label style="margin-top:8px">方式2：拖拽或点击上传 txt 文件</label>
      <div id="drop" class="dropzone">拖拽 txt 到此处，或点击选择文件<input id="file" type="file" accept=".txt" style="margin-top:8px"></div>

      <button style="margin-top:10px" onclick="runAnalyze()">开始分析</button>
      <div id="msg" class="muted" style="margin-top:8px"></div>
    </div>

    <div class="card">
      <h3 style="margin-top:0">结果概览</h3>
      <div class="kpis">
        <div class="kpi"><div class="muted">接口总数</div><div id="k1">-</div></div>
        <div class="kpi"><div class="muted">BGP异常</div><div id="k2">-</div></div>
        <div class="kpi"><div class="muted">OSPF异常</div><div id="k3">-</div></div>
        <div class="kpi"><div class="muted">路由总数</div><div id="k4">-</div></div>
      </div>
      <h4>异常列表</h4>
      <div id="findings"></div>
      <h4>JSON 结果</h4>
      <pre id="json"></pre>
    </div>
  </div>
</div>
<script>
const fileInput = document.getElementById('file');
const drop = document.getElementById('drop');
let uploadedText = '';
function readFile(file){
  const r = new FileReader();
  r.onload = e => { uploadedText = e.target.result; document.getElementById('msg').innerText = `已读取文件: ${file.name}`; };
  r.readAsText(file,'utf-8');
}
fileInput.addEventListener('change', e => { if(e.target.files[0]) readFile(e.target.files[0]);});
drop.addEventListener('dragover', e=>{ e.preventDefault(); drop.style.background='#dbeafe';});
drop.addEventListener('dragleave', e=>{ e.preventDefault(); drop.style.background='#eff6ff';});
drop.addEventListener('drop', e=>{ e.preventDefault(); drop.style.background='#eff6ff'; if(e.dataTransfer.files[0]) readFile(e.dataTransfer.files[0]);});

async function init(){
  const r = await fetch('/config');
  const c = await r.json();
  document.getElementById('outdir').value = c.output_dir;
}

function sevColor(s){ return s==='high' ? '#dc2626' : (s==='medium' ? '#d97706' : '#2563eb'); }

async function runAnalyze(){
  const pasted = document.getElementById('text').value.trim();
  const text = pasted || uploadedText;
  if(!text){ alert('请粘贴文本或上传 txt 文件'); return; }
  const body = {
    device_name: document.getElementById('device').value,
    vendor: document.getElementById('vendor').value,
    text,
    output_dir: document.getElementById('outdir').value
  };
  const r = await fetch('/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const data = await r.json();
  if(!r.ok){ alert(data.error || '分析失败'); return; }

  const s = data.payload.summary;
  document.getElementById('k1').innerText = s.interface.total;
  document.getElementById('k2').innerText = s.protocol.bgp.abnormal;
  document.getElementById('k3').innerText = s.protocol.ospf.abnormal;
  document.getElementById('k4').innerText = s.routing.total;

  const findings = data.payload.findings || [];
  document.getElementById('findings').innerHTML = findings.length
    ? findings.map(f => `<div style='margin:6px 0'><span class='badge' style='background:${sevColor(f.severity)}'>${f.severity}</span> <b>${f.type}</b> - ${f.message}</div>`).join('')
    : '<div class="muted">未发现异常</div>';

  document.getElementById('json').innerText = JSON.stringify(data.payload, null, 2);
  document.getElementById('msg').innerText = `已输出 JSON: ${data.json_path} ｜ HTML报告: ${data.html_path}`;
}
init();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        p = urlparse(self.path)
        if p.path == '/':
            body = HTML.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p.path == '/config':
            self._send(200, {'output_dir': str(get_default_output_dir())})
            return
        self._send(404, {'error': 'not found'})

    def do_POST(self) -> None:
        if self.path != '/analyze':
            self._send(404, {'error': 'not found'})
            return
        length = int(self.headers.get('Content-Length', '0'))
        data = json.loads(self.rfile.read(length).decode('utf-8'))

        text = (data.get('text') or '').strip()
        if not text:
            self._send(400, {'error': 'text is required'})
            return

        device_name = (data.get('device_name') or 'Device-1').strip()
        vendor = data.get('vendor')
        vendor = None if vendor in (None, '', 'auto') else vendor

        output_dir = set_default_output_dir(data.get('output_dir') or str(get_default_output_dir()))
        payload = run_pipeline(text=text, device_name=device_name, vendor=vendor)

        safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in device_name)
        json_path = output_dir / f'{safe_name}_analysis.json'
        html_path = output_dir / f'{safe_name}_report.html'
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        write_html_report(payload, html_path)

        self._send(200, {'payload': payload, 'json_path': str(json_path), 'html_path': str(html_path)})


def run() -> None:
    server = HTTPServer(('0.0.0.0', 8787), Handler)
    print('Web tool running at http://127.0.0.1:8787')
    server.serve_forever()


if __name__ == '__main__':
    run()

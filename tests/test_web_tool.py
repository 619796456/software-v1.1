from __future__ import annotations

import json
from pathlib import Path

from app import CONFIG_PATH, get_default_output_dir, set_default_output_dir
from analyzer.pipeline import run_pipeline


SAMPLE = """
show running-config
router bgp 65100
 neighbor 172.16.0.2 remote-as 65200
exit
BGP neighbor 172.16.0.2 state Established uptime 1d
Total routes: 10 Direct: 2 Static: 1 BGP: 5 OSPF: 2
"""


def test_run_pipeline_returns_expected_keys() -> None:
    payload = run_pipeline(SAMPLE, "R1", vendor=None)
    assert set(payload.keys()) == {"parsed", "summary", "findings", "topology"}
    assert payload["parsed"]["vendor"] == "cisco"


def test_output_dir_config_roundtrip(tmp_path: Path) -> None:
    old = CONFIG_PATH.read_text(encoding='utf-8') if CONFIG_PATH.exists() else None
    try:
        target = tmp_path / 'outputs'
        set_default_output_dir(str(target))
        resolved = get_default_output_dir()
        assert resolved == target.resolve()
        raw = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        assert Path(raw['output_dir']) == target.resolve()
    finally:
        if old is None:
            if CONFIG_PATH.exists():
                CONFIG_PATH.unlink()
        else:
            CONFIG_PATH.write_text(old, encoding='utf-8')

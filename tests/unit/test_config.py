from pathlib import Path
import yaml
from dc_calib.config import preflight

ROOT=Path(__file__).resolve().parents[2]


def test_template_blocks_and_independent_cwd(tmp_path,monkeypatch):
    first=preflight('configs/session.example.yaml',ROOT)
    monkeypatch.chdir(tmp_path)
    assert preflight('configs/session.example.yaml',ROOT)==first
    assert not first['ready'] and not first['hardware_accepted']
    assert any(i['code']=='INTRINSICS' or i['field']=='intrinsics.fx' for i in first['issues'])


def test_bad_stage():
    import pytest
    with pytest.raises(ValueError):preflight('configs/session.example.yaml',ROOT,'unknown')

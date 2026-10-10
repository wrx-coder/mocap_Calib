import json
import numpy as np
from dc_calib.cli import main
from dc_mocap.geom.rotations import rotation_difference_deg


def test_full_offline_demo(tmp_path):
    path=tmp_path/'demo'
    assert main(['demo','--output',str(path)])==0
    result=json.loads((path/'result/calibration.json').read_text())
    truth=json.loads((path/'inputs/truth.json').read_text())
    assert result['status']=='synthetic_pass'
    T=np.array(result['T_R_C']);expected=np.array(truth['T_R_C'])
    assert np.linalg.norm(T[:3,3]-expected[:3,3])<.003
    assert rotation_difference_deg(T[:3,:3],expected[:3,:3])<.1
    assert 'T_torso_C' in result
    assert main(['demo','--output',str(path)])==2

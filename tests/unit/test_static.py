import numpy as np
import pytest
from dc_mocap.io.fz_csv import MocapFrame
from dc_mocap.process.static import extract_mocap_samples


def test_id_recovery_missing_pose_and_ambiguity():
    T=np.eye(4)
    frames=[MocapFrame(i*.01,{'a' if i<5 else 'b':np.array([.1,.2,1.])},T) for i in range(10)]
    rows,_=extract_mocap_samples(frames,[('s',0,.1)],'a')
    assert rows[0]['n_frames']==10
    frames[5].T_W_R=None
    rows,_=extract_mocap_samples(frames,[('s',0,.1)],'a')
    assert rows[0]['n_frames']==9
    frames[6].markers['other']=np.array([.101,.2,1.])
    with pytest.raises(ValueError):extract_mocap_samples(frames,[('s',0,.1)],'a')

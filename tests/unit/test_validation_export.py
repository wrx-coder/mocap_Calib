import numpy as np
import pytest
from dc_calib.solver.rigid import fit_rigid
from dc_calib.camera.rgbd import surface_to_center
from dc_calib.export.bundle import export_bundle
from dc_mocap.geom.transforms import make_transform,transform_points


def test_surface_scale_and_no_scale_in_rotation():
    rng=np.random.default_rng(19)
    raw=np.column_stack([rng.uniform(-.5,.5,60),rng.uniform(-.5,.5,60),rng.uniform(1,3,60)])
    T=make_transform(np.eye(3),[.1,-.05,.2])
    target=transform_points(T,surface_to_center(raw,.04,1.03))
    fit=fit_rigid(raw,target,quantity='surface',radius_m=.04,estimate_scale=True)
    assert abs(fit['depth_scale']-1.03)<1e-7
    assert np.allclose(fit['T'],T,atol=1e-7)
    assert np.isclose(np.linalg.det(fit['T'][:3,:3]),1)


def test_export_gates_and_overwrite(tmp_path):
    fit=dict(T=np.eye(4),quantity='center',radius_m=0.,depth_scale=1.)
    report=dict(validation_passed=True,mocap_frame='R',camera_frame='C')
    proof={k:True for k in ('same_center_confirmed','torso_alignment_checked','independent_holdout_confirmed','deployment_configuration_frozen')}
    real=export_bundle(tmp_path/'real',fit,report,'real')
    assert real['status']=='unverified' and 'T_torso_C' not in real
    synth=export_bundle(tmp_path/'synth',fit,report,'synthetic',T_torso_R=np.eye(4),attestation=proof)
    assert synth['status']=='synthetic_pass'
    fail=export_bundle(tmp_path/'fail',fit,{**report,'validation_passed':False},'real',T_torso_R=np.eye(4),attestation=proof)
    assert fail['status']=='validation_failed'
    with pytest.raises(FileExistsError):export_bundle(tmp_path/'real',fit,report,'real')

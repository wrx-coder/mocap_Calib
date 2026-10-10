"""Export candidates safely, never automatically touch URDF or overwrite."""
from pathlib import Path
import json
import numpy as np
from dc_mocap.geom.transforms import compose,validate_transform


def json_ready(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:json_ready(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_ready(v) for v in value]
    return value


def export_bundle(directory,fit,report,source_kind,T_torso_R=None,T_C_L=None,attestation=None,provenance=None):
    if source_kind not in ('real','synthetic'):
        raise ValueError('Unknown source kind')
    T=validate_transform(fit['T']);attestation=attestation or {}
    status='unverified'
    if not report.get('validation_passed'):
        status='validation_failed'
    elif source_kind=='synthetic':
        status='synthetic_pass'
    elif T_torso_R is not None and all(attestation.get(k) is True for k in ('same_center_confirmed','torso_alignment_checked','independent_holdout_confirmed','deployment_configuration_frozen')):
        status='hardware_accepted'
    bundle=dict(schema_version=1,status=status,source_kind=source_kind,unit='m',transform_convention='B_to_A',frames=dict(R=report['mocap_frame'],C=report['camera_frame'],torso='torso_link'),T_R_C=T,compensation=dict(quantity=fit['quantity'],radius_m=fit['radius_m'],depth_scale=fit['depth_scale']),attestation=attestation,provenance=provenance or {})
    if T_torso_R is not None:
        bundle['T_torso_R']=validate_transform(T_torso_R)
        bundle['T_torso_C']=compose(T_torso_R,T)
        if T_C_L is not None:
            bundle['T_C_L']=validate_transform(T_C_L)
            bundle['T_torso_L']=compose(bundle['T_torso_C'],T_C_L)
    directory=Path(directory)
    if directory.exists():
        raise FileExistsError(f'Choose a new versioned output directory: {directory}')
    directory.mkdir(parents=True)
    (directory/'calibration.json').write_text(json.dumps(json_ready(bundle),indent=2,allow_nan=False),encoding='utf-8')
    (directory/'report.json').write_text(json.dumps(json_ready(report),indent=2,allow_nan=False),encoding='utf-8')
    return bundle

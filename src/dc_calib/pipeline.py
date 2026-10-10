"""Complete offline point-product -> calibration candidate pipeline."""
import numpy as np
from dc_mocap.model.contracts import paired_arrays,meta_path
from dc_mocap.model.config import file_hash,load_yaml
from dc_calib.solver.rigid import fit_rigid
from dc_calib.alignment.torso import align_torso
from dc_calib.validation.static import evaluate,split_consistency
from dc_calib.export.bundle import export_bundle


def run_calibration(mocap,camera,pairs,output,radius_m=0.,estimate_scale=False,torso=None,attestation=None,rmse_limit_m=.02,min_spread_ratio=.05):
    a,b,sigma,train,rows,mm,cm=paired_arrays(mocap,camera,pairs)
    if not np.isfinite(rmse_limit_m) or rmse_limit_m<=0:
        raise ValueError('Invalid acceptance threshold')
    if mm['source_kind']!=cm['source_kind'] or mm['frame']==cm['frame'] or mm['quantity']!='center':
        raise ValueError('Incompatible source/frame/quantity')
    if train.sum()<3 or (~train).sum()<1:
        raise ValueError('Need >=3 train and >=1 independent validation positions')
    if cm['quantity']=='center' and (radius_m!=0 or estimate_scale):
        raise ValueError('Already compensated centers: do not add radius or scale')
    if cm['quantity']=='surface' and radius_m<=0:
        raise ValueError('Surface observations require an explicitly measured positive radius')
    fit=fit_rigid(a[train],b[train],sigma[train],cm['quantity'],radius_m,estimate_scale,min_spread_ratio)
    holdout=evaluate(fit,a[~train],b[~train])
    consistency=split_consistency(a[train],b[train],sigma[train],cm['quantity'],radius_m,estimate_scale)
    passed=holdout['rmse_m']<rmse_limit_m and consistency.get('available',False) and consistency['rotation_difference_deg']<.5 and consistency['translation_difference_m']<.01
    T_torso_R=None;alignment=None
    if torso:
        T_torso_R,alignment=align_torso(torso)
        if alignment['leave_one_errors_m'] and max(alignment['leave_one_errors_m'])>.01:
            passed=False
    report=dict(schema_version=1,mocap_frame=mm['frame'],camera_frame=cm['frame'],validation_passed=bool(passed),threshold_rmse_m=rmse_limit_m,holdout=holdout,split_consistency=consistency,train=evaluate(fit,a[train],b[train]),alignment=alignment,fit_spread_ratio=fit['spread_ratio'],sample_ids=[r['sample_id'] for r in rows],train_ids=[r['sample_id'] for r,t in zip(rows,train) if t],validation_ids=[r['sample_id'] for r,t in zip(rows,train) if not t])
    provenance={str(p):file_hash(p) for p in (mocap,camera,pairs,meta_path(mocap),meta_path(camera))}
    if torso:
        provenance[str(torso)]=file_hash(torso)
    report['input_metadata']={'mocap':mm,'camera':cm}
    return export_bundle(output,fit,report,mm['source_kind'],T_torso_R=T_torso_R,attestation=load_yaml(attestation) if attestation else None,provenance=provenance),report

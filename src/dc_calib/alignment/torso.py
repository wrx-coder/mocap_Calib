"""R -> torso from explicitly matched feature centers."""
import numpy as np
from dc_mocap.model.contracts import read_rows,truth
from dc_mocap.geom.transforms import transform_points
from dc_calib.solver.rigid import kabsch


def align_torso(path):
    rows=[r for r in read_rows(path) if truth(r.get('valid',True))]
    a=np.array([[float(r['p_R_'+axis+'_m']) for axis in 'xyz'] for r in rows])
    b=np.array([[float(r['q_torso_'+axis+'_m']) for axis in 'xyz'] for r in rows])
    ids=[r['feature_id'] for r in rows]
    if len(set(ids))!=len(ids):
        raise ValueError('Duplicate features')
    T=kabsch(a,b)
    errors=np.linalg.norm(transform_points(T,a)-b,axis=1)
    leave_one=[]
    if len(rows)>=4:
        for i in range(len(rows)):
            keep=np.arange(len(rows))!=i
            t=kabsch(a[keep],b[keep])
            leave_one.append(float(np.linalg.norm(transform_points(t,a[i])-b[i])))
    return T,dict(feature_count=len(rows),fit_rmse_m=float(np.sqrt(np.mean(errors**2))),leave_one_errors_m=leave_one)

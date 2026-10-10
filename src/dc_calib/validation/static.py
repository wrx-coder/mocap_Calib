"""Small independent holdout and split-consistency report."""
import numpy as np
from dc_calib.camera.rgbd import surface_to_center
from dc_calib.solver.rigid import fit_rigid
from dc_mocap.geom.transforms import transform_points
from dc_mocap.geom.rotations import rotation_difference_deg


def evaluate(fit,source,target):
    a=np.asarray(source,float);b=np.asarray(target,float)
    if not len(a):
        return {'available':False,'passed':False}
    p=surface_to_center(a,fit['radius_m'],fit['depth_scale']) if fit['quantity']=='surface' else a
    error=transform_points(fit['T'],p)-b
    norms=np.linalg.norm(error,axis=1)
    # Equal-count depth bins avoid empty fixed cutoffs.
    order=np.argsort(p[:,2]);bins=[]
    for ix in np.array_split(order,min(4,len(order))):
        bins.append(dict(count=len(ix),depth_min_m=float(p[ix,2].min()),depth_max_m=float(p[ix,2].max()),rmse_m=float(np.sqrt(np.mean(norms[ix]**2)))))
    regions=[]
    for name,ix in [('left',p[:,0]<0),('right',p[:,0]>=0),('upper',p[:,1]<0),('lower',p[:,1]>=0)]:
        if ix.any():
            regions.append(dict(region=name,count=int(ix.sum()),rmse_m=float(np.sqrt(np.mean(norms[ix]**2)))))
    return dict(available=True,regions=regions,count=len(a),rmse_m=float(np.sqrt(np.mean(norms**2))),p95_m=float(np.percentile(norms,95)),max_m=float(norms.max()),axis_rmse_m=np.sqrt(np.mean(error**2,axis=0)).tolist(),depth_bins=bins)


def split_consistency(a,b,sigma,quantity,radius_m,estimate_scale=False):
    if len(a)<8:
        return {'available':False,'reason':'Need >=8 train points for split check'}
    order=np.argsort(a[:,2]);first=order[::2];second=order[1::2]
    try:
        x=fit_rigid(a[first],b[first],sigma[first],quantity,radius_m,estimate_scale)
        y=fit_rigid(a[second],b[second],sigma[second],quantity,radius_m,estimate_scale)
    except ValueError as e:
        return {'available':False,'reason':str(e)}
    return dict(available=True,rotation_difference_deg=rotation_difference_deg(x['T'][:3,:3],y['T'][:3,:3]),translation_difference_m=float(np.linalg.norm(x['T'][:3,3]-y['T'][:3,3])),scale_difference=abs(x['depth_scale']-y['depth_scale']))

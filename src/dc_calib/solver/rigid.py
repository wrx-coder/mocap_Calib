"""Rigid Kabsch + weighted Huber refinement; optional surface depth scale."""
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from dc_mocap.geom.transforms import make_transform,transform_points,inverse
from dc_calib.camera.rgbd import surface_to_center


def spread_ratio(points):
    p=np.asarray(points,float)
    if p.ndim!=2 or p.shape[1]!=3 or len(p)<3 or not np.isfinite(p).all():
        raise ValueError('Need >=3 finite 3D points')
    eig=np.linalg.eigvalsh(np.cov(p.T))
    return float(max(eig[0],0)/eig[-1]) if eig[-1]>0 else 0.


def kabsch(source,target):
    a=np.asarray(source,float);b=np.asarray(target,float)
    if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=3 or len(a)<3 or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Need matched finite points')
    ac=a-a.mean(axis=0);bc=b-b.mean(axis=0)
    if np.linalg.matrix_rank(ac,tol=1e-9)<2 or np.linalg.matrix_rank(bc,tol=1e-9)<2:
        raise ValueError('Collinear/coincident point set')
    U,_,Vt=np.linalg.svd(ac.T@bc)
    correction=np.diag([1.,1.,np.linalg.det(Vt.T@U.T)])
    R=Vt.T@correction@U.T
    return make_transform(R,b.mean(axis=0)-R@a.mean(axis=0))


def fit_rigid(source,target,sigma=None,quantity='center',radius_m=0.,estimate_scale=False,min_spread_ratio=0.):
    a=np.asarray(source,float);b=np.asarray(target,float)
    if quantity not in ('surface','center'):
        raise ValueError('Unknown quantity')
    if quantity=='center' and (estimate_scale or radius_m!=0):
        raise ValueError('Do not compensate already computed centers')
    if quantity=='surface' and (not np.isfinite(radius_m) or radius_m<0):
        raise ValueError('Invalid physical radius')
    if sigma is None:
        sigma=np.ones_like(a)
    sigma=np.broadcast_to(np.asarray(sigma,float),a.shape)
    if not np.isfinite(sigma).all() or np.any(sigma<=0):
        raise ValueError('Invalid sigma')
    centers=surface_to_center(a,radius_m) if quantity=='surface' else a
    if min_spread_ratio and spread_ratio(centers)<min_spread_ratio:
        raise ValueError('Insufficient 3D spread: collect more depths/directions')
    T0=kabsch(centers,b)
    initial=np.r_[Rotation.from_matrix(T0[:3,:3]).as_rotvec(),T0[:3,3]]
    if estimate_scale:
        initial=np.r_[initial,1.]
    def unpack(x):
        return make_transform(Rotation.from_rotvec(x[:3]).as_matrix(),x[3:6]),float(x[6]) if estimate_scale else 1.
    def residual(x):
        T,s=unpack(x)
        p=surface_to_center(a,radius_m,s) if quantity=='surface' else a
        # Whiten in camera coordinates: do not rotate depth noise into
        # a falsely isotropic/world-axis weighting.
        return ((transform_points(inverse(T),b)-p)/sigma).ravel()
    lower=np.full(len(initial),-np.inf);upper=np.full(len(initial),np.inf)
    if estimate_scale:
        lower[-1]=.8;upper[-1]=1.2
    result=least_squares(residual,initial,loss='huber',f_scale=2.5,x_scale='jac',bounds=(lower,upper))
    if not result.success or not np.isfinite(result.x).all():
        raise ValueError('Optimization did not converge')
    if np.linalg.matrix_rank(result.jac)<len(initial):
        raise ValueError('Unidentifiable parameters')
    T,s=unpack(result.x)
    if estimate_scale and min(s-.8,1.2-s)<1e-5:
        raise ValueError('Depth scale reached physical bound')
    return dict(T=T,depth_scale=s,radius_m=radius_m,quantity=quantity,cost=float(result.cost),spread_ratio=spread_ratio(centers))

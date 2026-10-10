"""Independent RGB-D geometry. Consumes a mask, does not run a detector."""
import numpy as np
from scipy.optimize import root
from dc_mocap.geom.transforms import transform_points


def camera_from_info(info):
    """Convert saved ROS CameraInfo YAML/JSON to our camera config."""
    K=np.asarray(info['k'] if 'k' in info else info['K'],float).reshape(3,3)
    D=info.get('d',info.get('D',[]))
    frame=info.get('header',{}).get('frame_id','camera_color_optical_frame')
    return dict(schema_version=1,status='configured',model='D435i',optical_frame=frame,
                resolution_px=[info['width'],info['height']],
                intrinsics=dict(source='calibrated_CameraInfo',fx=float(K[0,0]),fy=float(K[1,1]),cx=float(K[0,2]),cy=float(K[1,2]),distortion_model=info.get('distortion_model','none'),distortion_coefficients=list(D)),
                observation=dict(pipeline='rgbd_surface',depth_semantics='color_z',depth_unit=None,ball_radius_m=None,ball_radius_already_compensated=False,depth_scale_already_compensated=False))


def pixel_ray(u,v,intrinsics):
    fx,fy,cx,cy=[float(intrinsics[k]) for k in ('fx','fy','cx','cy')]
    if not np.isfinite([u,v,fx,fy,cx,cy]).all() or min(fx,fy)<=0:
        raise ValueError('Invalid calibrated intrinsics/pixel')
    target=np.array([(u-cx)/fx,(v-cy)/fy])
    coefficients=np.asarray(intrinsics.get('distortion_coefficients') or [],float)
    model=intrinsics.get('distortion_model','none')
    if not np.isfinite(coefficients).all():
        raise ValueError('Nonfinite distortion')
    if model not in ('none','plumb_bob','brown_conrady'):
        raise ValueError('Unsupported distortion model; rectify with calibrated driver first')
    if coefficients.size and np.any(coefficients):
        if len(coefficients)!=5:
            raise ValueError('Brown model needs 5 coefficients')
        k1,k2,p1,p2,k3=coefficients
        def residual(q):
            x,y=q;r2=x*x+y*y;radial=1+k1*r2+k2*r2*r2+k3*r2**3
            return [x*radial+2*p1*x*y+p2*(r2+2*x*x)-target[0],y*radial+p1*(r2+2*y*y)+2*p2*x*y-target[1]]
        solution=root(residual,target)
        if not solution.success or np.linalg.norm(residual(solution.x))>1e-8:
            raise ValueError('Undistortion failed')
        target=solution.x
    return np.array([*target,1.])


def surface_to_center(points,radius_m,scale=1.):
    p=np.asarray(points,float)
    if p.ndim not in (1,2) or p.shape[-1]!=3 or not np.isfinite(p).all() or not np.isfinite([radius_m,scale]).all() or radius_m<0 or scale<=0 or np.any(p[...,2]<=0):
        raise ValueError('Invalid surface/radius/scale')
    norms=np.linalg.norm(p,axis=-1,keepdims=True)
    return scale*p+radius_m*p/norms


def extract_rgbd(depth,mask,camera,quantity='surface',foreground_percentile=50.,min_samples=4):
    depth=np.asarray(depth,float);mask=np.asarray(mask)
    obs=camera['observation'];intr=camera['intrinsics']
    units=obs.get('depth_unit')
    if units is None or not np.isfinite(units) or units<=0 or obs.get('depth_semantics')!='color_z':
        raise ValueError('Declare depth units and true color_z registered depth')
    if quantity not in ('surface','center') or depth.ndim!=2 or mask.shape!=depth.shape or not np.isin(mask,[0,1,False,True]).all():
        raise ValueError('Invalid mask/depth/quantity')
    resolution=camera.get('resolution_px')
    if resolution and list(resolution)!=[depth.shape[1],depth.shape[0]]:
        raise ValueError('Resolution does not match calibrated intrinsics')
    ys,xs=np.nonzero(mask)
    if len(xs)<min_samples or (xs==0).any() or (ys==0).any() or (xs==depth.shape[1]-1).any() or (ys==depth.shape[0]-1).any():
        raise ValueError('Mask empty/small/touches image boundary')
    z=depth[ys,xs]*units
    z=z[np.isfinite(z)&(z>0)]
    if len(z)<min_samples or not 0<foreground_percentile<=100:
        raise ValueError('Insufficient valid depth')
    z=z[z<=np.percentile(z,foreground_percentile)]
    median=np.median(z);mad=np.median(np.abs(z-median))
    z=z[np.abs(z-median)<=max(.001,3*mad)]
    if len(z)<min_samples:
        raise ValueError('Insufficient retained depth')
    u,v=float(xs.mean()),float(ys.mean())
    surface=pixel_ray(u,v,intr)*float(np.median(z))
    p=surface
    if quantity=='center':
        if obs.get('ball_radius_already_compensated') is not False:
            raise ValueError('Depth surface input must not already have radius compensation')
        radius=obs.get('ball_radius_m')
        if radius is None:
            raise ValueError('Measure physical ball radius')
        p=surface_to_center(surface,radius)
    return dict(x_m=float(p[0]),y_m=float(p[1]),z_m=float(p[2]),u=u,v=v,surface_depth_m=float(np.median(z)),valid_depth_count=len(z),quantity=quantity)


def native_depth_point_to_color(u,v,z_m,depth_intrinsics,T_color_depth):
    """Correct native point route; unlike merely relabelling a depth image."""
    if z_m<=0:
        raise ValueError('Invalid depth')
    return transform_points(T_color_depth,pixel_ray(u,v,depth_intrinsics)*z_m)

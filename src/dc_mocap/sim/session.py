"""Small deterministic full-chain dataset, explicitly synthetic."""
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from dc_mocap.geom.transforms import make_transform,transform_points,inverse
from dc_mocap.model.contracts import write_rows,write_product


def generate_session(directory,seed=7,count=80):
    root=Path(directory)
    if root.exists():
        raise FileExistsError(root)
    root.mkdir(parents=True)
    rng=np.random.default_rng(seed)
    centers=np.column_stack([rng.uniform(-.8,.8,count),rng.uniform(-.6,.6,count),rng.uniform(.8,3.5,count)])
    T=make_transform(Rotation.from_rotvec([.18,-.23,.12]).as_matrix(),[.08,-.04,.35])
    torso=make_transform(Rotation.from_rotvec([-.1,.06,.02]).as_matrix(),[.03,.01,-.08])
    radius=.04
    surface=centers-radius*centers/np.linalg.norm(centers,axis=1,keepdims=True)
    true_R=transform_points(T,centers)
    mocap=[];camera=[];pairs=[];windows=[];long=[];cam_frames=[]
    frame_fields=['time_s','marker_id','x','y','z','rigid_x','rigid_y','rigid_z','qx','qy','qz','qw']
    for i in range(count):
        sid=f'p{i:04d}';start=i*2.;points=[];cpoints=[]
        windows.append(dict(sample_id=sid,t_start_s=start,t_end_s=start+.9))
        for j in range(30):
            t=start+j*.03
            W_R=make_transform(Rotation.from_rotvec([0,0,.005*np.sin(t)]).as_matrix(),[.2,.1,.4])
            point=true_R[i]+rng.normal(0,.0002,3)
            q=Rotation.from_matrix(W_R[:3,:3]).as_quat()
            world=transform_points(W_R,point)
            long.append(dict(zip(frame_fields,[t,'ball' if j<15 else 'ball_restored',*world,*W_R[:3,3],*q])))
            points.append(point)
            cp=surface[i]+rng.normal(0,[.0004,.0004,.001],3)
            cpoints.append(cp)
            cam_frames.append(dict(time_s=t,x_m=cp[0],y_m=cp[1],z_m=cp[2]))
        def row(p):
            p=np.asarray(p);v=p.var(axis=0,ddof=1);mean=p.mean(axis=0)
            return dict(sample_id=sid,x_m=mean[0],y_m=mean[1],z_m=mean[2],cov_xx=v[0],cov_yy=v[1],cov_zz=v[2],n_frames=len(p))
        mocap.append(row(points));camera.append(row(cpoints))
        pairs.append(dict(sample_id=sid,mocap_segment_id=sid,camera_segment_id=sid,split='validation' if i%5==0 else 'train',valid=True,notes='synthetic'))
    base=dict(schema_version=1,source_kind='synthetic',unit='m',clock='synthetic_clock',radius_compensated=False,provenance={'generator':'independent synthetic session','seed':seed})
    write_product(root/'mocap.csv',mocap,{**base,'frame':'chest_R','quantity':'center'})
    write_product(root/'camera.csv',camera,{**base,'frame':'camera_color_optical_frame','quantity':'surface'})
    write_rows(root/'pairs.csv',pairs,list(pairs[0]))
    write_rows(root/'windows.csv',windows,list(windows[0]))
    write_rows(root/'mocap_long.csv',long,frame_fields)
    write_rows(root/'camera_frames.csv',cam_frames,list(cam_frames[0]))
    features=rng.uniform(-.2,.2,(8,3));target=transform_points(torso,features)
    feature_rows=[dict(feature_id=f'f{i}',p_R_x_m=a[0],p_R_y_m=a[1],p_R_z_m=a[2],q_torso_x_m=b[0],q_torso_y_m=b[1],q_torso_z_m=b[2],valid=True,notes='synthetic') for i,(a,b) in enumerate(zip(features,target))]
    write_rows(root/'torso.csv',feature_rows,list(feature_rows[0]))
    import json
    truth=dict(T_R_C=T.tolist(),T_torso_R=torso.tolist(),radius_m=radius)
    (root/'truth.json').write_text(json.dumps(truth,indent=2),encoding='utf-8')
    return truth

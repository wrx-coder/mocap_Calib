"""Manual windows first: robust to clock differences and marker ID changes."""
import numpy as np
from dc_mocap.io.fz_csv import points_in_r
from dc_mocap.model.contracts import read_rows


def read_windows(path):
    rows=read_rows(path)
    ids=[r['sample_id'] for r in rows]
    if len(ids)!=len(set(ids)) or not rows:
        raise ValueError('Duplicate/empty window IDs')
    windows=[]
    for r in rows:
        start,end=float(r['t_start_s']),float(r['t_end_s'])
        if not np.isfinite([start,end]).all() or end<=start:
            raise ValueError('Invalid static window')
        windows.append((r['sample_id'],start,end))
    ordered=sorted(windows,key=lambda w:w[1])
    if any(a[2]>b[1] for a,b in zip(ordered,ordered[1:])):
        raise ValueError('Overlapping windows: same position cannot leak across samples')
    return windows


def aggregate_points(sample_id,points):
    p=np.asarray(points,dtype=float)
    if p.ndim!=2 or p.shape[1]!=3 or len(p)<3 or not np.isfinite(p).all():
        raise ValueError(f'{sample_id}: need >=3 valid frames')
    mean=p.mean(axis=0)
    # Conservative per-frame spread: not divided by n under correlated depth noise.
    variance=p.var(axis=0,ddof=1)
    return dict(sample_id=sample_id,x_m=mean[0],y_m=mean[1],z_m=mean[2],cov_xx=variance[0],cov_yy=variance[1],cov_zz=variance[2],n_frames=len(p))


def extract_mocap_samples(frames,windows,marker_id=None,seed_R=None,gate_m=.03,min_fraction=.8,max_std_m=.002):
    if marker_id is None and seed_R is None:
        raise ValueError('Choose marker_id or an R-frame seed; never select arbitrary marker')
    if gate_m<=0 or not 0<min_fraction<=1 or max_std_m<=0:
        raise ValueError('Invalid extraction thresholds')
    samples=[]; report=[]
    for sid,start,end in windows:
        segment=[f for f in frames if start<=f.time_s<=end]
        reference=None if seed_R is None else np.asarray(seed_R,dtype=float)
        selected=[]; missing=0
        for f in segment:
            candidates=points_in_r(f)
            if reference is None:
                point=candidates.get(str(marker_id))
                if point is None:
                    missing+=1
                    continue
                reference=point.copy()
            # After initial identity/seed, allow IDs to change at same location.
            nearby=[p for p in candidates.values() if np.linalg.norm(p-reference)<=gate_m]
            if len(nearby)>1:
                raise ValueError(f'{sid}: multiple candidates inside spatial gate; narrow gate/manual selection')
            if not nearby:
                missing+=1
                continue
            selected.append(nearby[0])
        if not segment or len(selected)/len(segment)<min_fraction:
            raise ValueError(f'{sid}: insufficient valid marker + rigid frames')
        row=aggregate_points(sid,selected)
        std=float(np.sqrt(max(row[k] for k in ('cov_xx','cov_yy','cov_zz'))))
        if std>max_std_m:
            raise ValueError(f'{sid}: not static or noisy ({std:.6f} m)')
        samples.append(row)
        report.append(dict(sample_id=sid,total_frames=len(segment),valid_frames=len(selected),missing_frames=missing,std_max_m=std))
    return samples,report


def aggregate_camera(rows,windows,max_std_m=None):
    out=[]
    for sid,start,end in windows:
        points=[]
        for r in rows:
            if start<=float(r['time_s'])<=end:
                p=[float(r[k]) for k in ('x_m','y_m','z_m')]
                if np.isfinite(p).all():
                    points.append(p)
        item=aggregate_points(sid,points)
        if max_std_m is not None and np.sqrt(max(item[k] for k in ('cov_xx','cov_yy','cov_zz')))>max_std_m:
            raise ValueError(f'{sid}: camera static threshold exceeded')
        out.append(item)
    return out


def suggest_windows(times,points,threshold_m=.002,min_duration_s=.3):
    """Simple adjacent-motion segmentation; manual confirmation still required."""
    t=np.asarray(times,float);p=np.asarray(points,float)
    if len(t)!=len(p) or p.shape!=(len(t),3) or len(t)<2 or not np.isfinite(t).all() or np.any(np.diff(t)<=0):
        raise ValueError('Invalid ordered trajectory')
    out=[];begin=0
    for i in range(1,len(t)+1):
        boundary=i==len(t) or not np.isfinite(p[i]).all() or not np.isfinite(p[i-1]).all() or np.linalg.norm(p[i]-p[i-1])>threshold_m
        if boundary:
            if i-begin>=3 and t[i-1]-t[begin]>=min_duration_s and np.isfinite(p[begin:i]).all() and p[begin:i].std(axis=0).max()<=threshold_m:
                out.append((f's{len(out):04d}',float(t[begin]),float(t[i-1])))
            begin=i
    return out

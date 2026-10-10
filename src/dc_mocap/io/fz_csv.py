"""Read long-format or header-driven FZMotion CSV, never asset template points.

The FZ format adapter is provisional until checked against a real export.
"""
from dataclasses import dataclass
from pathlib import Path
import csv
import re
import numpy as np
from dc_mocap.geom.rotations import quaternion_to_matrix
from dc_mocap.geom.transforms import make_transform, inverse, transform_points

UNIT = {'m': 1., 'cm': .01, 'mm': .001}


@dataclass
class MocapFrame:
    time_s: float
    markers: dict
    T_W_R: object  # None means unavailable; no held pose.


def _number(s):
    try:
        v = float(s)
        return v if np.isfinite(v) else np.nan
    except (ValueError, TypeError):
        return np.nan


def _pose(xyz, quat, scale):
    if not np.isfinite(xyz).all() or not np.isfinite(quat).all():
        return None
    try:
        return make_transform(quaternion_to_matrix(quat), np.asarray(xyz)*scale)
    except ValueError:
        return None


def read_mocap(path, rigid_name, unit=None, world_axis=None, export_scale=1., zero_marker_is_missing=True):
    """world_axis retained as explicit metadata; points are converted W->R.

    Changing only W cancels in inverse(T_W_R)*p_W, so no axis permutation
    is applied to R or the optical frame. Left-handed inputs are unsupported.
    """
    if world_axis not in ('Y_up','Z_up') or export_scale != 1:
        raise ValueError('Declare right-handed Y_up/Z_up and export_scale=1')
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError('Empty mocap CSV')
    metadata={'adapter':'provisional_fz_csv','world_axis':world_axis,'export_scale':export_scale}
    if 'time_s' in rows[0]:
        if unit not in UNIT:
            raise ValueError('Long-format input requires explicit m/cm/mm')
        scale=UNIT[unit]
        records=[dict(zip(rows[0],r)) for r in rows[1:] if r]
        groups={}
        for r in records:
            t=_number(r.get('time_s'))
            if not np.isfinite(t):
                raise ValueError('Invalid frame time')
            groups.setdefault(t,[]).append(r)
        frames=[]
        for t, group in groups.items():
            markers={}; poses=[]
            for r in group:
                xyz=np.array([_number(r.get(k)) for k in ('x','y','z')])
                if np.isfinite(xyz).all() and not (zero_marker_is_missing and np.all(xyz==0)):
                    mid=r.get('marker_id','')
                    if not mid or mid in markers:
                        raise ValueError('Ambiguous marker ID in frame')
                    markers[mid]=xyz*scale
                pose=_pose([_number(r.get(k)) for k in ('rigid_x','rigid_y','rigid_z')],[_number(r.get(k)) for k in ('qx','qy','qz','qw')],scale)
                if pose is not None:
                    poses.append(pose)
            if poses and any(not np.allclose(p,poses[0],atol=1e-8) for p in poses[1:]):
                raise ValueError('Conflicting rigid poses at same time')
            frames.append(MocapFrame(t,markers,poses[0] if poses else None))
        metadata['adapter']='long_csv'
    else:
        def normalize(s):
            return re.sub(r'[\s_-]+','',s).lower()
        type_i=next((i for i,r in enumerate(rows) if any(normalize(c)=='type' for c in r[:2])),None)
        frame_i=next((i for i,r in enumerate(rows) if len(r)>1 and normalize(r[0])=='frame' and normalize(r[1])=='time'),None)
        if type_i is None or frame_i is None or frame_i < type_i+4:
            raise ValueError('Unrecognized FZ multi-row header; supply original sample, not OCR table')
        for r in rows[:type_i]:
            for j,c in enumerate(r[:-1]):
                if normalize(c)=='lengthunits':
                    metadata['header_unit']=r[j+1].strip().lower()
        header_unit=metadata.get('header_unit')
        if header_unit and unit and header_unit!=unit:
            raise ValueError('Configured unit conflicts with CSV LengthUnits')
        unit=header_unit or unit
        if unit not in UNIT:
            raise ValueError('Missing/unsupported LengthUnits; do not guess mm')
        scale=UNIT[unit]
        width=max(len(r) for r in rows[type_i:frame_i+1])
        def filled(r):
            out=[]; last=''
            for i in range(width):
                v=r[i].strip() if i<len(r) else ''
                if i>=2:
                    last=v or last
                    v=last
                out.append(v)
            return out
        types=filled(rows[type_i]);names=filled(rows[type_i+1]);ids=filled(rows[type_i+2])
        quantities=filled(rows[frame_i-1]);components=rows[frame_i]
        groups={}
        for j in range(2,min(width,len(components))):
            typ=normalize(types[j]); name=names[j]; ident=ids[j]
            quantity=normalize(quantities[j]); component=normalize(components[j])
            if typ not in ('marker','rigidbody'):
                continue
            if typ=='rigidbody' and name!=rigid_name:
                continue
            if quantity not in ('position','rotation') or component not in ('x','y','z','w'):
                continue
            key=(typ,name,ident)
            cols=groups.setdefault(key,{})
            field=(quantity,component)
            if field in cols:
                raise ValueError('Duplicate FZ field')
            cols[field]=j
        rigid=[(key,cols) for key,cols in groups.items() if key[0]=='rigidbody']
        if len(rigid)!=1:
            raise ValueError('Expected exactly one selected rigid body')
        cols=rigid[0][1]
        if not all(('rotation',c) in cols for c in ('x','y','z','w')):
            raise ValueError('Missing xyzw rigid rotation (Euler exports unsupported)')
        def values(r,cols,quantity,comps):
            return np.array([_number(r[cols[(quantity,c)]]) if (quantity,c) in cols and cols[(quantity,c)]<len(r) else np.nan for c in comps])
        frames=[]
        for r in rows[frame_i+1:]:
            if not r or not any(c.strip() for c in r):
                continue
            t=_number(r[1] if len(r)>1 else None)
            if not np.isfinite(t):
                raise ValueError('Invalid FZ frame time')
            markers={}; pose=None
            for (typ,name,ident),cols in groups.items():
                xyz=values(r,cols,'position','xyz')
                if typ=='rigidbody':
                    pose=_pose(xyz,values(r,cols,'rotation','xyzw'),scale)
                elif np.isfinite(xyz).all() and not (zero_marker_is_missing and np.all(xyz==0)):
                    mid=ident or name
                    if mid in markers:
                        raise ValueError('Duplicate marker identity')
                    markers[mid]=xyz*scale
            frames.append(MocapFrame(t,markers,pose))
    if not frames or any(b.time_s<=a.time_s for a,b in zip(frames,frames[1:])):
        raise ValueError('Empty or non-monotonic frame time')
    metadata.update(unit=unit,frame_count=len(frames),missing_pose_frames=sum(f.T_W_R is None for f in frames))
    return frames,metadata


def points_in_r(frame):
    if frame.T_W_R is None:
        return {}
    T=inverse(frame.T_W_R)
    return {k:transform_points(T,p) for k,p in frame.markers.items()}

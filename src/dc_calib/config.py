"""Small stage-aware preflight. Readiness is not hardware acceptance."""
import numpy as np
from dc_mocap.model.config import load_yaml, resolve_path, issue
from dc_mocap.model.contracts import paired_arrays


def preflight(session_file, root, stage='template'):
    if stage not in ('template','mocap_extract','camera_extract','solve'):
        raise ValueError('UNKNOWN_STAGE')
    cfg = load_yaml(resolve_path(root, str(session_file)))
    errors = []
    def required(v, field):
        if v is None or v == '' or (isinstance(v,list) and not v):
            errors.append(issue('MISSING', field, 'Provide actual value'))
            return False
        return True
    def path(v, field):
        if required(v, field):
            if not resolve_path(root, v).is_file():
                errors.append(issue('FILE_MISSING',field,str(v)))
    required(cfg.get('session_id'), 'session_id')
    if cfg.get('schema_version') != 1:
        errors.append(issue('VERSION','schema_version','Expected 1'))
    if stage in ('template','mocap_extract'):
        sc = cfg.get('source_conventions', {})
        for k in ('length_unit','world_axis','handedness','quaternion_order','quaternion_direction','clock_label'):
            required(sc.get(k), 'source_conventions.'+k)
        if sc.get('length_unit') not in ('m','cm','mm'):
            errors.append(issue('UNIT','length_unit','Expected m/cm/mm'))
        if sc.get('world_axis') not in ('Y_up','Z_up') or sc.get('handedness') != 'right':
            errors.append(issue('AXIS','source_conventions','Specify right handed Y_up/Z_up'))
        if sc.get('quaternion_order') != 'xyzw' or sc.get('quaternion_direction') != 'R_to_W':
            errors.append(issue('QUATERNION','source_conventions','Expected xyzw R_to_W'))
        if sc.get('export_scale') != 1:
            errors.append(issue('SCALE','export_scale','Use unscaled export (1)'))
        files = cfg.get('inputs',{}).get('mocap_csv',[])
        required(files,'inputs.mocap_csv')
        for f in files:
            path(f,'inputs.mocap_csv')
    if stage in ('template','camera_extract'):
        try:
            cam = load_yaml(resolve_path(root,cfg.get('camera_config')))
            intr = cam.get('intrinsics',{})
            for k in ('fx','fy','cx','cy'):
                v=intr.get(k)
                if required(v,'intrinsics.'+k) and (not isinstance(v,(int,float)) or not np.isfinite(v) or (k in ('fx','fy') and v<=0)):
                    errors.append(issue('INTRINSICS',k,'Invalid calibrated intrinsic'))
            obs=cam.get('observation',{})
            required(cam.get('optical_frame'),'optical_frame')
            if not isinstance(obs.get('depth_unit'),(int,float)) or not np.isfinite(obs['depth_unit']) or obs['depth_unit']<=0:
                errors.append(issue('DEPTH_UNITS','depth_unit','Positive metres per depth unit required'))
            if obs.get('depth_semantics') != 'color_z':
                errors.append(issue('DEPTH_GEOMETRY','depth_semantics','Reproject to color z first'))
            for k in ('ball_radius_already_compensated','depth_scale_already_compensated'):
                if not isinstance(obs.get(k),bool):
                    errors.append(issue('COMPENSATION',k,'Explicit bool required'))
            radius=obs.get('ball_radius_m')
            if radius is not None and (not isinstance(radius,(int,float)) or not np.isfinite(radius) or radius<0):
                errors.append(issue('RADIUS','ball_radius_m','Physical radius must be nonnegative'))
        except (ValueError,TypeError,OSError) as e:
            errors.append(issue('CAMERA_CONFIG','camera_config',str(e)))
    if stage=='solve':
        try:
            inputs=cfg.get('inputs',{})
            a,b,s,t,rows,mm,cm=paired_arrays(*(resolve_path(root,inputs.get(k)) for k in ('mocap_product','camera_product','sample_pairs')))
            frames=cfg.get('frames',{})
            if mm['frame']!=frames.get('mocap_rigid_body') or cm['frame']!=frames.get('camera_optical'):
                errors.append(issue('FRAME','products','Product frames do not match config'))
            if mm['source_kind']!=cm['source_kind']:
                errors.append(issue('SOURCE_KIND','products','Do not mix real and synthetic'))
            if t.sum()<3 or (~t).sum()<1:
                errors.append(issue('SPLIT','sample_pairs','Need >=3 train and independent validation'))
        except (ValueError,KeyError,TypeError,OSError) as e:
            errors.append(issue('PRODUCT','inputs',str(e)))
    return {'schema_version':1,'stage':stage,'ready':not errors and stage!='template','hardware_accepted':False,'issues':errors}

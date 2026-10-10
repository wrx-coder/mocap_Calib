"""Offline commands: no control, no detector inference, no implicit TF."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import yaml
from dc_mocap.model.config import load_yaml,file_hash
from dc_mocap.model.contracts import read_rows,write_rows,write_product
from dc_mocap.io.fz_csv import read_mocap
from dc_mocap.process.static import read_windows,extract_mocap_samples,aggregate_camera
from dc_mocap.sim.session import generate_session
from dc_calib.camera.rgbd import extract_rgbd,camera_from_info
from dc_calib.pipeline import run_calibration
from dc_calib.config import preflight
from dc_calib.export.bundle import json_ready


def main(argv=None):
    parser=argparse.ArgumentParser(description='D435i + MoCap static calibration (offline)')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('demo');p.add_argument('--output',required=True)
    p=sub.add_parser('preflight');p.add_argument('--session',required=True);p.add_argument('--root',required=True);p.add_argument('--stage',default='template')
    p=sub.add_parser('camera-info');p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('rgbd');p.add_argument('--npz',required=True);p.add_argument('--camera',required=True);p.add_argument('--quantity',choices=['surface','center'],default='surface');p.add_argument('--time-s',type=float,required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('rgbd-batch');p.add_argument('--manifest',required=True);p.add_argument('--camera',required=True);p.add_argument('--quantity',choices=['surface','center'],default='surface');p.add_argument('--output',required=True)
    p=sub.add_parser('extract-mocap');p.add_argument('--input',required=True);p.add_argument('--windows',required=True);p.add_argument('--rigid',required=True);p.add_argument('--unit',choices=['m','cm','mm']);p.add_argument('--world-axis',choices=['Y_up','Z_up'],required=True);p.add_argument('--marker-id');p.add_argument('--seed-r',type=float,nargs=3);p.add_argument('--gate-m',type=float,default=.03);p.add_argument('--output',required=True);p.add_argument('--frame',required=True);p.add_argument('--source-kind',choices=['real','synthetic'],required=True);p.add_argument('--clock',required=True)
    p=sub.add_parser('aggregate-camera');p.add_argument('--input',required=True);p.add_argument('--windows',required=True);p.add_argument('--quantity',choices=['surface','center'],required=True);p.add_argument('--output',required=True);p.add_argument('--frame',default='camera_color_optical_frame');p.add_argument('--source-kind',choices=['real','synthetic'],required=True);p.add_argument('--clock',required=True)
    p=sub.add_parser('solve');p.add_argument('--mocap',required=True);p.add_argument('--camera',required=True);p.add_argument('--pairs',required=True);p.add_argument('--torso');p.add_argument('--radius-m',type=float,default=0.);p.add_argument('--estimate-scale',action='store_true');p.add_argument('--attestation');p.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='preflight':
            result=preflight(args.session,args.root,args.stage);print(json.dumps(result,indent=2,ensure_ascii=False));return 0 if result['ready'] else 2
        if args.command=='camera-info':
            path=Path(args.output)
            if path.exists():raise FileExistsError(path)
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(yaml.safe_dump(camera_from_info(load_yaml(args.input)),sort_keys=False),encoding='utf-8')
        elif args.command=='rgbd':
            with np.load(args.npz,allow_pickle=False) as d:
                result=extract_rgbd(d['depth'],d['mask'],load_yaml(args.camera),args.quantity)
            row={k:result[k] for k in ('x_m','y_m','z_m','u','v','surface_depth_m')};row={'time_s':args.time_s,**row}
            write_rows(args.output,[row],list(row));print(json.dumps(result))
        elif args.command=='rgbd-batch':
            camera=load_yaml(args.camera);rows=[];base=Path(args.manifest).resolve().parent
            for item in read_rows(args.manifest):
                file=Path(item['npz']);file=file if file.is_absolute() else base/file
                with np.load(file,allow_pickle=False) as d:
                    result=extract_rgbd(d['depth'],d['mask'],camera,args.quantity)
                rows.append(dict(time_s=float(item['time_s']),**{k:result[k] for k in ('x_m','y_m','z_m','u','v','surface_depth_m')}))
            if not rows or any(b['time_s']<=a['time_s'] for a,b in zip(rows,rows[1:])):
                raise ValueError('Manifest empty or timestamps not increasing')
            write_rows(args.output,rows,list(rows[0]))
        elif args.command in ('extract-mocap','aggregate-camera'):
            windows=read_windows(args.windows)
            if args.command=='extract-mocap':
                frames,diagnostics=read_mocap(args.input,args.rigid,args.unit,args.world_axis)
                rows,quality=extract_mocap_samples(frames,windows,args.marker_id,args.seed_r,args.gate_m)
                quantity='center';radius_compensated=False
            else:
                rows=aggregate_camera(read_rows(args.input),windows);diagnostics={};quality=[]
                quantity=args.quantity;radius_compensated=quantity=='center'
            meta=dict(schema_version=1,frame=args.frame,unit='m',source_kind=args.source_kind,clock=args.clock,quantity=quantity,radius_compensated=radius_compensated,provenance={args.input:file_hash(args.input),args.windows:file_hash(args.windows)},diagnostics=diagnostics,quality=quality)
            write_product(args.output,rows,meta)
        elif args.command=='solve':
            bundle,report=run_calibration(args.mocap,args.camera,args.pairs,args.output,args.radius_m,args.estimate_scale,args.torso,args.attestation)
            print(json.dumps({'status':bundle['status'],'holdout':report['holdout']},indent=2));return 0 if report['validation_passed'] else 2
        elif args.command=='demo':
            root=Path(args.output)
            if root.exists():raise FileExistsError(root)
            root.mkdir(parents=True)
            truth=generate_session(root/'inputs')
            # Exercise parsing, ID change association and aggregation, not just products.
            frames,diag=read_mocap(root/'inputs/mocap_long.csv','chest_R','m','Z_up')
            rows,quality=extract_mocap_samples(frames,read_windows(root/'inputs/windows.csv'),'ball')
            meta=dict(schema_version=1,frame='chest_R',unit='m',source_kind='synthetic',clock='synthetic_clock',quantity='center',radius_compensated=False,provenance={'input_hash':file_hash(root/'inputs/mocap_long.csv')},diagnostics=diag)
            write_product(root/'extracted_mocap.csv',rows,meta)
            bundle,report=run_calibration(root/'extracted_mocap.csv',root/'inputs/camera.csv',root/'inputs/pairs.csv',root/'result',truth['radius_m'],torso=root/'inputs/torso.csv')
            print(json.dumps({'status':bundle['status'],'holdout':report['holdout'],'output':str(root)},indent=2))
            return 0 if bundle['status']=='synthetic_pass' else 2
        return 0
    except (ValueError,KeyError,TypeError,OSError) as e:
        print(f'ERROR: {e}',file=sys.stderr);return 2


if __name__=='__main__':
    raise SystemExit(main())

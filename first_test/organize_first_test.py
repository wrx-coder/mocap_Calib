#!/usr/bin/env python3
"""Package first_test data without inventing masks, poses, synchronization or target identities.

Run from any directory. Refuses existing destination sessions. Requires the previous
parse_rosbags.py export, OpenCV, numpy, PyYAML and the project's Python packages.
"""
import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

FIELDS = ['time_s', 'marker_id', 'x', 'y', 'z', 'rigid_x', 'rigid_y', 'rigid_z', 'qx', 'qy', 'qz', 'qw']


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_yaml(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding='utf-8')


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def finite_number(text):
    try:
        value = float(text)
        return value if np.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def parse_mocap(source, destination, record_id, provenance):
    with source.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f))
    metadata = dict(zip(rows[0][::2], rows[0][1::2]))
    if metadata.get('LengthUnits') != 'mm':
        raise ValueError('This session converter requires explicit mm in original header')
    type_i = next(i for i, r in enumerate(rows) if r[:2] == ['', 'Type'])
    frame_i = next(i for i, r in enumerate(rows) if r[:2] == ['Frame', 'Time'])
    types, names, ids = rows[type_i:type_i + 3]
    quantities, components = rows[frame_i - 1:frame_i + 1]
    groups = {}
    for j in range(2, len(components)):
        if types[j] not in ('Marker', 'Rigid Body') or quantities[j] not in ('Position', 'Rotation') or components[j] not in ('X', 'Y', 'Z', 'W'):
            continue
        group = groups.setdefault((types[j], names[j], ids[j]), {})
        field = (quantities[j], components[j])
        if field in group:
            raise ValueError(f'Duplicate column: {field}')
        group[field] = j
    markers, rigids, long_rows = [], [], []
    stats = {f'{kind}:{name}:{ident}': {'complete_frames': 0, 'invalid_frames': 0}
             for kind, name, ident in groups}
    previous_time = None
    for r in rows[frame_i + 1:]:
        if not r or not any(r):
            continue
        time_s = finite_number(r[1])
        if time_s is None or (previous_time is not None and time_s <= previous_time):
            raise ValueError('Invalid/nonmonotonic frame time')
        previous_time = time_s
        values = {}
        for key, cols in groups.items():
            xyz = [finite_number(r[cols[('Position', c)]]) if ('Position', c) in cols and cols[('Position', c)] < len(r) else None for c in 'XYZ']
            xyz = [v * .001 if v is not None else None for v in xyz]
            quaternion = [finite_number(r[cols[('Rotation', c)]]) if ('Rotation', c) in cols and cols[('Rotation', c)] < len(r) else None for c in 'XYZW']
            if key[0] == 'Marker':
                valid = all(v is not None for v in xyz) and xyz != [0., 0., 0.]
            else:
                valid = all(v is not None for v in xyz + quaternion) and np.linalg.norm(quaternion) > 1e-12
            stats[':'.join(key)]['complete_frames' if valid else 'invalid_frames'] += 1
            values[key] = (xyz, quaternion, valid)
        torso_keys = [key for key in groups if key[0] == 'Rigid Body' and key[1] == 'torso']
        if len(torso_keys) != 1:
            raise ValueError('Expected one exported torso body')
        torso_xyz, torso_q, torso_valid = values[torso_keys[0]]
        for (kind, name, ident), (xyz, quaternion, valid) in values.items():
            base = dict(frame_index=r[0], time_s=time_s)
            if kind == 'Marker':
                markers.append(dict(**base, marker_id=ident, marker_name=name,
                                    **dict(zip(['x_m', 'y_m', 'z_m'], xyz)), valid=valid))
                # Missing cells stay empty. Do not drop raw marker identities or hold the pose.
                long_rows.append(dict(time_s=time_s, marker_id=ident,
                                      **dict(zip(['x', 'y', 'z'], xyz)),
                                      **dict(zip(['rigid_x', 'rigid_y', 'rigid_z'], torso_xyz)),
                                      **dict(zip(['qx', 'qy', 'qz', 'qw'], torso_q))))
            else:
                rigids.append(dict(**base, rigid_name=name, rigid_id=ident,
                                   **dict(zip(['x_m', 'y_m', 'z_m'], xyz)),
                                   **dict(zip(['qx', 'qy', 'qz', 'qw'], quaternion)), valid=valid))
    destination.mkdir(parents=True, exist_ok=False)
    write_csv(destination / 'mocap_long.csv', FIELDS, long_rows)
    write_csv(destination / 'markers_world.csv', list(markers[0]), markers)
    write_csv(destination / 'rigids_world.csv', list(rigids[0]), rigids)
    torso_stat = next(v for k, v in stats.items() if k.startswith('Rigid Body:torso:'))
    meta = dict(schema_version=1, record_id=record_id, source_kind='real',
                status='converted_conventions_pending' if torso_stat['complete_frames'] else 'blocked_missing_rigid_pose',
                frame='mocap_world_as_exported', unit='m', time_unit='s', clock=f'mocap_recording:{record_id}',
                source_header=metadata, frame_count=len(rigids) // sum(key[0] == 'Rigid Body' for key in groups),
                reference_rigid_body='torso', marker_ids=[key[2] for key in groups if key[0] == 'Marker'],
                source_conventions=dict(world_axis=None, handedness=None, quaternion_order='xyzw',
                                        quaternion_direction=None, export_scale=None, start_time_timezone=None),
                identity_assignment='pending_manual_confirmation',
                missing_values='Empty CSV cells; no interpolation, zero filling or identity poses',
                provenance=provenance, diagnostics=stats,
                notes=['World coordinates only; not a static R-frame product.',
                       'Positions explicitly converted from header mm to m; no axis/rotation conversion.',
                       'long CSV uses exported torso fields without asserting R_to_W direction.',
                       'Marker IDs do not establish physical target identity.'])
    write_yaml(destination / 'mocap_long.meta.yaml', meta)
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path.insert(0, str(root / 'src'))
    from dc_calib.camera.rgbd import camera_from_info
    source = root / 'first_test'
    parsed = root / 'data/processed/first_test_parsed'
    raw = root / 'data/raw/first_test'
    processed = root / 'data/processed/first_test'
    configs = root / 'configs/local/first_test'
    reports = root / 'outputs/reports/first_test'
    for path in [raw, processed, configs, reports]:
        if path.exists():
            raise FileExistsError(path)
    camera_reports = json.loads((parsed / 'summary.json').read_text(encoding='utf-8'))
    for path in [raw, processed, configs, reports]:
        path.mkdir(parents=True)
    inventory, records, trial_rows, camera_status, mocap_status = [], [], [], [], []

    def copy_original(path, destination, label, record_id):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        original_hash, copied_hash = digest(path), digest(destination)
        if original_hash != copied_hash:
            raise ValueError(f'Copy hash mismatch: {path}')
        destination.chmod(0o444)
        entry = dict(record_id=record_id, category=label,
                     original_path=path.relative_to(root).as_posix(),
                     raw_path=destination.relative_to(root).as_posix(),
                     bytes=path.stat().st_size, sha256=original_hash,
                     status='raw_preserved_hash_verified')
        inventory.append(entry)
        return entry

    copy_original(source / 'AGENT.md', raw / 'metadata/collection_notes.md', 'collection_notes', 'session')
    for group, prefix in [('ball', 'sphere'), ('tag_board', 'board_')]:
        for index in range(1, 4):
            filename = f'{prefix}{index:02d}.csv' if group == 'ball' else f'{prefix}{index}.csv'
            record_id = f'M_{group}_{index:02d}'
            entry = copy_original(source / filename, raw / 'mocap' / group / filename, 'mocap', record_id)
            destination = processed / group / 'mocap' / record_id
            meta = parse_mocap(raw / 'mocap' / group / filename, destination, record_id,
                               {entry['raw_path']: entry['sha256']})
            mocap_status.append(meta)
            marker_stats = {k: v for k, v in meta['diagnostics'].items() if k.startswith('Marker:')}
            note = '待确认 marker 身份/坐标约定/静态窗口；不与相机强配'
            records.append(dict(record_id=record_id, target_type=group, sensor='mocap',
                                original_name=filename, frame_count=meta['frame_count'],
                                raw_path=entry['raw_path'], processed_path=destination.relative_to(root).as_posix(),
                                status=meta['status'], paired_record_id='', notes=note))
            trial_rows.append(dict(trial_id=record_id, purpose=f'first_test_{group}_mocap',
                                   mocap_file=entry['raw_path'], camera_file='',
                                   settings_file='configs/local/first_test/session.yaml',
                                   target_id=group, notes=note))
            print(record_id, meta['status'], 'markers',len(marker_stats),flush=True)
    previews = []
    for group in ['ball', 'tag_board']:
        selected = sorted([r for r in camera_reports if r['group'] == group], key=lambda r: r['recording'])
        for index, old_report in enumerate(selected, 1):
            record_id = f'C_{group}_{index:02d}'
            name = old_report['recording']
            provenance = {}
            for path in sorted((source / group / name).iterdir()):
                if path.is_file():
                    entry = copy_original(path, raw / 'camera' / group / name / path.name, 'camera_bag', record_id)
                    provenance[entry['raw_path']] = entry['sha256']
            destination = processed / group / 'camera' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Relocate already decoded products; raw recordings remain untouched.
            shutil.move(str(parsed / group / name), str(destination))
            pairs = read_csv(destination / 'rgbd_pairs.csv')
            npz_dir = destination / 'npz'
            npz_dir.mkdir()
            first_stamp = old_report['color']['first_header_timestamp_ns']
            frames = []
            for index_pair, pair in enumerate(pairs):
                color = cv2.imread(str(destination / pair['color_file']), cv2.IMREAD_COLOR)
                depth = cv2.imread(str(destination / pair['depth_file']), cv2.IMREAD_UNCHANGED)
                if color is None or depth is None or depth.dtype != np.uint16 or depth.shape != color.shape[:2]:
                    raise ValueError('RGB-D image validation failed')
                rgb = cv2.cvtColor(color, cv2.COLOR_BGR2RGB)
                path = npz_dir / f'{index_pair:06d}.npz'
                np.savez_compressed(path, rgb=rgb, depth=depth)
                stamp = int(pair['header_timestamp_ns'])
                frames.append(dict(time_s=(stamp - first_stamp) / 1e9, npz=path.relative_to(destination).as_posix(),
                                   header_timestamp_ns=stamp, color_index=pair['color_index'], depth_index=pair['depth_index'],
                                   mask_status='missing', status='blocked_missing_mask_and_depth_unit'))
            write_csv(destination / 'frames.csv', list(frames[0]), frames)
            # Only ready NPZ rows belong in the executable CLI manifest. No masks exist yet.
            write_csv(destination / 'rgbd_manifest.csv', ['time_s', 'npz'], [])
            write_csv(destination / 'camera_windows.csv', ['sample_id', 't_start_s', 't_end_s'], [])
            info = yaml.safe_load((destination / 'camera_info.yaml').read_text())
            camera = camera_from_info(info)
            camera['status'] = 'intrinsics_imported_observation_pending'
            camera['source_kind'] = 'real'
            camera['provenance'] = provenance
            camera['observation']['depth_semantics'] = None
            camera['observation']['depth_alignment_topic'] = '/camera/aligned_depth_to_color/image_raw'
            camera['observation']['depth_registration_verified'] = False
            camera['observation']['output_quantity'] = None
            camera['observation']['note'] = 'Confirm actual color_z geometry, depth units, segmentation and target radius before extraction.'
            config_path = configs / group / f'{record_id}.camera.yaml'
            write_yaml(config_path, camera)
            meta = dict(schema_version=1, source_kind='real', record_id=record_id,
                        target_type=group, status='frames_converted_observation_blocked',
                        frame=info['header']['frame_id'], clock=f'camera_header_relative:{record_id}',
                        time_unit='s', time_origin_header_ns=first_stamp, depth_unit=None,
                        depth_storage='uint16_raw_no_scaling', rgb_storage='uint8_RGB',
                        npz_keys=['rgb', 'depth'], mask_present=False,
                        executable_rgbd_manifest_rows=0, matched_frame_count=len(frames),
                        pairing_basis='exact_sensor_header_timestamp_one_to_one',
                        camera_config=config_path.relative_to(root).as_posix(), provenance=provenance,
                        blockers=['target_mask_missing', 'depth_unit_unconfirmed', 'color_z_geometry_unverified',
                                  'cross_sensor_pairing_unconfirmed', 'target_dimensions_unrecorded'],
                        notes=['NPZ is an intermediate frame archive, not yet an extract_rgbd input.',
                               'Add a binary mask for the same RGB frame, then register ready rows in rgbd_manifest.csv.',
                               'Use relative header time_s, not MP4 frame number or bag receipt clock.'])
            write_yaml(destination / 'frames.meta.yaml', meta)
            camera_status.append(dict(record_id=record_id, **old_report))
            previews.append(cv2.imread(str(destination / 'preview.jpg')))
            records.append(dict(record_id=record_id, target_type=group, sensor='camera',
                                original_name=name, frame_count=old_report['color']['count'],
                                raw_path=(raw / 'camera' / group / name).relative_to(root).as_posix(),
                                processed_path=destination.relative_to(root).as_posix(),
                                status=meta['status'], paired_record_id='',
                                notes=f'{len(frames)} 个配对 NPZ；mask/深度尺度待确认；未确认动捕对应'))
            trial_rows.append(dict(trial_id=record_id, purpose=f'first_test_{group}_camera',
                                   mocap_file='', camera_file=(raw / 'camera' / group / name).relative_to(root).as_posix(),
                                   settings_file=config_path.relative_to(root).as_posix(), target_id=group,
                                   notes='独立相机录制编号，不能当作已确认的动捕试次配对'))
            print(record_id, 'NPZ', len(frames), flush=True)
    write_csv(raw / 'file_manifest.csv', list(inventory[0]), inventory)
    write_csv(processed / 'recordings.csv', list(records[0]), records)
    write_csv(processed / 'trial_manifest.csv', ['trial_id','purpose','mocap_file','camera_file','settings_file','target_id','notes'], trial_rows)
    write_csv(processed / 'sample_pairs.csv', ['sample_id','mocap_segment_id','camera_segment_id','split','valid','notes'], [])
    write_csv(processed / 'torso_correspondences.csv', ['feature_id','p_R_x_m','p_R_y_m','p_R_z_m','q_torso_x_m','q_torso_y_m','q_torso_z_m','valid','notes'], [])
    write_csv(processed / 'target_inventory.csv', ['target_id','diameter_1_m','diameter_2_m','diameter_3_m','surface','rgb_detected','depth_valid','mocap_single_point','same_center_basis','notes'], [
        dict(target_id='ball', diameter_1_m='', diameter_2_m='', diameter_3_m='', surface='marker', rgb_detected='', depth_valid='', mocap_single_point='', same_center_basis='', notes='单 marker 靶球；物理半径和每段 target marker ID 待确认'),
        dict(target_id='tag_board', diameter_1_m='', diameter_2_m='', diameter_3_m='', surface='ARCODE_board', rgb_detected='', depth_valid='', mocap_single_point='false', same_center_basis='', notes='四角 marker；用户已知板长宽但尚未提供数值；不可按单球流程处理')])
    write_csv(processed / 'marker_roles.csv', ['record_id','marker_id','role','physical_identity','confirmed','notes'], [
        dict(record_id=m['record_id'],marker_id=mid,role='',physical_identity='',confirmed='false',notes='待确认：靶球/板角/参考刚体/其他；ID 不保证跨录制一致')
        for m in mocap_status for mid in m['marker_ids']])
    for group in ['ball', 'tag_board']:
        write_csv(processed / group / 'mocap_windows.csv', ['sample_id','t_start_s','t_end_s'], [])
    write_yaml(configs / 'targets.yaml', dict(schema_version=1, status='dimensions_pending',
        reference_rigid=dict(marker_count=4, marker_ids=None, rigid_name_in_csv='torso',
                             physical_frame_confirmed=False, notes='4 marker 刚体来自采集说明；与导出 torso 的物理对应待确认'),
        ball=dict(target_kind='single_marker', radius_m=None, marker_id_by_recording=None, same_center_confirmed=False),
        tag_board=dict(target_kind='ARCODE_board', corner_marker_count=4, width_m=None, height_m=None,
                       code_family=None, code_ids=None, corner_marker_roles=None,
                       marker_center_to_board_geometry=None, notes='长宽已知但未提供；码图案边长与整板尺寸需区分；不假设 marker 球心位于码平面')))
    session = yaml.safe_load((root / 'configs/session.example.yaml').read_text())
    session.update(session_id='first_test', status='organized_not_solver_ready', source_kind='real',
                   camera_config='configs/local/first_test/ball/C_ball_01.camera.yaml')
    session['inputs']['mocap_csv'] = [r['raw_path'] for r in records if r['sensor'] == 'mocap']
    session['inputs']['camera_recording'] = [r['raw_path'] for r in records if r['sensor'] == 'camera']
    session['inputs']['sample_pairs'] = 'data/processed/first_test/sample_pairs.csv'
    session['source_conventions'].update(length_unit='mm', export_scale=None, quaternion_order='xyzw',
                                         clock_label='per_recording_mocap_relative_time', missing_value_encoding='empty_cells')
    session['frames']['mocap_rigid_body'] = 'torso'
    session['frames']['torso'] = None
    session['frames']['camera_link'] = None
    session['static_sampling'] = {k: None for k in session['static_sampling']}
    session['notes'] = ['camera_config is only the first ball stream index; use each record camera config for extraction.',
                        'Export scale, handedness, world axis and quaternion direction require confirmation.',
                        'No static windows, target roles, train/validation split or inter-sensor pairs confirmed.',
                        'ARCODE board is a separate target model, not implemented by the single-ball solver.']
    write_yaml(configs / 'session.yaml', session)
    metadata = dict(schema_version=1, session_id='first_test', source_kind='real',
                    status='organized_not_solver_ready', frame=None, units=dict(length='m',time='s',depth='raw_uint16_unknown_scale'),
                    raw_manifest='data/raw/first_test/file_manifest.csv',
                    conventions_config='configs/local/first_test/session.yaml',
                    target_config='configs/local/first_test/targets.yaml',
                    provenance={entry['raw_path']: entry['sha256'] for entry in inventory},
                    camera_recordings=6, mocap_recordings=6, npz_frame_count=sum(r['exact_header_rgbd_pairs'] for r in camera_reports),
                    hardware_accepted=False, cross_sensor_pairing='not_confirmed',
                    blockers=['missing_masks', 'unknown_depth_scale', 'unverified_color_z', 'unconfirmed_mocap_conventions',
                              'missing_board_rigid_poses', 'target_geometry_and_marker_roles_pending',
                              'missing_static_windows_and_explicit_pairs', 'missing_independent_holdout'])
    write_yaml(processed / 'meta.yaml', metadata)
    (reports / 'camera_summary.json').write_text(json.dumps(camera_status, ensure_ascii=False, indent=2), encoding='utf-8')
    (reports / 'mocap_summary.json').write_text(json.dumps(mocap_status, ensure_ascii=False, indent=2), encoding='utf-8')
    cv2.imwrite(str(reports / 'preview_all.jpg'), np.vstack(previews))
    raw_readme = '# first_test 原始录制\n\n原始文件逐字节复制且 SHA-256 已核验，副本设为只读。源 first_test 文件未修改。\n\n- `camera/ball/`、`camera/tag_board/`：原 ROS 2 bag 与 metadata.yaml。\n- `mocap/ball/`、`mocap/tag_board/`：保留厂家多层表头 CSV，不改时间与列。\n- `metadata/collection_notes.md`：采集说明快照。\n- `file_manifest.csv`：原路径、归档路径、大小、哈希及独立录制编号。\n\n`C_*` 与 `M_*` 的相同序号只表示各自的排序，**不表示跨传感器配对**。\n'
    (raw / 'README.md').write_text(raw_readme, encoding='utf-8')
    overview = '''# first_test 数据目录与状态标记

**真实试采，已整理；未完成球心/板位姿提取，未达到求解或实机验收条件。**
所有下述路径相对项目根目录；原始 `first_test/` 录制未修改。

## 分类与文件格式

| 位置 | 内容 | 标记 |
|---|---|---|
| `data/raw/first_test/` | 原始 ROS bag、厂家 CSV、采集说明、SHA-256 清单 | 原始保留/只读副本 |
| `data/processed/first_test/ball/camera/<录制时间>/` | 单球 RGB-D 帧、NPZ、时间表、相机信息 | 帧转换完成，观测待提取 |
| `data/processed/first_test/tag_board/camera/<录制时间>/` | 板 RGB-D 帧、NPZ、时间表、相机信息 | 独立板方案，不能套单球模型 |
| `data/processed/first_test/<类别>/mocap/M_<类别>_<编号>/` | 项目长表 CSV、世界系 marker/刚体表、元数据 | 坐标约定/身份待确认 |
| `configs/local/first_test/` | CameraInfo 导入的项目相机 YAML、会话和靶标配置 | 未知参数用 null |
| `outputs/reports/first_test/` | 完整性检查、相机/动捕统计及预览 | 非外参结果 |

## 编号和身份

- `C_ball_01..03` / `C_tag_board_01..03`：各组相机按目录时间排序。
- `M_ball_01..03` / `M_tag_board_01..03`：各组动捕按 CSV 文件编号。
- 二者只是独立录制 ID，不是配对的 sample_id。`recordings.csv` 的 `paired_record_id` 故意留空。
- `trial_manifest.csv` 使用项目模板字段，每个传感器单独登记，另一侧文件留空。
- `marker_roles.csv` 列出所有原始 marker ID，物理角色待人工填写。
- `target_inventory.csv`、`configs/local/first_test/targets.yaml` 记录单球与 ARCODE 板，缺尺寸/角色不猜值。

## 相机 NPZ 与 CLI

每个配对帧 NPZ 保存 `rgb`（uint8、RGB 顺序）和 `depth`（uint16 原始值、0 为无效）。
RGB-D 仅按完全相同的 header 时间戳一对一配对，共 **1439** 个 NPZ。
`frames.csv` 有 `time_s,npz` 加时间戳/索引/状态；time_s 相对各自录制首张 RGB 的 header 时间。
**现在 NPZ 不含 mask，不能直接输入 rgbd/rgbd-batch。** 不生成全图/空白占位 mask。
`rgbd_manifest.csv` 只有项目所需 `time_s,npz` 表头，暂时无 ready 行。
得到同帧的真实二值 mask、确认深度尺度和 color_z 几何后，才可把合格 NPZ 登记进去。
`camera_windows.csv` 只有静态窗口表头，等待人工选段。
MP4 是观看副本；PNG/NPZ 和 CSV 才保留原像素和采样时间。

单球命令模板（完成前置项之后再执行）：
```bash
PYTHONPATH=src python3 -m dc_calib.cli rgbd-batch \\
  --manifest data/processed/first_test/ball/camera/20261011_173128/rgbd_manifest.csv \\
  --camera configs/local/first_test/ball/C_ball_01.camera.yaml \\
  --quantity surface --output data/processed/first_test/ball/camera_frames_01.csv
```
ARCODE 板的码型/码尺寸/四角 marker 与码平面关系未提供，当前核心 CLI 不支持直接板位姿求解。

## 动捕 CSV

`mocap_long.csv` 的字段完全匹配项目读取接口：
`time_s,marker_id,x,y,z,rigid_x,rigid_y,rigid_z,qx,qy,qz,qw`。
位置按原表头 mm 明确转换成 m；保留所有 marker（包括缺测行），刚体字段来自原 CSV 的 `torso`。
`markers_world.csv` 和 `rigids_world.csv` 另存原身份/逐帧有效性。
这些是 **世界系逐帧数据**，不是已提取的 R 系静态球心产品。缺失值为空，不平滑/不插值/不填零。
全部 CSV 原表头为 120 Hz；源世界轴、左右手、导出缩放和四元数方向尚未确认。
`mocap_long.meta.yaml` 保存单位、时钟、源表头、哈希、缺测统计和待确认事项。

- 3 份板 CSV：`Rigid0` 和 `torso` 位姿均全部缺失，8 个 marker 有坐标；须明确哪4个是板角、哪4个是参考刚体。
- 3 份单球 CSV：`torso` 位姿完整，`Rigid0` 全缺失；不能从多余散点中擅自指定靶球。
- 单球部分散点 ID 变化/缺测需确认空间关联，同一 ID 稳定不等于已证明物理身份。
- 同一单球帧刚体有效与 marker 有效才可用于后续 R 系提取。

## 配对与结果模板

`sample_pairs.csv`、`torso_correspondences.csv` 和各组 `mocap_windows.csv` 仅保留项目表头。
没有伪造配对、静态窗口、球心、协方差、留出划分或 torso 外参。
板 CSV 与相机录制的墙钟时间也不总重叠；墙钟近似相邻不构成同步证明。
板缺刚体位姿暂不能走现有 R 系球心路径，需要经确认的刚体 marker 几何重建/适配。
当前只有每类3段试采，没有经确认的独立训练/留出位置，不能声明 hardware_accepted。

## 后续需填写

1. 深度单位、color_z 注册验证、同帧目标 mask；单球实测半径。
2. 板尺寸、码族/ID、实际码边长、四角 marker 角色及球心相对板几何。
3. 4 marker 参考刚体与 `torso` 的物理对应、轴/左右手/缩放/四元数方向。
4. 相机与动捕录制对应、各自时钟静态窗口、训练/独立留出位置。

数据/config/report 默认由项目 .gitignore 忽略，请另行备份真实录制。
'''
    (processed / 'README.md').write_text(overview, encoding='utf-8')
    (configs / 'README.md').write_text('# first_test 本地配置\n\n相机 YAML 为实录 CameraInfo 导入，不是重做内参。每段单独登记溯源；当前 K/D 一致。\n`depth_unit`、`depth_semantics`、尺寸和未确认的动捕约定均保留 null，以免 preflight 把未知值当成已验证。\n查看 `data/processed/first_test/README.md` 与 `outputs/reports/first_test/readiness.md`。\n', encoding='utf-8')
    (source / 'README.md').write_text('# first_test 原始来源与整理入口\n\n本目录原始 bag/CSV 未修改；采集背景见 [AGENT.md](AGENT.md)。\n\n- [整理说明与格式](../data/processed/first_test/README.md)\n- [原始归档清单](../data/raw/first_test/file_manifest.csv)\n- [录制索引](../data/processed/first_test/recordings.csv)\n- [待确认事项与校验报告](../outputs/reports/first_test/readiness.md)\n- [本地配置](../configs/local/first_test/README.md)\n\n脚本：`parse_rosbags.py` 解码；`organize_first_test.py` 分类、转项目长表/帧NPZ、登记溯源。脚本拒绝覆盖已存在的会话目录。\n', encoding='utf-8')
    # Preserve the old export index and point to its relocated frame directories.
    (parsed / 'MOVED.md').write_text('# 已分类迁移\n\n帧目录已迁移到 `../first_test/ball/camera/` 与 `../first_test/tag_board/camera/`。\n原 summary/README 保留为首次解析历史记录；新会话入口为 `../first_test/README.md`。\n', encoding='utf-8')
    print('Packaging complete; run validate_first_test.py for final audit.', flush=True)


if __name__ == '__main__':
    main()

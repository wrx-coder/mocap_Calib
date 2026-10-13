#!/usr/bin/env python3
"""Audit first_test archives and conversions; not a physical calibration acceptance test."""
import csv
import hashlib
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'src'))
from dc_calib.config import preflight
from dc_mocap.io.fz_csv import read_mocap


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    processed = ROOT / 'data/processed/first_test'
    reports = ROOT / 'outputs/reports/first_test'
    manifest = csv_rows(ROOT / 'data/raw/first_test/file_manifest.csv')
    mutable_source_snapshots = []
    for item in manifest:
        original, raw = ROOT / item['original_path'], ROOT / item['raw_path']
        assert item['sha256'] == digest(raw), item
        assert raw.stat().st_size == int(item['bytes'])
        if item['category'] in ('collection_notes', 'marker_role_notes'):
            if digest(original) != item['sha256']:
                mutable_source_snapshots.append(item['raw_path'])
        else:
            assert digest(original) == item['sha256'], item
            assert original.stat().st_size == int(item['bytes'])
        assert raw.stat().st_mode & 0o222 == 0, raw
    records = csv_rows(processed / 'recordings.csv')
    assert len(records) == 12 and all(not r['paired_record_id'] for r in records)
    frames_verified = 0
    mocap_frames = 0
    missing_rigid_frames = 0
    for record in records:
        directory = ROOT / record['processed_path']
        if record['sensor'] == 'camera':
            frames = csv_rows(directory / 'frames.csv')
            meta = yaml.safe_load((directory / 'frames.meta.yaml').read_text())
            assert len(frames) == meta['matched_frame_count']
            assert csv_rows(directory / 'rgbd_manifest.csv') == []
            assert csv_rows(directory / 'camera_windows.csv') == []
            assert all(float(b['time_s']) > float(a['time_s']) for a, b in zip(frames, frames[1:]))
            color_rows = csv_rows(directory / 'color_frames.csv')
            depth_rows = csv_rows(directory / 'depth_frames.csv')
            for frame in frames:
                c, d = color_rows[int(frame['color_index'])], depth_rows[int(frame['depth_index'])]
                stamp = int(frame['header_timestamp_ns'])
                assert stamp == int(c['header_timestamp_ns']) == int(d['header_timestamp_ns'])
                assert abs(float(frame['time_s']) - (stamp - meta['time_origin_header_ns']) / 1e9) < 1e-12
                with np.load(directory / frame['npz'], allow_pickle=False) as arrays:
                    assert set(arrays.files) == {'depth', 'rgb'}
                    assert arrays['depth'].dtype == np.uint16 and arrays['rgb'].dtype == np.uint8
                    assert np.array_equal(arrays['depth'], cv2.imread(str(directory / d['file']), cv2.IMREAD_UNCHANGED))
                    assert np.array_equal(arrays['rgb'], cv2.cvtColor(cv2.imread(str(directory / c['file'])), cv2.COLOR_BGR2RGB))
                frames_verified += 1
            config = yaml.safe_load((ROOT / meta['camera_config']).read_text())
            info = yaml.safe_load((directory / 'camera_info.yaml').read_text())
            assert config['intrinsics']['fx'] == info['k'][0]
            assert config['intrinsics']['fy'] == info['k'][4]
            assert config['observation']['depth_unit'] is None
            assert config['observation']['depth_semantics'] is None
        else:
            # Z_up here is only a controlled parser comparison argument. The parser
            # does not reorient W/R. This audit does NOT establish the physical axis.
            original, _ = read_mocap(ROOT / record['raw_path'], 'torso', 'mm', 'Z_up')
            converted, _ = read_mocap(directory / 'mocap_long.csv', 'torso', 'm', 'Z_up')
            assert len(original) == len(converted) == int(record['frame_count'])
            for a, b in zip(original, converted):
                assert a.time_s == b.time_s and a.markers.keys() == b.markers.keys()
                assert all(np.array_equal(a.markers[k], b.markers[k]) for k in a.markers)
                if a.T_W_R is None:
                    assert b.T_W_R is None
                    missing_rigid_frames += 1
                else:
                    assert np.allclose(a.T_W_R, b.T_W_R, rtol=0, atol=1e-12)
                mocap_frames += 1
        print('Verified', record['record_id'], flush=True)
    assert frames_verified == 1439
    assert mocap_frames == 2550
    static_rows = csv_rows(processed / 'static/all_marker_positions.csv')
    assert len(static_rows) == 33
    for record in records:
        if record['sensor'] != 'mocap':
            continue
        original, _ = read_mocap(ROOT / record['raw_path'], 'torso', 'mm', 'Z_up')
        for row in [r for r in static_rows if r['record_id'] == record['record_id']]:
            points = [frame.markers[row['marker_id']] for frame in original if row['marker_id'] in frame.markers]
            assert len(points) == int(row['valid_frames'])
            assert int(row['total_frames']) == len(original)
            actual = [float(row[k]) for k in ['x_m', 'y_m', 'z_m']]
            assert np.allclose(actual, np.mean(points, axis=0), rtol=0, atol=1e-12)
            assert row['frame'] == 'mocap_world_as_exported' and row['length_unit'] == 'm'
    assert len([r for r in static_rows if r['role'] == 'board_corner']) == 12
    assert len([r for r in static_rows if r['role'] == 'reference_rigid_body']) == 12
    assert len([r for r in static_rows if r['role'] == 'sphere_target' and r['role_status'] == 'inferred_unconfirmed']) == 3
    for name in ['sample_pairs.csv', 'torso_correspondences.csv']:
        assert csv_rows(processed / name) == []
    readiness = {stage: preflight('configs/local/first_test/session.yaml', ROOT, stage)
                 for stage in ['template', 'mocap_extract', 'camera_extract', 'solve']}
    assert all(not value['ready'] and not value['hardware_accepted'] for value in readiness.values())
    audit = dict(schema_version=1, session_id='first_test', source_kind='real',
                 status='file_integrity_and_conversion_verified_not_calibration_accepted',
                 archived_file_hashes_verified=len(manifest),
                 historical_note_snapshots_with_changed_live_source=mutable_source_snapshots,
                 static_marker_positions_verified=len(static_rows),
                 npz_frames_pixel_verified=frames_verified,
                 mocap_frames_numeric_equivalence_verified=mocap_frames,
                 mocap_frames_missing_torso_pose=missing_rigid_frames,
                 cross_sensor_pairing_confirmed=False, masks_generated=False, hardware_accepted=False,
                 parser_comparison_note='Z_up is a comparison-only argument; physical axis/direction remain unconfirmed.',
                 preflight=readiness)
    (reports / 'audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# first_test 完整性与就绪状态', '',
             '**文件完整性和格式转换核验通过；尚未满足观测提取/外参求解条件。**', '',
             f'- {len(manifest)} 个归档文件 SHA-256 与登记一致，副本为只读；原 bag/CSV 与来源一致。',
             '- 采集说明会更新，旧说明快照保留原哈希，最新说明另存哈希版本，不要求历史快照与当前文本相同。',
             f'- {len(static_rows)} 个 World 系静态 marker 坐标核验通过（每次分别取完整 XYZ 帧均值、mm→m）；无跨次平均或抖动指标。',
             f'- {frames_verified} 个配对 NPZ 与 PNG 的 RGB/深度像素逐一一致；uint8 RGB + uint16 depth。',
             f'- {mocap_frames} 个动捕帧与原始 CSV 数值/缺测/ID 等价，位置 mm→m。',
             f'- {missing_rigid_frames} 个动捕帧缺 torso 位姿，均来自3次板采集；没有补值。',
             '- 项目读取器原表/长表数值对比通过，不代表物理轴、手性或四元数方向已确认。',
             '- 每段独立时钟；相机/动捕配对、静态窗口、marker身份和留出划分尚未确认。',
             '- 未生成假 mask/球心/板位姿/torso对应或外参。', '',
             '## Preflight（预期阻塞）', '']
    for stage, value in readiness.items():
        lines += [f'### {stage}', '', f"ready: {str(value['ready']).lower()}", '']
        for issue in value['issues']:
            lines.append(f"- `{issue['code']}` / `{issue['field']}`：{issue['message']}")
        lines.append('')
    lines += ['## 下一步', '',
              '动捕以后续静态表 `data/processed/first_test/static/README.md` 为入口，不按运动轨迹或时间段抖动处理。',
              '按会话说明确认靶标尺寸、角色/候选身份、坐标约定、深度尺度/几何与跨传感器静态采集对应。',
              '参考四点跨次几何变化尚未核查，不能直接共用刚体模板。',
              '同帧真实 mask 完成后，才将 NPZ 登记入各段 `rgbd_manifest.csv`。',
              '完整机器可读核验见同目录 `audit.json`。', '']
    (reports / 'readiness.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({k: v for k, v in audit.items() if k != 'preflight'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

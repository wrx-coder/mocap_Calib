#!/usr/bin/env python3
"""Read-only ROS 2 SQLite bag export; requires rclpy, sensor_msgs, numpy, OpenCV, PyYAML."""
import argparse
import csv
import json
import sqlite3
from pathlib import Path

import cv2
import numpy as np
import yaml
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CameraInfo, Image

COLOR = '/camera/color/image_raw'
DEPTH = '/camera/aligned_depth_to_color/image_raw'
INFO = '/camera/color/camera_info'


def header_ns(msg):
    return msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nanosec


def image_array(msg):
    formats = {'rgb8': ('u1', 3), 'bgr8': ('u1', 3), '16UC1': ('u2', 1)}
    if msg.encoding not in formats:
        raise ValueError(f'Unsupported encoding: {msg.encoding}')
    dtype, channels = formats[msg.encoding]
    dtype = np.dtype(('>' if msg.is_bigendian else '<') + dtype)
    width_bytes = msg.width * channels * dtype.itemsize
    if msg.step < width_bytes or len(msg.data) != msg.height * msg.step:
        raise ValueError('Invalid image stride/data length')
    rows = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.step)
    arr = rows[:, :width_bytes].copy().view(dtype).reshape(msg.height, msg.width, channels)
    if channels == 1:
        return arr[:, :, 0].astype(np.uint16)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR) if msg.encoding == 'rgb8' else arr


def camera_dict(msg):
    return {
        'header': {'stamp': {'sec': msg.header.stamp.sec, 'nanosec': msg.header.stamp.nanosec},
                   'frame_id': msg.header.frame_id},
        'height': msg.height, 'width': msg.width,
        'distortion_model': msg.distortion_model,
        'd': [float(v) for v in msg.d], 'k': [float(v) for v in msg.k],
        'r': [float(v) for v in msg.r], 'p': [float(v) for v in msg.p],
        'binning_x': msg.binning_x, 'binning_y': msg.binning_y,
        'roi': {k: getattr(msg.roi, k) for k in
                ['x_offset', 'y_offset', 'height', 'width', 'do_rectify']},
    }


def save_csv(path, fields, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def timing(rows):
    stamps = np.array([r['header_timestamp_ns'] for r in rows], dtype=np.int64)
    diffs = np.diff(stamps) / 1e9
    positive = diffs[diffs > 0]
    median = float(np.median(positive)) if len(positive) else None
    return {
        'count': len(rows),
        'first_header_timestamp_ns': int(stamps[0]) if len(stamps) else None,
        'last_header_timestamp_ns': int(stamps[-1]) if len(stamps) else None,
        'first_bag_timestamp_ns': rows[0]['bag_timestamp_ns'] if rows else None,
        'last_bag_timestamp_ns': rows[-1]['bag_timestamp_ns'] if rows else None,
        'header_span_s': float((stamps[-1] - stamps[0]) / 1e9) if len(stamps) > 1 else 0,
        'mean_fps': float((len(stamps) - 1) * 1e9 / (stamps[-1] - stamps[0]))
                    if len(stamps) > 1 and stamps[-1] > stamps[0] else None,
        'median_interval_ms': median * 1000 if median else None,
        'max_interval_ms': float(diffs.max() * 1000) if len(diffs) else None,
        'gaps_gt_1_5_median': int(np.sum(diffs > 1.5 * median)) if median else 0,
        'duplicate_header_timestamps': int(len(stamps) - len(np.unique(stamps))),
        'backward_header_steps': int(np.sum(diffs < 0)),
    }


def export_bag(bag, output):
    dbs = sorted(bag.glob('*.db3'))
    if len(dbs) != 1:
        raise ValueError(f'{bag}: expected exactly one SQLite file')
    output.mkdir(parents=True, exist_ok=False)
    for folder in ['color', 'depth']:
        (output / folder).mkdir()
    rows = {COLOR: [], DEPTH: [], INFO: []}
    layouts = {COLOR: set(), DEPTH: set()}
    depth_valid, depth_samples = [], []
    first_info, intrinsics_signatures = None, set()
    connection = sqlite3.connect(dbs[0].resolve().as_uri() + '?mode=ro', uri=True)
    connection.execute('PRAGMA query_only=ON')
    topics = {tid: (name, typ, serialization) for tid, name, typ, serialization in
              connection.execute('SELECT id,name,type,serialization_format FROM topics')}
    bounds = connection.execute('SELECT min(timestamp),max(timestamp),count(*) FROM messages').fetchone()
    samples = []
    color_total = connection.execute('SELECT count(*) FROM messages WHERE topic_id IN '
                                    '(SELECT id FROM topics WHERE name=?)', (COLOR,)).fetchone()[0]
    sample_indices = set(np.linspace(0, color_total - 1, 3, dtype=int)) if color_total else set()
    with (output / 'camera_info_all.jsonl').open('w', encoding='utf-8') as info_file:
        for tid, bag_ns, data in connection.execute('SELECT topic_id,timestamp,data FROM messages ORDER BY timestamp,id'):
            name, typ, serialization = topics[tid]
            if name not in rows:
                continue
            if serialization != 'cdr':
                raise ValueError(f'Unsupported serialization: {serialization}')
            expected = 'sensor_msgs/msg/CameraInfo' if name == INFO else 'sensor_msgs/msg/Image'
            if typ != expected:
                raise ValueError(f'{name}: unexpected type {typ}')
            msg = deserialize_message(data, CameraInfo if name == INFO else Image)
            index = len(rows[name])
            row = {'index': index, 'bag_timestamp_ns': bag_ns,
                   'header_timestamp_ns': header_ns(msg), 'frame_id': msg.header.frame_id}
            if name == INFO:
                entry = camera_dict(msg)
                info_file.write(json.dumps({'bag_timestamp_ns': bag_ns, **entry}) + '\n')
                first_info = entry if first_info is None else first_info
                signature = {k: v for k, v in entry.items() if k != 'header'}
                intrinsics_signatures.add(json.dumps(signature, sort_keys=True))
            else:
                frame = image_array(msg)
                folder = 'color' if name == COLOR else 'depth'
                relative = f'{folder}/{index:06d}.png'
                if not cv2.imwrite(str(output / relative), frame, [cv2.IMWRITE_PNG_COMPRESSION, 3]):
                    raise RuntimeError(f'Failed to write {relative}')
                row.update({'file': relative, 'encoding': msg.encoding,
                            'width': msg.width, 'height': msg.height})
                layouts[name].add((msg.width, msg.height, msg.encoding, msg.header.frame_id))
                if name == COLOR and index in sample_indices:
                    thumb = cv2.resize(frame, (480, 360))
                    cv2.putText(thumb, f'{bag.name} frame {index}', (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
                    samples.append(thumb)
                if name == DEPTH:
                    valid = frame[frame > 0]
                    fraction = float(len(valid) / frame.size)
                    row['valid_fraction'] = fraction
                    quantiles = np.percentile(valid, [5, 50, 95]).tolist() if len(valid) else [None] * 3
                    row.update(dict(zip(['depth_raw_p05', 'depth_raw_p50', 'depth_raw_p95'], quantiles)))
                    depth_valid.append(fraction)
                    if len(valid):
                        depth_samples.append(quantiles)
            rows[name].append(row)
    connection.close()
    for name, filename in [(COLOR, 'color_frames.csv'), (DEPTH, 'depth_frames.csv'), (INFO, 'camera_info_frames.csv')]:
        if rows[name]:
            save_csv(output / filename, list(rows[name][0]), rows[name])
    if first_info:
        (output / 'camera_info.yaml').write_text(yaml.safe_dump(first_info, sort_keys=False), encoding='utf-8')
    # Exact sensor header timestamps only: do not match unrelated clocks or reuse depth frames.
    depth_by_stamp = {}
    for row in rows[DEPTH]:
        depth_by_stamp.setdefault(row['header_timestamp_ns'], []).append(row)
    pairs, used_depth = [], set()
    for color in rows[COLOR]:
        candidates = depth_by_stamp.get(color['header_timestamp_ns'], [])
        depth = next((r for r in candidates if r['index'] not in used_depth), None)
        if depth is None:
            continue
        used_depth.add(depth['index'])
        pairs.append({'color_index': color['index'], 'depth_index': depth['index'],
                      'header_timestamp_ns': color['header_timestamp_ns'],
                      'color_file': color['file'], 'depth_file': depth['file'],
                      'depth_minus_color_bag_ms': (depth['bag_timestamp_ns'] - color['bag_timestamp_ns']) / 1e6})
    save_csv(output / 'rgbd_pairs.csv', ['color_index', 'depth_index', 'header_timestamp_ns',
             'color_file', 'depth_file', 'depth_minus_color_bag_ms'], pairs)
    color_timing = timing(rows[COLOR])
    # MP4 is a constant-rate viewing copy; original timing is preserved in CSV.
    if rows[COLOR]:
        fps = 1000 / color_timing['median_interval_ms'] if color_timing['median_interval_ms'] else 30.0
        size = (rows[COLOR][0]['width'], rows[COLOR][0]['height'])
        video = cv2.VideoWriter(str(output / 'color.mp4'), cv2.VideoWriter_fourcc(*'mp4v'), fps, size)
        if not video.isOpened():
            raise RuntimeError('MP4 VideoWriter could not open')
        try:
            for row in rows[COLOR]:
                frame = cv2.imread(str(output / row['file']))
                if frame is None or frame.shape[:2] != (size[1], size[0]):
                    raise ValueError('Color frame missing or dimensions changed')
                video.write(frame)
        finally:
            video.release()
    preview = np.hstack(samples) if samples else None
    if preview is not None:
        cv2.imwrite(str(output / 'preview.jpg'), preview)
    report = {
        'source': str(bag.resolve()), 'bag_duration_s': (bounds[1] - bounds[0]) / 1e9,
        'total_messages': bounds[2], 'topics': [dict(name=n, type=t, serialization=s) for n, t, s in topics.values()],
        'color': color_timing, 'depth': timing(rows[DEPTH]), 'camera_info': timing(rows[INFO]),
        'image_layouts': {n: [list(v) for v in sorted(layout)] for n, layout in layouts.items()},
        'camera_info_unique_configurations': len(intrinsics_signatures),
        'exact_header_rgbd_pairs': len(pairs), 'unpaired_color_frames': len(rows[COLOR]) - len(pairs),
        'unpaired_depth_frames': len(rows[DEPTH]) - len(pairs),
        'depth_units_m': None,
        'depth_units_note': '16UC1 raw values preserved. No depth scale topic recorded; confirm device depth_units before converting to meters.',
        'mean_depth_valid_fraction': float(np.mean(depth_valid)) if depth_valid else None,
        'median_frame_depth_raw_quantiles_p05_p50_p95': np.median(depth_samples, axis=0).tolist() if depth_samples else None,
        'bag_minus_header_first_color_s': (rows[COLOR][0]['bag_timestamp_ns'] - rows[COLOR][0]['header_timestamp_ns']) / 1e9 if rows[COLOR] else None,
        'mp4_note': 'Lossy constant-rate preview; use lossless PNG and timestamp CSV for calibration.',
    }
    (output / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{bag}: RGB={len(rows[COLOR])}, depth={len(rows[DEPTH])}, exact pairs={len(pairs)}', flush=True)
    return report, preview


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--output', type=Path, required=True, help='New output directory; refuses overwrite')
    args = parser.parse_args()
    bags = [(group, bag) for group in ['ball', 'tag_board']
            for bag in sorted((args.input / group).iterdir()) if bag.is_dir() and list(bag.glob('*.db3'))]
    if not bags:
        raise ValueError('No ROS bags found')
    args.output.mkdir(parents=True, exist_ok=False)
    reports, previews = [], []
    for group, bag in bags:
        report, preview = export_bag(bag, args.output / group / bag.name)
        reports.append({'group': group, 'recording': bag.name, **report})
        if preview is not None:
            previews.append(preview)
    (args.output / 'summary.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    if previews:
        cv2.imwrite(str(args.output / 'preview_all.jpg'), np.vstack(previews))
    lines = ['# 首次试采 ROS 2 bag 解析', '',
             '| 类型 | 录制 | bag时长(s) | RGB帧 | 深度帧 | RGB平均fps | 精确配对 | 未配对RGB |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in reports:
        lines.append(f"| {r['group']} | {r['recording']} | {r['bag_duration_s']:.3f} | {r['color']['count']} | {r['depth']['count']} | {r['color']['mean_fps']:.2f} | {r['exact_header_rgbd_pairs']} | {r['unpaired_color_frames']} |")
    lines += ['', '## 导出内容', '',
              '- `color.mp4`：便于播放的有损、固定帧率预览；不替代原始时序。',
              '- `color/*.png`：无损彩色帧（文件由 OpenCV 写入，读取时是 BGR）。',
              '- `depth/*.png`：无损 16 位原始深度值，0 视为无效。',
              '- `*_frames.csv`：逐帧 bag/header 时间戳（整数纳秒）及图像信息。',
              '- `rgbd_pairs.csv`：仅按完全相同的 header 时间戳一对一配对，不复用深度帧。',
              '- `camera_info.yaml`：首帧内参；`camera_info_all.jsonl` 保存所有 CameraInfo。',
              '- `summary.json`：帧率、间隔异常、深度有效比例和时钟偏移等统计。',
              '- `preview_all.jpg`：每段的首/中/末彩色帧。', '',
              '## 注意', '',
              '深度单位未由录制数据证明，不能直接假设 1 个原始值等于 1 mm。需确认设备 depth_units。',
              'bag 接收时间与传感器 header 时间并非同一时钟；不可直接与动捕 CSV 时间混用。',
              '已对齐深度话题名称和 frame_id 不构成深度几何/实际注册准确性的验证。',
              '本次只解析相机录制，尚未提取球心/标定板位姿或完成动捕配对、外参标定。', '']
    (args.output / 'README.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    main()

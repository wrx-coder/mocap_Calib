#!/usr/bin/env python3
"""Integrate current static-position/role notes into the classified session.

Existing source CSV and archived recordings remain untouched. Each sampling file
stays independent. Mean XYZ uses complete finite triples, no jitter/covariance.
"""
import csv
import hashlib
import json
import shutil
import statistics
from pathlib import Path

import yaml
from export_static_positions import static_rows
from parse_mocap_csv import parse_csv

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'first_test'
RAW = ROOT / 'data/raw/first_test'
PROCESSED = ROOT / 'data/processed/first_test'
CONFIG = ROOT / 'configs/local/first_test'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding='utf-8')


def main():
    inventory = read_csv(RAW / 'file_manifest.csv')
    snapshot_provenance = {}
    for name in ['AGENT.md', 'marker_roles.json']:
        source = SOURCE / name
        sha = digest(source)
        destination = RAW / 'metadata' / f'{source.stem}_{sha[:12]}{source.suffix}'
        if not destination.exists():
            shutil.copy2(source, destination)
            destination.chmod(0o444)
        if digest(destination) != sha:
            raise ValueError(f'Snapshot hash mismatch: {destination}')
        relative = destination.relative_to(ROOT).as_posix()
        snapshot_provenance[relative] = sha
        if not any(row['raw_path'] == relative for row in inventory):
            inventory.append(dict(record_id='session', category='collection_notes' if name == 'AGENT.md' else 'marker_role_notes',
                                  original_path=source.relative_to(ROOT).as_posix(), raw_path=relative,
                                  bytes=source.stat().st_size, sha256=sha, status='versioned_source_snapshot_hash_verified'))
    write_csv(RAW / 'file_manifest.csv', list(inventory[0]), inventory)
    roles = json.loads((SOURCE / 'marker_roles.json').read_text())
    write_yaml(CONFIG / 'marker_roles.yaml', dict(schema_version=1, source_kind='real',
               status='geometry_identified_and_candidate_unconfirmed', roles=roles,
               provenance=snapshot_provenance, human_confirmed=False))
    records = read_csv(PROCESSED / 'recordings.csv')
    combined, role_rows, static_index = [], [], []
    fields = ['record_id','source_file','data_name','marker_id','role','role_status','board_corner_order',
              'x_m','y_m','z_m','frame','length_unit','valid_frames','total_frames','method']
    for record in records:
        if record['sensor'] != 'mocap':
            continue
        source = ROOT / record['raw_path']
        destination = ROOT / record['processed_path']
        data = parse_csv(source)
        if data.metadata['LengthUnits'] != 'mm' or data.metadata['CoordinateSpace'] != 'World':
            raise ValueError('Static conversion requires explicit mm / World header')
        rows = []
        for item in static_rows(source, roles):
            # Verify the independent static exporter against the actual complete triples.
            triples = data.series('Marker', item['marker_id'], 'Position', ('X', 'Y', 'Z'))
            valid = [p for p in triples if all(v is not None for v in p)]
            expected = [statistics.mean(axis) for axis in zip(*valid)] if valid else [None] * 3
            assert [item['x'],item['y'],item['z']] == expected
            rows.append(dict(record_id=record['record_id'], source_file=item['file'], data_name=item['data_name'],
                             marker_id=item['marker_id'],role=item['role'],role_status=item['role_status'],
                             board_corner_order=item['board_corner_order'],
                             **dict(zip(['x_m','y_m','z_m'], [v * .001 if v is not None else None for v in expected])),
                             frame='mocap_world_as_exported', length_unit='m', valid_frames=len(valid),
                             total_frames=len(data.rows), method='mean_of_complete_xyz_frames'))
            role_rows.append(dict(record_id=record['record_id'],marker_id=item['marker_id'],role=item['role'],
                                  role_status=item['role_status'],board_corner_order=item['board_corner_order'],
                                  human_confirmed='false',
                                  notes='Geometry-inferred role, not manually confirmed; no cross-record rigid template' if item['role_status']=='geometry_identified' else 'Target candidate only' if item['role_status']=='inferred_unconfirmed' else 'Unclassified'))
        static = destination / 'static'
        write_csv(static / 'marker_positions.csv', fields, rows)
        for role, filename in [('board_corner','board_corners.csv'),('reference_rigid_body','reference_rigid_markers.csv'),
                               ('sphere_target','target_candidates.csv'),('unclassified','unclassified_markers.csv')]:
            subset = [r for r in rows if r['role'] == role]
            if subset:
                write_csv(static / filename, fields, subset)
        source_entry = next(r for r in inventory if r['raw_path'] == record['raw_path'])
        write_yaml(static / 'marker_positions.meta.yaml', dict(schema_version=1,record_id=record['record_id'],
                   source_kind='real',status='static_world_positions_roles_not_human_confirmed',
                   frame='mocap_world_as_exported',unit='m',quantity='marker_center',
                   method='arithmetic_mean_of_complete_xyz_per_file_per_marker',
                   time_series_used_downstream=False, cross_record_averaging=False, covariance_computed=False,
                   provenance={record['raw_path']:source_entry['sha256'],**snapshot_provenance},
                   notes=['No time interval, velocity, acceleration, jitter or fabricated covariance.',
                          'This is NOT the R-frame solver static-product schema.',
                          'Reference marker geometry varies across board recordings; do not share a fixed rigid template.',
                          'Board perimeter order is not an image corner orientation.',
                          '101642 is an inferred sphere candidate, not a confirmed physical identity.']))
        combined.extend(rows)
        record['primary_static_path'] = (static / 'marker_positions.csv').relative_to(ROOT).as_posix()
        record['notes'] = '静止采集：完整 XYZ 帧逐 marker 均值，主要入口为 static/；保留各次采集，不做轨迹/抖动；角色状态见静态表'
        static_index.append(dict(record_id=record['record_id'],target_type=record['target_type'],
                                 file=record['original_name'],static_file=record['primary_static_path'],
                                 n_markers=len(rows),total_frames=len(data.rows),status='static_world_only'))
        print(record['record_id'],len(rows),'static markers',flush=True)
    for record in records:
        record.setdefault('primary_static_path','')
    write_csv(PROCESSED / 'recordings.csv',list(records[0]),records)
    write_csv(PROCESSED / 'marker_roles.csv',list(role_rows[0]),role_rows)
    write_csv(PROCESSED / 'static/all_marker_positions.csv',fields,combined)
    for group in ['ball','tag_board']:
        selected = [r for r in combined if r['record_id'].startswith(f'M_{group}_')]
        write_csv(PROCESSED / group / 'static/all_marker_positions.csv',fields,selected)
    write_csv(PROCESSED / 'static/index.csv',list(static_index[0]),static_index)
    metadata = yaml.safe_load((PROCESSED / 'meta.yaml').read_text())
    metadata['provenance'].update(snapshot_provenance)
    metadata['primary_mocap_input'] = 'data/processed/first_test/static/index.csv'
    metadata['static_position_method'] = 'mean_complete_xyz_per_file_per_marker_no_cross_record_averaging'
    metadata['marker_role_config'] = 'configs/local/first_test/marker_roles.yaml'
    metadata['latest_collection_note_snapshot'] = next(k for k in snapshot_provenance if '/AGENT_' in k)
    metadata['blockers'].append('reference_rigid_geometry_varies_across_board_recordings') if 'reference_rigid_geometry_varies_across_board_recordings' not in metadata['blockers'] else None
    write_yaml(PROCESSED / 'meta.yaml',metadata)
    targets = yaml.safe_load((CONFIG / 'targets.yaml').read_text())
    targets['reference_rigid'].update(marker_ids=roles['board']['reference_rigid_body_marker_ids'],
                                     marker_ids_status='geometry_identified_in_board_recordings',
                                     rigid_template_shared_across_recordings=False,
                                     notes='板数据几何识别的4 marker；跨次距离变化，不能直接共用固定刚体模板；sphere torso 点对应仍未知')
    targets['ball']['candidate_marker_ids'] = roles['sphere']['target_marker_ids']
    targets['ball']['candidate_identity_status'] = 'inferred_unconfirmed'
    targets['tag_board']['corner_marker_ids_in_perimeter_order'] = roles['board']['board_marker_ids_in_perimeter_order']
    targets['tag_board']['corner_marker_roles'] = 'geometry_identified_not_image_corner_orientation'
    write_yaml(CONFIG / 'targets.yaml',targets)
    readme = '''# 静态动捕坐标：主要处理入口

本会话 CSV 是静止位置采集，不按轨迹处理。
`index.csv` 指向每次采集的分类表；`all_marker_positions.csv` 只拼接记录，**不合并不同采集的坐标**。
每个文件、每个 marker 一行；仅 XYZ 同时有效的帧参与三个坐标的算术均值。
项目单位为 **m**（原 CSV 的 mm 明确乘 0.001），坐标系仍为原导出 World，记为 `mocap_world_as_exported`。
缺测不补零/不插值；有效帧数和总帧数只记录覆盖情况。
**不输出逐帧时间、位置标准差、速度/加速度、抖动或人为协方差。**

## 分类

| role | 意义 | role_status |
|---|---|---|
| board_corner | 101555、101556、101557、101558；板角环绕顺序1–4 | geometry_identified |
| reference_rigid_body | 板录制中的101563、101573、101597、101609 | geometry_identified |
| sphere_target | 单球录制中的101642 | inferred_unconfirmed |
| unclassified | sphere其他散点 | unknown |

每次采集目录 `static/` 提供 `marker_positions.csv`，再按角色分为
`board_corners.csv`、`reference_rigid_markers.csv`、`target_candidates.csv`、`unclassified_markers.csv`（有该类才创建）。
板环绕顺序不等于图像左上等方位；球心距离不等于板外形/码尺寸。
参考刚体跨次采集距离发生变化，不共用固定模板。sphere candidate 身份未人工确认。

## 项目接口边界

这是带角色的 **World 系静态 marker 表**，不是求解器要求的 R 系 `sample_id,x_m,y_m,z_m,cov_*,n_frames` 产品。
不能为了凑字段填0协方差、虚构R系或静态样本配对。
`mocap_long.csv`/`markers_world.csv`/`rigids_world.csv` 只作兼容/追溯附件，后续位置处理使用本静态表。

元数据带 schema/source_kind/frame/unit/provenance；原始数据的轴/手性、R系构造与跨传感器对应仍需确认。
角色配置见 `configs/local/first_test/marker_roles.yaml`，源记录见归档的 AGENT 哈希版本。
复现整理：`python3 first_test/sync_static_first_test.py`。
'''
    (PROCESSED / 'static/README.md').write_text(readme,encoding='utf-8')
    # This dedicated static README supersedes trajectory-oriented preparation notes.
    overview = PROCESSED / 'README.md'
    text = overview.read_text()
    heading = '## 最新采集约定：静态结果优先\n'
    if heading not in text:
        text += '''
## 最新采集约定：静态结果优先

`first_test/AGENT.md` 在整理期间更新了静止采集处理约定与 marker 分组记录。
**后续动捕入口为 [static/README.md](static/README.md) 和 `static/index.csv`**；
每次采集每个 marker 一行的完整 XYZ 帧算术均值，单位 m，不合并三次结果，不做时间段抖动分析。
本页上方逐帧长表/窗口说明仅保留接口背景，**不是当前静止数据的主要处理路径**。

- 板角：101555/101556/101557/101558；参考四点：101563/101573/101597/101609，状态 geometry_identified。
- 单球 101642：inferred_unconfirmed；其他 sphere 散点未分类。
- 板四角顺序仅环绕顺序；参考四点跨次距离变化，不生成共用刚体模板。
- `marker_roles.csv` 和 `configs/local/first_test/marker_roles.yaml` 已同步角色/状态，不将推断当成人工确认。
- 原静态 mm 表保留在 `first_test/parsed/static/`；项目分类表统一转换为 m。
- 逐帧 CSV 仅作追溯，静态表不带时间/速度/抖动/标准差，也不伪造求解器协方差。
- 最新采集说明按哈希版本归档，初次较短说明快照保留，不覆盖历史记录。
'''
        overview.write_text(text,encoding='utf-8')
    pointer = SOURCE / 'README.md'
    text = pointer.read_text()
    if '静态数据主要入口' not in text:
        text += '\n静态数据主要入口：[静态分类表说明](../data/processed/first_test/static/README.md)；复现同步：`python3 sync_static_first_test.py`。\n'
        pointer.write_text(text,encoding='utf-8')


if __name__ == '__main__':
    main()

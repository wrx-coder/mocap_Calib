#!/usr/bin/env python3
"""Infer first_test geometry from static real observations; never deploy/accept.

OpenCV is optional to the core but required here. Original data/configs stay
unchanged. ROI/threshold selection is explicit and data-inspected, not an
independent holdout. World axes are preserved exactly as exported.
"""
import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import cv2
import numpy as np
import yaml
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from dc_calib.solver.inference import fit_similarity, fit_world_pnp, project_world
from dc_calib.solver.rigid import kabsch
from dc_mocap.geom.transforms import inverse, transform_points

# Inspected RGB-derived candidate regions, NOT inferred permanent identity.
SETTINGS = {
    'C_tag_board_01': ('tag_board', '20261011_172629', [320, 125, 455, 220], 180),
    'C_tag_board_02': ('tag_board', '20261011_172751', [275, 55, 395, 75], 200),
    'C_tag_board_03': ('tag_board', '20261011_172834', [150, 150, 250, 275], 180),
    'C_ball_01': ('ball', '20261011_173128', [380, 185, 410, 215], 200),
    'C_ball_02': ('ball', '20261011_173244', [85, 65, 115, 95], 130),
    'C_ball_03': ('ball', '20261011_173317', [610, 140, 638, 165], 130),
}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def json_value(x):
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    raise TypeError(type(x).__name__)


def contours(rgb, roi, threshold):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    x0, y0, x1, y1 = roi
    binary = np.zeros_like(gray)
    binary[y0:y1, x0:x1] = gray[y0:y1, x0:x1] > threshold
    cs, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    result = []
    for c in cs:
        area, per = cv2.contourArea(c), cv2.arcLength(c, True)
        _, _, w, h = cv2.boundingRect(c)
        if 8 < area < 250 and .65 < w / h < 1.6 and per and 4*np.pi*area/per**2 > .4:
            m = cv2.moments(c)
            result.append((np.array([m['m10']/m['m00'], m['m01']/m['m00']]), c, area))
    return result


def extract(data, output):
    observations, summaries, provenance = [], {}, {}
    for rid, (group, directory, roi, threshold) in SETTINGS.items():
        folder = data / group / 'camera' / directory
        frame_manifest = folder / 'frames.csv'
        provenance[str(frame_manifest.relative_to(ROOT))] = sha(frame_manifest)
        frames = list(csv.DictReader(frame_manifest.open()))
        first = np.load(folder / frames[0]['npz'])
        seeds = contours(first['rgb'], roi, threshold)
        expected = 1 if group == 'ball' else (2 if rid.endswith('02') else 4)
        if len(seeds) != expected:
            raise ValueError(f'{rid}: expected {expected} candidates, got {len(seeds)}')
        seeds = sorted(seeds, key=lambda x: (x[0][1], x[0][0]))
        tracks = [[] for _ in seeds]
        outdir = output / 'observations' / rid
        outdir.mkdir(parents=True)
        for row in frames:
            path = folder / row['npz']
            provenance[str(path.relative_to(ROOT))] = sha(path)
            a = np.load(path)
            candidates = contours(a['rgb'], roi, threshold)
            used = set()
            for ci, (seed, _, _) in enumerate(seeds):
                matches = [(np.linalg.norm(uv-seed), j, uv, c, area)
                           for j, (uv, c, area) in enumerate(candidates)
                           if j not in used and np.linalg.norm(uv-seed) < 4]
                if len(matches) != 1:
                    continue  # missing or ambiguous is rejected, never filled
                _, j, uv, c, area = matches[0]
                used.add(j)
                mask = np.zeros(a['depth'].shape, np.uint8)
                cv2.drawContours(mask, [c], -1, 1, -1)
                raw = a['depth'][(mask > 0) & (a['depth'] > 0)]
                item = {'record_id': rid, 'candidate_id': ci, 'source_npz': str(path.relative_to(ROOT)),
                        'time_s': row['time_s'], 'u_px': uv[0], 'v_px': uv[1],
                        'area_px2': area, 'depth_raw_median': float(np.median(raw)) if len(raw) else '',
                        'valid_depth_pixels': len(raw)}
                observations.append(item)
                tracks[ci].append(item)
                if group == 'ball':
                    cv2.imwrite(str(outdir / (Path(row['npz']).stem + '.mask.png')), mask * 255)
        means = []
        for ci, track in enumerate(tracks):
            if len(track) < .8 * len(frames):
                raise ValueError(f'{rid} candidate {ci}: insufficient static coverage')
            valid = [r for r in track if r['depth_raw_median'] != '']
            if group == 'ball' and len(valid) < .8 * len(frames):
                raise ValueError(f'{rid}: insufficient valid depth coverage')
            means.append({'candidate_id': ci, 'uv_px': np.mean([[r['u_px'], r['v_px']] for r in track], 0),
                          'area_px2': float(np.mean([r['area_px2'] for r in track])),
                          'depth_raw': float(np.mean([r['depth_raw_median'] for r in valid])) if valid else None,
                          'valid_rgb_frames': len(track), 'valid_depth_frames': len(valid),
                          'total_frames': len(frames)})
        summaries[rid] = means
        preview = cv2.cvtColor(first['rgb'], cv2.COLOR_RGB2BGR)
        for ci, (uv, c, _) in enumerate(seeds):
            cv2.drawContours(preview, [c], -1, (0, 255, 0), 1)
            cv2.putText(preview, str(ci), tuple(uv.astype(int)+[5, -5]), cv2.FONT_HERSHEY_SIMPLEX, .5, (0, 0, 255), 1)
        cv2.imwrite(str(outdir / 'overlay.png'), preview)
    dump_csv(output / 'camera_candidates.csv', observations)
    return summaries, provenance


def board_solve(world, summaries, K):
    image = [np.array([r['uv_px'] for r in summaries[f'C_tag_board_{i:02}']]) for i in (1, 3)]
    for i, p in enumerate(image):
        q = p - p.mean(0)
        image[i] = p[np.argsort(np.arctan2(q[:, 1], q[:, 0]))]
    orders = [np.roll(np.arange(4), i) for i in range(4)] + [np.roll(np.arange(4)[::-1], i) for i in range(4)]
    candidates = []
    for m1, m3 in itertools.permutations(range(3), 2):
        for o1, o3 in itertools.product(orders, repeat=2):
            obj = np.concatenate([world[m1], world[m3]])
            uv = np.concatenate([image[0][o1], image[1][o3]])
            try:
                fit = fit_world_pnp(obj, uv, K)
            except (ValueError, cv2.error):
                continue
            candidates.append({**fit, 'mocap_indices': [m1, m3], 'corner_orders': [o1, o3]})
    if len(candidates) < 2:
        raise ValueError('Insufficient PnP candidates')
    candidates.sort(key=lambda x: x['rmse_px'])
    best = candidates[0]
    # Board 02 is clipped: only two lower markers are visible; never fabricate upper corners.
    m2 = list(set(range(3)) - set(best['mocap_indices']))[0]
    pred = project_world(best['T'], world[m2], K)
    obs = np.array([r['uv_px'] for r in summaries['C_tag_board_02']])
    checks = []
    for ids in itertools.permutations(range(4), 2):
        errors = np.linalg.norm(pred[list(ids)] - obs, axis=1)
        checks.append({'marker_indices': ids, 'errors_px': errors, 'rmse_px': float(np.sqrt(np.mean(errors**2)))})
    checks.sort(key=lambda x: x['rmse_px'])
    return {'best': best, 'runner_up_rmse_px': candidates[1]['rmse_px'], 'hypotheses_count': len(candidates),
            'T_W_C': inverse(best['T']), 'partial_board_02': checks[0],
            'partial_board_mocap_index': m2, 'predicted_board_02_pixels': pred,
            'independent_holdout': False}


def ball_solve(world, summaries, K):
    rows = [summaries[f'C_ball_{i:02}'][0] for i in range(1, 4)]
    uv = np.array([r['uv_px'] for r in rows])
    raw = np.array([r['depth_raw'] for r in rows])
    rays = np.c_[(uv - K[:2, 2]) / np.diag(K)[:2], np.ones(3)]
    rays /= np.linalg.norm(rays, axis=1)[:, None]
    surface = rays * (raw / rays[:, 2])[:, None]
    radius_raw = np.sqrt(np.array([r['area_px2'] for r in rows]) / np.pi) * raw / np.sqrt(K[0, 0]*K[1, 1])
    hypotheses = []
    for p in itertools.permutations(range(3)):
        fit = fit_similarity(surface + rays * radius_raw[:, None], world[list(p)])
        hypotheses.append({**fit, 'mocap_indices': p})
    hypotheses.sort(key=lambda x: x['rmse_m'])
    best = hypotheses[0]
    nominal_centers = surface * .001 + rays * .007
    fixed_T = kabsch(nominal_centers, world[list(best['mocap_indices'])])
    fixed_errors = np.linalg.norm(transform_points(fixed_T, nominal_centers) - world[list(best['mocap_indices'])], axis=1)
    fixed = {'T': fixed_T, 'errors_m': fixed_errors, 'depth_unit': .001, 'radius_m': .007,
             'rmse_m': float(np.sqrt(np.mean(fixed_errors**2)))}
    # Explicitly exhibit radius/scale confounding; do not quietly accept a negative radius.
    ids = np.array([[0, 1], [0, 2], [1, 2]])
    target = world[list(best['mocap_indices'])]
    distances = np.linalg.norm(target[ids[:, 0]] - target[ids[:, 1]], axis=1)
    def residual(x):
        center = x[0] * surface + x[1] * rays
        return np.linalg.norm(center[ids[:, 0]] - center[ids[:, 1]], axis=1) - distances
    free = least_squares(residual, [.001, .007], x_scale='jac')
    return {'hypotheses': hypotheses, 'best': best, 'T_W_C': best['T'],
            'depth_unit_m_per_raw_inferred': best['scale'],
            'radius_m_by_silhouette': best['scale'] * radius_raw,
            'radius_method': 'equivalent_area silhouette; approximation depends on threshold and visible sphere',
            'fixed_1mm_raw_7mm_radius_sensitivity': fixed,
            'free_scale_radius_diagnostic': {'depth_unit': free.x[0], 'radius_m': free.x[1],
                                           'pair_distance_errors_m': residual(free.x),
                                           'normalized_scale_radius_jacobian_cosine': float(abs(np.dot(free.jac[:, 0], free.jac[:, 1])) / (np.linalg.norm(free.jac[:, 0]) * np.linalg.norm(free.jac[:, 1]))),
                                           'warning': 'Negative unconstrained radius / weak separation: do not adopt this fit'},
            'rays': rays, 'surface_raw': surface, 'uv_px': uv,
            'quantity': 'approximate_center', 'independent_holdout': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True, help='New result directory, never overwrite')
    args = p.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError(out)
    data = ROOT / 'data/processed/first_test'
    static = data / 'static/all_marker_positions.csv'
    rows = list(csv.DictReader(static.open()))
    xyz = lambda r: [float(r[k]) for k in ('x_m', 'y_m', 'z_m')]
    boards = np.array([[xyz(r) for r in rows if r['record_id'] == f'M_tag_board_{i:02}' and r['role'] == 'board_corner'] for i in range(1, 4)])
    balls = np.array([xyz(r) for r in rows if r['role'] == 'sphere_target'])
    config = ROOT / 'configs/local/first_test/ball/C_ball_01.camera.yaml'
    camera = yaml.safe_load(config.read_text())
    k = camera['intrinsics']
    if any(abs(x) > 1e-12 for x in k['distortion_coefficients']):
        raise ValueError('This diagnostic expects recorded zero distortion')
    K = np.array([[k['fx'], 0, k['cx']], [0, k['fy'], k['cy']], [0, 0, 1.]])
    out.mkdir(parents=True)
    summaries, provenance = extract(data, out)
    provenance[str(static.relative_to(ROOT))] = sha(static)
    provenance[str(config.relative_to(ROOT))] = sha(config)
    for path in (Path(__file__).resolve(), ROOT / 'src/dc_calib/solver/inference.py'):
        provenance[str(path.relative_to(ROOT))] = sha(path)
    board = board_solve(boards, summaries, K)
    ball = ball_solve(balls, summaries, K)
    delta = inverse(board['T_W_C']) @ ball['T_W_C']
    rotation_difference = float(np.degrees(Rotation.from_matrix(delta[:3, :3]).magnitude()))
    translation_difference = float(np.linalg.norm(delta[:3, 3]))
    # Reference marker distances localize nonrigidity without filling missing rigid poses.
    refs = np.array([[xyz(r) for r in rows if r['record_id'] == f'M_tag_board_{i:02}' and r['role'] == 'reference_rigid_body'] for i in range(1, 4)])
    ref_pairs = []
    for a, b in itertools.combinations(range(4), 2):
        ds = np.linalg.norm(refs[:, a] - refs[:, b], axis=1)
        ref_pairs.append({'ids': [['101563', '101573', '101597', '101609'][i] for i in (a, b)],
                          'distances_m': ds, 'range_m': float(np.ptp(ds))})
    # Actual same-frame world->R conversion precedes static averaging. No axis guess is required algebraically.
    relative_points, pose_summaries, relative_candidates = [], [], []
    for i in range(1, 4):
        f = data / f'ball/mocap/M_ball_{i:02}/mocap_long.csv'
        provenance[str(f.relative_to(ROOT))] = sha(f)
        rr = [r for r in csv.DictReader(f.open()) if r['marker_id'] == '101642']
        q = Rotation.from_quat([[float(r[k]) for k in ('qx', 'qy', 'qz', 'qw')] for r in rr])
        tr = np.array([[float(r[k]) for k in ('rigid_x', 'rigid_y', 'rigid_z')] for r in rr])
        pw = np.array([[float(r[k]) for k in ('x', 'y', 'z')] for r in rr])
        pr = q.inv().apply(pw - tr).mean(0)
        relative_points.append({'record_id': f'M_ball_{i:02}', 'x_m': pr[0], 'y_m': pr[1], 'z_m': pr[2],
                                'valid_frames': len(rr), 'status': 'conditional_xyzw_R_to_W; marker_identity_inferred'})
        R = q.mean().as_matrix()
        pose = np.eye(4); pose[:3, :3] = R; pose[:3, 3] = tr.mean(0)
        pose_summaries.append(pose)
        relative_candidates.append(inverse(pose) @ ball['T_W_C'])
    centers = ball['best']['scale'] * (ball['surface_raw'] + ball['rays'] *
              (ball['radius_m_by_silhouette'] / ball['best']['scale'])[:, None])
    order = ball['best']['mocap_indices']
    paired_pr = np.array([[relative_points[i][k] for k in ('x_m', 'y_m', 'z_m')] for i in order])
    conditional_T = kabsch(centers, paired_pr)
    conditional_errors = np.linalg.norm(transform_points(conditional_T, centers) - paired_pr, axis=1)
    # Keep diagnostics tied to the explicit best pairing; no reuse as holdout.
    paired_world = balls[list(order)]
    board_ball_projection = project_world(board['best']['T'], paired_world, K)
    board_ball_pixel_errors = np.linalg.norm(board_ball_projection - ball['uv_px'], axis=1)
    board_ball_errors = np.linalg.norm(transform_points(board['T_W_C'], centers) - paired_world, axis=1)
    board_geometry = []
    for i, corners in enumerate(boards):
        sides = np.linalg.norm(corners - np.roll(corners, -1, axis=0), axis=1)
        diagonals = [np.linalg.norm(corners[0] - corners[2]), np.linalg.norm(corners[1] - corners[3])]
        board_geometry.append({'record_id': f'M_tag_board_{i+1:02}', 'cyclic_side_lengths_m': sides,
                               'diagonal_lengths_m': diagonals,
                               'interpretation': 'measured marker-center spacing, not board outer or code dimensions'})
    dump_csv(out / 'mocap_target_R_static.csv', relative_points)
    pair_rows = []
    for ci, mi in enumerate(order):
        pair_rows.append({'camera_record': f'C_ball_{ci+1:02}', 'mocap_record': f'M_ball_{mi+1:02}',
                          'status': 'geometry_inferred_not_manually_confirmed', 'split': 'diagnostic_all_fit'})
    for ci, mi in zip((1, 3), board['best']['mocap_indices']):
        pair_rows.append({'camera_record': f'C_tag_board_{ci:02}', 'mocap_record': f'M_tag_board_{mi+1:02}',
                          'status': 'geometry_inferred_not_manually_confirmed', 'split': 'diagnostic_all_fit'})
    pair_rows.append({'camera_record': 'C_tag_board_02', 'mocap_record': f"M_tag_board_{board['partial_board_mocap_index']+1:02}",
                      'status': 'partial_two_corner_crosscheck', 'split': 'diagnostic_not_independent'})
    dump_csv(out / 'record_pair_candidates.csv', pair_rows)
    report = {'schema_version': 1, 'status': 'unverified', 'source_kind': 'real', 'deployable': False,
              'frame': 'mocap_world_as_exported', 'length_unit': 'm', 'K': K,
              'observation_settings': SETTINGS, 'camera_static_candidates': summaries,
              'board_rgb_pnp': board, 'ball_rgbd_similarity': ball,
              'cross_target_check': {'rotation_difference_deg': rotation_difference,
                                     'translation_difference_m': translation_difference,
                                     'consistent': False, 'board_predicts_ball_pixels': board_ball_projection,
                                     'board_vs_ball_pixel_errors': board_ball_pixel_errors,
                                     'board_transform_ball_center_errors_m': board_ball_errors,
                                     'limit': 'different acquisition groups; fixed camera assumption unproven'},
              'measured_board_marker_geometry': board_geometry,
              'conditional_torso_rigid': {'T_R_C': conditional_T,
                                          'errors_m': conditional_errors, 'T_R_C_by_record': relative_candidates,
                                          'convention': 'assumed stored xyzw maps rigid R to exported W; not torso_link'},
              'reference_marker_geometry': ref_pairs, 'provenance_sha256': provenance,
              'limitations': ['No independent physical-position holdout or split-half test; only three ball positions.',
                              'Depth registration/color_z and device depth_units not independently proven.',
                              'Masks are actual thresholded RGB contours, approximate silhouette, not a validated segmentation model.',
                              'Board corner apparent image center vs 3D sphere center may be biased.',
                              'Board 02 upper corners are outside image; only two real observations used.',
                              'No torso_link CAD correspondence, hand tool offset, controller state or real-time timing mapping.',
                              'Never deploy or fill acceptance attestation from this report.']}
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=json_value)+'\n')
    summary = f'''# first_test 数据推导与候选求解

**真实数据已推进至候选求解；状态 unverified，不可部署，不是实机验收。**

## 可从已有数据求得的内容

- 从同帧 RGB 阈值轮廓提取真实 marker mask，缺测/歧义拒绝，不使用全图占位。每次采集独立静态平均，无抖动/速度分析。
- 板四角采用实际动捕球心几何，无须臆造码族、板外形尺寸或理想矩形。枚举录制配对及循环/反向角顺序后做 PnP。
- 最佳板候选重投影 RMSE **{board['best']['rmse_px']:.3f} px**，次优 **{board['runner_up_rmse_px']:.3f} px**。
- 第二次相机板录制顶部被裁切，真实可见两角交叉检查 RMSE **{board['partial_board_02']['rmse_px']:.3f} px**，不补造上角。
- 单球全部六种配对拟合，最优训练拟合 RMSE **{ball['best']['rmse_m']*1000:.2f} mm**，次优 **{ball['hypotheses'][1]['rmse_m']*1000:.2f} mm**。
- 单球深度单位推导 **{ball['best']['scale']:.9f} m/raw**；阈值轮廓等效面积半径推导 **{np.mean(ball['radius_m_by_silhouette'])*1000:.2f} mm**。二者依赖轮廓/前表面假设，不是设备配置或尺测事实。
- 缺失胸部位姿的板录制先交付 `T_W_C`，不伪造 `T_R_C`。单球真实逐帧位姿先 W→R 后平均，提供条件性 `T_R_C`，不等于 `T_torso_C`。

## 必须保留的失败证据

板与单球外参相差 **{rotation_difference:.3f}° / {translation_difference*1000:.2f} mm**。板解预测单球的像素偏差分别为 **{', '.join(f'{x:.2f}' for x in board_ball_pixel_errors)} px**；不能合并为已验证安装外参。
原因候选包括组间安装/参考结构变化、深度/轮廓中心偏差与跨记录状态不一致；本报告不把任何一项写成已证实原因。
自由联合求半径和尺度产生半径 **{ball['free_scale_radius_diagnostic']['radius_m']*1000:.2f} mm**（非物理负值），提示现有三点和当前观测模型不支持可靠的自由补偿；未采用该拟合。
参考四点跨次间距见 JSON，无法认定为不变刚体模板；不能用四点填补厂家空位姿。

## 产品与复现

- `report.json`：矩阵、全部配对排名、交叉检查、条件性 R 系结果、SHA-256 输入溯源和限制。
- `camera_candidates.csv`：真实图像轮廓/原始深度观测；`observations/`：单球二值 mask 及 RGB 标注预览。
- `record_pair_candidates.csv`：几何推断配对，不改原会话未确认的配对表，不虚构 train/validation。
- `mocap_target_R_static.csv`：单球真实同帧转 R 后平均；声明四元数解释为条件假设。

```bash
python3 first_test/infer_geometry.py --output outputs/calibration/first_test_inferred_v4
```

输出目录必须不存在。原始数据、已有归档、配置 null 和正式求解器验收门槛均不改。

## 后续最小工作

1. 核验轮廓 overlay、同球心与几何推断配对；确认实际 depth_units/color_z 和组间安装是否变化。
2. 基于本候选做独立新位置验证：至少 8 个训练位置加独立留出，覆盖深度/高度，不用现有三点伪造分半验收。
3. 机器人系必须另有 torso_link 结构对应；精准抓球还需真实工具中心、关节状态/时钟和只读失效门控。现有数据不能恢复这些未观测自由度。
'''
    (out / 'README.md').write_text(summary)
    print(summary)


if __name__ == '__main__':
    main()

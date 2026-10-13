#!/usr/bin/env python3
"""从 8 个 Marker 中寻找两组紧凑四点，并按逐帧平面拟合误差区分板子和刚体。

运行：python3 identify_marker_groups.py
依赖：numpy，以及同目录的 parse_mocap_csv.py。
所有长度保持 CSV 原单位；平面拟合 RMS = 最小奇异值 / sqrt(4)。
分类依据是两组相对共面程度，不代表验证了刚体跨采集的形状不变。
"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np

from parse_mocap_csv import parse_csv


def describe_group(points, ids):
    centered = points - points.mean(axis=1, keepdims=True)
    singular_values = np.linalg.svd(centered, compute_uv=False)
    rms = singular_values[:, -1] / np.sqrt(4)
    volumes = np.abs(np.linalg.det(points[:, 1:] - points[:, :1])) / 6
    pairs = []
    for a, b in itertools.combinations(range(4), 2):
        distances = np.linalg.norm(points[:, a] - points[:, b], axis=1)
        pairs.append({"ids": [ids[a], ids[b]],
                      "mean": float(distances.mean()),
                      "std": float(distances.std()),
                      "min": float(distances.min()),
                      "max": float(distances.max())})
    return {"marker_ids": ids,
            "valid_frames": len(points),
            "centroid_mean": points.mean(axis=(0, 1)).tolist(),
            "plane_rms_mean": float(rms.mean()),
            "plane_rms_max": float(rms.max()),
            "normalized_planarity_mean": float(np.mean(singular_values[:, -1] /
                                                       singular_values[:, 0])),
            "tetrahedron_volume_mean": float(volumes.mean()),
            "pair_distances": pairs}


def identify(path):
    data = parse_csv(path)
    ids = list(dict.fromkeys(col.object_id for col in data.columns
                             if col.object_type == "Marker"))
    if len(ids) != 8:
        raise ValueError(f"{path}: 需要 8 个 Marker，实际为 {len(ids)}")
    points = np.stack([data.series("Marker", marker_id, "Position", ("X", "Y", "Z"))
                       for marker_id in ids], axis=1).astype(float)
    points = points[np.isfinite(points).all(axis=(1, 2))]
    if not len(points):
        raise ValueError(f"{path}: 没有 8 个 Marker 同时可见的完整帧")
    candidates = []
    for first in itertools.combinations(range(8), 4):
        # 两组交换视为同一种分组，总计 35 种。
        if 0 not in first:
            continue
        second = tuple(i for i in range(8) if i not in first)
        score = sum(float(np.mean(np.sum(
            (points[:, group] - points[:, group].mean(axis=1, keepdims=True)) ** 2,
            axis=2))) for group in (first, second))
        candidates.append((score, first, second))
    candidates.sort()
    score, first, second = candidates[0]
    groups = [describe_group(points[:, group], [ids[i] for i in group])
              for group in (first, second)]
    groups.sort(key=lambda group: group["plane_rms_mean"])
    return {"file": str(path),
            "length_unit": data.metadata.get("LengthUnits"),
            "actual_frames": len(data.rows),
            "complete_frames": len(points),
            "partition_score": score,
            "runner_up_partition_score": candidates[1][0],
            "board": groups[0],
            "reference_rigid_body": groups[1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--output", type=Path, default=Path("parsed/marker_groups.json"))
    args = parser.parse_args()
    files = args.files or sorted(Path.cwd().glob("board_*.csv"))
    if not files:
        parser.error("没有找到 board_*.csv")
    reports = [identify(path) for path in files]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(reports, ensure_ascii=False, indent=2,
                                      allow_nan=False) + "\n", encoding="utf-8")
    for report in reports:
        print(Path(report["file"]).name)
        for key, label in (("board", "板子"), ("reference_rigid_body", "参考刚体")):
            group = report[key]
            print(f"  {label}: {', '.join(group['marker_ids'])}; "
                  f"平面 RMS 均值 {group['plane_rms_mean']:.6f} "
                  f"{report['length_unit']}")
    print(f"结果已写入 {args.output}")


if __name__ == "__main__":
    main()

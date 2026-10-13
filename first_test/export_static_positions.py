#!/usr/bin/env python3
"""导出静止采集的带角色标记坐标，每个 Marker 每次采集仅保留一行。

运行：python3 export_static_positions.py
仅依赖标准库。角色配置来自同目录 marker_roles.json。
不输出逐帧时间、位置抖动或位置标准差；原始 CSV 不变。
"""
import argparse
import csv
import json
import statistics
from pathlib import Path

from parse_mocap_csv import parse_csv


FIELDS = ["file", "data_name", "object_type", "marker_id", "role", "role_status",
          "board_corner_order", "x", "y", "z", "length_unit", "coordinate_space",
          "valid_frames", "total_frames", "method"]


def static_rows(path, roles):
    data = parse_csv(path)
    name = path.stem.lower()
    family = "board" if name.startswith("board_") else "sphere" if name.startswith("sphere") else None
    ids = list(dict.fromkeys(col.object_id for col in data.columns
                             if col.object_type == "Marker"))
    result = []
    for marker_id in ids:
        role, status, corner = "unclassified", "unknown", ""
        if family == "board":
            corners = roles["board"]["board_marker_ids_in_perimeter_order"]
            if marker_id in corners:
                role, status, corner = "board_corner", "geometry_identified", corners.index(marker_id) + 1
            elif marker_id in roles["board"]["reference_rigid_body_marker_ids"]:
                role, status = "reference_rigid_body", "geometry_identified"
        elif family == "sphere" and marker_id in roles["sphere"]["target_marker_ids"]:
            role, status = "sphere_target", "inferred_unconfirmed"
        points = data.series("Marker", marker_id, "Position", ("X", "Y", "Z"))
        valid = [point for point in points if all(value is not None for value in point)]
        mean = [statistics.mean(axis) for axis in zip(*valid)] if valid else [None] * 3
        result.append(dict(zip(FIELDS, [
            path.name, data.metadata.get("DataName", ""), "Marker", marker_id,
            role, status, corner, *mean, data.metadata.get("LengthUnits", ""),
            data.metadata.get("CoordinateSpace", ""), len(valid), len(data.rows),
            "mean_of_complete_xyz_frames"])))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("parsed/static"))
    args = parser.parse_args()
    files = args.files or sorted(Path.cwd().glob("*.csv"))
    if not files:
        parser.error("没有找到 CSV 文件")
    roles = json.loads(Path(__file__).with_name("marker_roles.json").read_text(encoding="utf-8"))
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    combined = []
    for path in files:
        rows = static_rows(path, roles)
        out_path = output / f"{path.stem}_static.csv"
        if out_path.resolve() == path.resolve():
            parser.error(f"拒绝覆盖原始文件：{path}")
        with out_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        combined.extend(rows)
        print(f"{path.name}: {len(rows)} 个 Marker 静态位置 -> {out_path}")
    combined_path = output / "all_static_positions.csv"
    if any(combined_path.resolve() == path.resolve() for path in files):
        parser.error(f"拒绝覆盖原始文件：{combined_path}")
    with combined_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(combined)


if __name__ == "__main__":
    main()

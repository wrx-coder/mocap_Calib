#!/usr/bin/env python3
"""解析动捕多层表头 CSV；仅依赖 Python 标准库。

示例：
    python3 parse_mocap_csv.py
    python3 parse_mocap_csv.py board_1.csv --output-dir parsed

代码调用：
    data = parse_csv("board_1.csv")
    xyz = data.series("Marker", "101555", "Position", ("X", "Y", "Z"))
    # 每一项对应一帧；空字段为 None，坐标保持原单位。
"""

import argparse
import csv
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Column:
    object_type: str
    name: str
    object_id: str
    quantity: str
    component: str

    @property
    def label(self):
        if not self.object_type:
            return self.component
        return ".".join((self.object_type.replace(" ", "_"), self.name,
                         self.object_id, self.quantity, self.component))


@dataclass
class MocapData:
    metadata: dict
    columns: list
    rows: list

    def series(self, object_type, object_id, quantity, components):
        """按对象类型、ID、物理量和分量提取逐帧数据，不丢弃缺失帧。"""
        indices = []
        for component in components:
            matches = [i for i, col in enumerate(self.columns)
                       if (col.object_type, col.object_id, col.quantity, col.component)
                       == (object_type, str(object_id), quantity, component)]
            if len(matches) != 1:
                raise ValueError(f"字段不存在或不唯一：{object_type}/{object_id}/"
                                 f"{quantity}/{component}")
            indices.append(matches[0])
        return [tuple(row[i] for i in indices) for row in self.rows]

    def summary(self):
        objects = {}
        for col in self.columns[2:]:
            key = (col.object_type, col.name, col.object_id)
            if key not in objects:
                xyz = self.series(col.object_type, col.object_id, "Position", ("X", "Y", "Z"))
                valid = [point for point in xyz if all(v is not None for v in point)]
                axes = list(zip(*valid)) if valid else []
                objects[key] = {
                    "type": col.object_type, "name": col.name, "id": col.object_id,
                    "valid_position_frames": len(valid),
                    "missing_position_frames": len(xyz) - len(valid),
                    "mean_position": [statistics.mean(axis) for axis in axes] if axes else None,
                    "position_std": [statistics.pstdev(axis) for axis in axes] if axes else None,
                }
        warnings = []
        declared = self.metadata.get("FrameCount")
        if declared is not None and int(declared) != len(self.rows):
            warnings.append(f"声明帧数 {declared} 与实际帧数 {len(self.rows)} 不一致")
        frames = [row[0] for row in self.rows]
        times = [row[1] for row in self.rows]
        if any(b != a + 1 for a, b in zip(frames, frames[1:])):
            warnings.append("帧号不连续")
        if any(b <= a for a, b in zip(times, times[1:])):
            warnings.append("时间不严格递增")
        return {
            "metadata": self.metadata,
            "actual_frames": len(self.rows),
            "column_count": len(self.columns),
            "time_range_seconds": [times[0], times[-1]] if times else None,
            "objects": list(objects.values()),
            "warnings": warnings,
        }

    def export_csv(self, path):
        """导出唯一单层表头；缺失值仍写成空字段。"""
        with Path(path).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow([col.label for col in self.columns])
            writer.writerows(self.rows)


def parse_csv(path):
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.reader(stream))
    if not records or len(records[0]) % 2:
        raise ValueError(f"{path}: 元信息不是完整的键值对")
    metadata = dict(zip(records[0][::2], records[0][1::2]))
    header_index = next((i for i, row in enumerate(records)
                         if row[:2] == ["Frame", "Time"]), None)
    if header_index is None or header_index < 4:
        raise ValueError(f"{path}: 未找到 Frame,Time 多层表头")
    types, names, ids, quantities, components = records[header_index - 4:header_index + 1]
    width = len(components)
    if any(len(row) != width for row in (types, names, ids, quantities)):
        raise ValueError(f"{path}: 多层表头列数不一致")
    if (types[1], names[1], ids[1]) != ("Type", "Name", "ID"):
        raise ValueError(f"{path}: 不支持的多层表头布局")
    columns = [Column("", "", "", "", label) for label in components[:2]]
    columns.extend(Column(*fields) for fields in
                   zip(types[2:], names[2:], ids[2:], quantities[2:], components[2:]))
    if len({col.label for col in columns}) != width:
        raise ValueError(f"{path}: 存在重复字段")
    rows = []
    for line_number, record in enumerate(records[header_index + 1:], header_index + 2):
        if not record or all(not cell.strip() for cell in record):
            continue
        if len(record) != width:
            raise ValueError(f"{path}:{line_number}: 应有 {width} 列，实际 {len(record)} 列")
        try:
            row = [float(cell) if cell.strip() else None for cell in record]
            # 明确区分缺失值与非有限数值，避免后续统计和 JSON 出错。
            if any(value is not None and not math.isfinite(value) for value in row):
                raise ValueError("存在非有限数值")
            if row[0] is None or not row[0].is_integer() or row[1] is None:
                raise ValueError("Frame 必须为整数，Time 不得为空")
            row[0] = int(row[0])
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: {error}") from error
        rows.append(row)
    return MocapData(metadata, columns, rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", type=Path, help="默认读取当前目录的所有 CSV")
    parser.add_argument("--output-dir", type=Path, help="导出单层表头 CSV 和统计 JSON 的目录")
    args = parser.parse_args()
    files = args.files or sorted(Path.cwd().glob("*.csv"))
    if not files:
        parser.error("没有找到 CSV 文件")
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    for path in files:
        try:
            data = parse_csv(path)
            summary = data.summary()
        except (OSError, ValueError) as error:
            parser.exit(1, f"解析失败：{error}\n")
        print(f"{path.name}: {len(data.rows)} 帧，{len(data.columns)} 列，"
              f"{data.metadata.get('FrameRate', '?')} Hz，"
              f"单位 {data.metadata.get('LengthUnits', '?')}，"
              f"坐标系 {data.metadata.get('CoordinateSpace', '?')}")
        for obj in summary["objects"]:
            mean = obj["mean_position"]
            text = ", ".join(f"{v:.6f}" for v in mean) if mean else "无有效坐标"
            print(f"  {obj['type']} {obj['name']} (ID={obj['id']}): "
                  f"有效 {obj['valid_position_frames']}/{len(data.rows)}，均值 [{text}]")
        for warning in summary["warnings"]:
            print(f"  警告：{warning}")
        if args.output_dir:
            csv_path = args.output_dir / f"{path.stem}_flat.csv"
            json_path = args.output_dir / f"{path.stem}_summary.json"
            if csv_path.resolve() == path.resolve() or json_path.resolve() == path.resolve():
                parser.exit(1, f"拒绝覆盖输入文件：{path}\n")
            data.export_csv(csv_path)
            json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2,
                                            allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

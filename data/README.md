# 数据目录

## 原始数据：`raw/<session_id>/`

存放 FZMotion 工程、CSV、刚体资产、相机 bag/原生录制、内参和安装/特征记录。可按 `mocap/`、`camera/`、`robot/` 分子目录。原始文件只读保留，不做填补、平滑或覆盖；文件清单、哈希及来源进入会话元数据。

## 处理产品：`processed/<session_id>/`

计划存放 P1 躯干特征、P2 静态球样本、相机静态样本、显式配对表、训练/留出划分和质量统计。详见 [工作区接口](../document/design/工作区约定与接口.md)。当前为空，未实现提取器。

## 表头模板

[templates/](templates/) 提供人工准备用的 CSV 表头，无虚构坐标或样本：

- `torso_correspondences.example.csv`：R 系实测特征球心与 torso 系已知球心。
- `sample_pairs.example.csv`：双侧静态段配对与位置级 train/validation 划分。

这些不是厂家 CSV 格式，也不是完整 P1/P2 schema。实际坐标均须为 m，特征和样本身份经人工确认；缺段不顺延强配，散点 ID 不当永久身份。

原始/处理数据默认在 `.gitignore` 中忽略，后续版本控制只保留骨架与模板；工作区已纳入 Git，但真实数据应单独备份。

# D435i + FZMotion 空间外参标定

**RGB-D 静态单球离线闭环**：动捕数据 → 静态 R 系球心，与相机 color optical 系球心配对 → Kabsch/Huber → `T_R_C` → 已知 torso 对齐时组合 `T_torso_C`。

当前已实现共享几何、配置检查、CSV读取、手工静态窗口聚合/空间关联、RGB-D几何、torso 对齐、外参求解、留出/分半报告和版本化导出。**合成端到端测试通过；尚未收到真实动捕录制或完成实机标定。** 不控制机器人、不自动改 URDF、不推送私有源码。

## 最短使用路径

环境：Python≥3.10，numpy/scipy/PyYAML；测试需要 pytest。当前环境已有依赖，本次未安装软件。新环境可创建 venv 后 `python -m pip install -e '.[dev]'`。未安装项目时使用 `PYTHONPATH=src python -m dc_calib.cli`，安装后可用 `mocap-calib`。

```bash
# 一次测试
python3 -m pytest -q
# 一次演示（使用未存在的输出目录，不覆盖旧结果）
PYTHONPATH=src python3 -m dc_calib.cli demo --output outputs/calibration/demo_001
```

演示生成带真值的合成录制，实际经过 CSV 读取、marker ID 恢复、逐帧转 R/聚合、配对、球心补偿、优化、torso组合及导出。状态只能是 `synthetic_pass`，不能作为实机结果。

现场顺序：[核心流程](document/workflow/机器人动捕标定_核心流程.md) → [详细试采指南](document/workflow/首次试采操作指南.md) → [数据契约](document/design/标定数据契约_v1.md)。先选共同靶球并采12–20点，不要一上来采几百点。D435i 内参已完成，只导入既有标定/实机 CameraInfo，不重新标定。

## 实际数据命令

```bash
# 导入保存的 CameraInfo YAML（含 width/height/k/d/header）
PYTHONPATH=src python3 -m dc_calib.cli camera-info --input data/raw/session/camera_info.yaml --output configs/local/session/camera.yaml
# 填真实 depth units、球半径；depth 必须为正确 color_z，对应这帧 RGB/mask。
PYTHONPATH=src python3 -m dc_calib.cli rgbd --npz data/raw/session/frame.npz --camera configs/local/session/camera.yaml --time-s 1.0 --quantity surface --output data/processed/session/frame.csv
# 用自己的记录时钟给动捕窗口编号（不是跨设备时间同步）
PYTHONPATH=src python3 -m dc_calib.cli extract-mocap --input data/raw/session/mocap.csv --windows data/raw/session/mocap_windows.csv --rigid chest_R --world-axis Z_up --unit mm --marker-id 100242 --frame chest_R --source-kind real --clock mocap_recording --output data/processed/session/mocap.csv
# 已导出的相机逐帧观测聚合；相机窗口使用相机自己的时间
PYTHONPATH=src python3 -m dc_calib.cli aggregate-camera --input data/raw/session/camera_frames.csv --windows data/raw/session/camera_windows.csv --quantity surface --source-kind real --clock camera_recording --output data/processed/session/camera.csv
# 明确双侧静态位置配对与 train/validation；radius 是实测值，不照抄示例
PYTHONPATH=src python3 -m dc_calib.cli solve --mocap data/processed/session/mocap.csv --camera data/processed/session/camera.csv --pairs data/processed/session/pairs.csv --radius-m 0.04 --torso data/processed/session/torso.csv --output outputs/calibration/session/v1
```

以上路径/数值是用法示意；半径0.04不是你的球的已测值。`rgbd` 一次消费一个已有 mask 的 NPZ，输出一帧；`rgbd-batch --manifest <csv> --camera <yaml> --quantity surface --output <csv>` 批处理 `time_s,npz` 清单（NPZ路径相对清单文件），输出逐帧观测供聚合。模型mask和原始流NPZ由现有程序/外层采集器提供。命令不读取任意ROS bag、不运行分割模型、不自动修正深度注册。`--marker-id` 用于每个静止段初始化，之后按空间关联允许ID变化；若已遮挡改ID后无法初始化，改用 `--seed-r x y z` 或明确该段marker，歧义拒绝。

`--torso` 可省略，此时只输出 `T_R_C`，不伪造 torso 外参。缺少独立留出或分半检查不可用不通过验收；失败仍保存报告，命令返回2。共线/缺字段/重复补偿等错误直接拒绝。默认固定半径和尺度；`--estimate-scale` 仅为已声明 surface 的可选尺度精化，不估自由偏置。

发布真实 `hardware_accepted` 还需 `--attestation <yaml>`，包含四个明确 true：`same_center_confirmed`、`torso_alignment_checked`、`independent_holdout_confirmed`、`deployment_configuration_frozen`。这是对现场记录的确认，不是绕过检查的按钮；没有真实记录勿填true。默认真实结果仅 `unverified` 候选。工具不自动部署。

## 工作区

- `configs/`：会话/相机/求解模板与 `configs/local/` 实测配置（忽略）。
- `src/dc_mocap/`：共享几何、CSV、静态数据处理、合成器。
- `src/dc_calib/`：RGB-D、torso对齐、求解/报告/导出、CLI。
- `data/raw/`：原始录制只读保留；`data/processed/`：点产品/元数据/配对表。
- `outputs/`：结果和报告；输入/输出大型数据默认不入Git。
- `document/`：[文档索引](document/README.md)，厂家资料与历史方案保留。

## 当前边界

真实 FZMotion 适配器支持多层 Type/Name/ID/Position/Rotation 表头，拒绝无表头和欧拉角；尚未真实格式验收，首次 CSV 有差异应修适配器，不手工改原数据。源位置单位按表头/配置；默认零散点视为缺测，可在API显式关闭该策略。实际左手系、额外缩放不支持。

矩阵校验不证明真实坐标定义正确；同球心、支架固定和torso CAD对应仍由试采确认。既有世界点使用未标定TF，不能拿来独立标同一条链。反光球材料/尺寸可能影响RGB模型和深度，先试后采。

## 许可证

原创实现采用 [MIT](LICENSE)。厂家 PDF/DOCX/图片与转换件不属于本项目MIT重新授权，见 [第三方说明](THIRD_PARTY_NOTICES.md)。

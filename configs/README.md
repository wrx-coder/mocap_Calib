# 配置模板

| 文件 | 用途 |
|---|---|
| [session.example.yaml](session.example.yaml) | 输入路径、源约定、frame、采样与输出目录 |
| [camera.example.yaml](camera.example.yaml) | 相机内参、检测管线、补偿状态和 optical/link 变换 |
| [calibration.example.yaml](calibration.example.yaml) | 预期求解设置、物理补偿参数和静态验收目标 |

这些是**准备模板，不是可直接运行的配置**；当前没有配置加载器、schema 校验器或标定 CLI。`null` 表示未确认，不能靠默认值继续求解。

准备真实会话时，复制三个模板到 `configs/local/<session_id>/`，填写会话编号、输入路径与实测参数，并修改 `session` 中的 `camera_config`、`calibration_config` 引用。保留 `.example.yaml` 为未填写模板，避免覆盖基线。

后续加载器统一以工作区根目录解析相对路径。输入输出统一使用同一 `session_id`；不要把 raw 原始 CSV 与 processed 产品路径混用。

## 必须先确认

- CSV 长度单位、轴与手性、四元数顺序/方向、缺测表示、时间来源及刚体名。
- 实际相机 optical frame、原生观测 frame、内参、分辨率、曝光、对齐与检测代码版本。
- 观测是球前表面还是球心，是否已经做球半径或深度尺度补偿。
- 特征球心坐标、静态段配对与训练/验证划分。
- 所需固定变换的来源；未知变换保持 `null`，不要放单位矩阵。

CSV 常见 mm、xyzw 等来自厂商资料，仍应核对实际导出；内部规范化后才使用 m/xyzw。模板中的阈值是核心流程的初始工程目标，不是设备精度保证。相机静态门限、噪声模型和补偿参数不可照抄未测值。

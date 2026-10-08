# 机器人动捕空间外参标定工作区

用 FZMotion 与机器人相机的静态单球观测标定 `T_torso_C`。

> **当前状态：仅工作区骨架。** 已建立文档导航、Python 包目录、配置模板及数据/结果目录；没有 CSV 解析器、相机检测、标定求解器或可执行标定命令。没有安装依赖或修改机器人配置。工作区已纳入 Git 版本控制。

## 从这里开始

1. 按 [空间外参核心流程](document/workflow/机器人动捕标定_核心流程.md) 执行准备、躯干对齐、静态采样、求解和验收。
2. 阅读 [工作区约定与接口](document/design/工作区约定与接口.md)，明确数据边界和模块职责。
3. 从 [配置模板说明](configs/README.md) 开始填写真实会话信息。未知值保留 `null`，不能用单位矩阵冒充标定结果。
4. 原始数据放入 `data/raw/<session_id>/`，处理产品放入 `data/processed/<session_id>/`，结果和报告使用同一会话编号。
5. 全部资料见 [文档索引](document/README.md)。历史 v4 的动态时间标定、在线接口与备选路线不属于当前工作区实现范围。

## 目录结构

```text
mocap_Calib/
├── README.md
├── pyproject.toml           # 包元数据；算法依赖仅声明为可选项
├── configs/                # 会话、相机和求解/验收配置模板
├── src/
│   ├── dc_mocap/           # 预留：动捕解析、规范化、处理与产品输出
│   └── dc_calib/           # 预留：相机数据、躯干对齐、外参求解、验收与导出
├── tests/                  # 测试规划及空的 unit/integration/fixtures 目录
├── data/
│   ├── raw/                # 原始数据：不覆盖、不填补、不平滑
│   └── processed/          # P1/P2、相机静态样本及显式配对表
├── outputs/
│   ├── calibration/        # 带版本与验收状态的标定包
│   └── reports/            # 质量与静态验收报告
└── document/
    ├── workflow/           # 当前现场执行流程
    ├── design/             # 数据层规格、工作区接口
    ├── references/         # 原 v4 与 FZMotion 对接说明
    ├── archive/plans/      # 已完成的文档精简计划
    ├── pdf/                # 厂家原始 PDF（保持原目录）
    ├── markdown/           # 转换结果、元数据与图片（保持相对引用）
    └── docs/               # 厂家 DOCX（保持原目录）
```

## 环境与当前可做的检查

项目采用 Python `src` 布局，要求 Python ≥ 3.10；核心库不依赖 ROS。本次不创建环境或安装软件。`pyproject.toml` 中的依赖是后续实现建议，不是已验证的锁文件。

当前无需安装即可检查包骨架导入：

```bash
PYTHONPATH=src python3 -B -c "import dc_mocap, dc_calib; print('workspace skeleton OK')"
```

该命令只验证包存在，**不代表标定功能已实现或通过测试**。以后实现时可在独立虚拟环境中安装可选 `calibration` 和 `dev` 依赖；当前没有 CLI 入口。

## 固定约定

- `T_A_B`：B → A；最终 `T_torso_C = T_torso_R · T_R_C`。
- 内部单位 m/s/rad；四元数 xyzw；右手系。世界系建议 Z-up，optical 系保持 x 右/y 下/z 前。
- 动捕使用实测 Marker 散点；逐帧转 R 系后平均；不依赖散点 ID 永久不变。
- `sample_id` 与静态窗口显式配对，缺段不强行顺序匹配。
- 球心偏置/深度尺度与 SE(3) 外参分开保存；未通过静态验收不发布部署结果。

## 下一阶段（尚未实现）

先补齐真实 CSV、缺测格式、相机观测与 frame 样例，再按数据层规格实现解析与 P1/P2；随后实现躯干对齐、静态外参求解和合成数据测试。不要把历史方案提到但本目录没有的脚本当作可运行依赖。

## 许可证

本项目原创内容采用 [MIT License](LICENSE)。厂家 PDF、DOCX、图片及其 Markdown/OCR 转换件不纳入 MIT 重新授权；具体范围与待核实的再分发许可见 [第三方资料说明](THIRD_PARTY_NOTICES.md)。

# 文档索引

## 当前主线

流程与计划已统一到根目录 [workflow](../workflow/README.md)。新手先读 [首次试采操作指南与记录表](../workflow/首次试采操作指南.md)；最小操作流程原文与副本保留作对照，不再称新版三步速查。上机统一三步：准备设备/选球/确认能录 → 编号静态采集 → 导出/核对/备份。D435i已标定内参不重做，使用RGB-D（彩色图加深度）与color optical（彩色光学坐标系），英文可查 [术语说明](../workflow/术语说明.md)。软件字段见 [标定数据契约 v1](design/标定数据契约_v1.md)。

| 文档 | 用途 |
|---|---|
| [流程与计划目录索引](../workflow/README.md) | 文件分工、合并来源和原文副本说明 |
| [首次试采操作指南](../workflow/首次试采操作指南.md) | 新手详细三步操作、marker布置、候选球/15点/导出记录表 |
| [最小操作流程与marker布置](../workflow/机器人动捕标定_最小操作流程.md) | 原文保持不变，旧步骤0–5供对照；细节已参与合并 |
| [最小操作流程合并前副本](../workflow/机器人动捕标定_最小操作流程_合并前副本.md) | 与原文件逐字一致的备份 |
| [机器人动捕标定：空间外参核心流程](../workflow/机器人动捕标定_核心流程.md) | 坐标/离线求解、当前状态/推进计划、torso对齐与验收/使用 |
| [术语说明](../workflow/术语说明.md) | 英文、文件名与算法/结果状态的中文解释 |
| [工作区约定与接口](design/工作区约定与接口.md) | 模块分工、数据契约和目录对应 |
| [配置模板说明](../configs/README.md) | 填写真实会话和相机信息 |
| [数据目录说明](../data/README.md) | 原始录制、处理产品与配对记录 |
| [结果目录说明](../outputs/README.md) | 标定包、报告与验收状态 |
| [最小验证](../tests/README.md) | 软件合成闭环与现场留出边界 |

## 设计与参考资料

- [动捕数据层设计规格](design/动捕数据层_设计规格.md)：历史完整数据层设计。当前优先 P1/P2（静态点产品），P3 时间轨迹与 P4 在线接口不属于当前离线范围。
- [机器人动捕标定方案 v4](references/机器人动捕标定方案_v4.md)：完整调研与历史实施方案；保留原文，不作为当前所有功能均须实现的清单。
- [FZMotion 对接要点](references/FZMotion动捕系统要点_v4对接.md)：接口与厂商待确认项。文首已追加完整版核查结论；下文保留历史副本，不把旧“仅目录”作为当前唯一证据。
- [空间外参核心流程精简计划](archive/plans/空间外参核心流程精简计划.md)：已完成的历史计划，文中旧根目录路径仅作历史记录，不作为现行路径。

## 厂家原始资料（未改动）

- [FZMotion 3.0 Motar 用户手册 PDF](pdf/FZMotion3.0-Motar用户使用手册V1.0.pdf)
- [FZMotion 导出 CSV 格式 PDF](pdf/FZMotion导出CSV文件格式说明V1.2.pdf)
- [LuMoSDK 手册 PDF](pdf/LuMoSDK使用手册.pdf)
- [FZMotion MB/UE 数据传输手册 PDF](pdf/FZMotion-MB-UE数据传输操作手册.pdf)
- [人体关节顺序与命名 DOCX](docs/FZMotion人体关节顺序及命名.docx)

## 厂家资料 Markdown 转换结果（未改动）

- [FZMotion 3.0 Motar 用户手册](markdown/FZMotion3.0-Motar用户使用手册V1.0/FZMotion3.0-Motar用户使用手册V1.0.md)
- [FZMotion 导出 CSV 格式](markdown/FZMotion导出CSV文件格式说明V1.2/FZMotion导出CSV文件格式说明V1.2.md)
- [LuMoSDK 手册](markdown/LuMoSDK使用手册/LuMoSDK使用手册.md)
- [FZMotion MB/UE 数据传输手册](markdown/FZMotion-MB-UE数据传输操作手册%20%282%29/FZMotion-MB-UE数据传输操作手册.md)

转换文档可能含 OCR、表格和图号错误，接口契约以原始资料及实测为准。转换目录内的图片、元数据与日志保留，不拆散、不去重；无正文的旧转换目录仅保留记录，不列为阅读入口。

## 本次整理后的路径

| 原根目录文件 | 新位置 |
|---|---|
| `机器人动捕标定_核心流程.md` | `workflow/` |
| `动捕数据层_设计规格.md` | `document/design/` |
| `机器人动捕标定方案_v4.md` | `document/references/` |
| `FZMotion动捕系统要点_v4对接.md` | `document/references/` |
| `PLAN.md` | `document/archive/plans/空间外参核心流程精简计划.md` |

根目录包含工作区入口、项目配置和统一的 `workflow/`。原根目录 `plans/` 两份现行文档分别合入 `workflow/首次试采操作指南.md` 和 `workflow/机器人动捕标定_核心流程.md`，不再单独维护；历史存档不移动。现行链接已更新；最小操作流程原文与其副本保持不变。

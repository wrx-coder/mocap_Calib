# 文档索引

## 当前主线

现场优先：[首次试采操作指南](workflow/首次试采操作指南.md)；软件接口：[标定数据契约 v1](design/标定数据契约_v1.md)。D435i 的已标定内参不重做，主线为 RGB-D/color optical。

| 文档 | 用途 |
|---|---|
| [机器人动捕标定：空间外参核心流程](workflow/机器人动捕标定_核心流程.md) | 现场执行唯一主入口，仅空间外参 |
| [工作区约定与接口](design/工作区约定与接口.md) | 模块分工、数据契约和目录对应 |
| [配置模板说明](../configs/README.md) | 填写真实会话和相机信息 |
| [数据目录说明](../data/README.md) | 原始录制、处理产品与配对记录 |
| [结果目录说明](../outputs/README.md) | 标定包、报告与验收状态 |
| [最小验证](../tests/README.md) | 软件合成闭环与现场留出边界 |

## 设计与参考资料

- [动捕数据层设计规格](design/动捕数据层_设计规格.md)：历史完整数据层设计。当前优先 P1/P2，P3 时间轨迹与 P4 在线接口不属于本次骨架范围。
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
| `机器人动捕标定_核心流程.md` | `document/workflow/` |
| `动捕数据层_设计规格.md` | `document/design/` |
| `机器人动捕标定方案_v4.md` | `document/references/` |
| `FZMotion动捕系统要点_v4对接.md` | `document/references/` |
| `PLAN.md` | `document/archive/plans/空间外参核心流程精简计划.md` |

根目录只保留工作区入口与项目配置。现行核心流程的相对链接已更新；历史文档正文保留原样。

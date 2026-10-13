# first_test 原始来源与整理入口

本目录原始 bag/CSV 未修改；采集背景见 [AGENT.md](AGENT.md)。Git 仅保留脚本与文档；原始录制和派生产品保留本地，以下数据链接需要相应本地归档。

候选求解入口：`infer_geometry.py`。可直接查看的外参摘要：[两个 T_W_C](../document/results/first_test_extrinsics.md)；完整推进：[workflow 记录](../workflow/first_test_数据驱动推进记录.md)。

- [整理说明与格式](../data/processed/first_test/README.md)
- [原始归档清单](../data/raw/first_test/file_manifest.csv)
- [录制索引](../data/processed/first_test/recordings.csv)
- [待确认事项与校验报告](../outputs/reports/first_test/readiness.md)
- [本地配置](../configs/local/first_test/README.md)

脚本：`parse_rosbags.py` 解码；`organize_first_test.py` 分类、转项目长表/帧NPZ、登记溯源。脚本拒绝覆盖已存在的会话目录。

静态数据主要入口：[静态分类表说明](../data/processed/first_test/static/README.md)；复现同步：`python3 sync_static_first_test.py`。

# TRANSFER_DESIGN — 跨靶点迁移实验（蓝图 §12，P3-05 后半）

> **本文件是预注册文档**：实验未跑前确定口径；跑之后不改。改动需在 `docs/experience`（经验库）里新增一条"口径修订"记录并说明理由。
> 三靶点基线（per-target，scaffold split，锁定测试）已完成并锁定：MOR 0.9339 / KOR 0.8685 / DRD2 0.9015（AUROC，xgboost）。

## 1. 对比口径（已决，按本文件执行）

**主口径：Pooled-with-target-indicator vs per-target，锁定测试上按靶点分别读数。**

- **Arm A（基线，已有）**：每靶点单独训练（现状）。
- **Arm B（pooled）**：把三靶点的 train 分子**合并**，特征矩阵追加 3 列 target 指示位（one-hot），训练**一个**模型；验证与评测严格按各靶点自己的 scaffold manifest 读数。
- **Arm C（zero-shot 迁移分析，非主口径）**：用 MOR 模型直接给 KOR/DRD2 的验证集打分算 AUROC（AUROC 是靶点内排序量，跨靶点分数可比性在此口径下成立），用于回答"MOR 模型对相似靶点有多大的免费迁移"，只做分析、不进结论表。

**对比量**：Δ(target) = AUROC(B, target) − AUROC(A, target)，AUPRC 同理。
**负迁移判定（预注册）**：ΔAUROC ≤ −0.02 且其 95% CI 不含 0 → 判负迁移；只报 Δ 及 CI，不因单次波动改口径。
**不确定性**：**按 scaffold 聚类 bootstrap**（1,000 次，seed 17）——普通 bootstrap 在 scaffold 划分下不成立，必须以 scaffold 为重采样单元。

## 2. 数据纪律

- pooled 训练只允许三靶点各自的 **train split**；validation 用各自 val split；**锁定测试任何臂都不可触碰**（只有评测器）。
- 类别不平衡保持原样（不加重采样）；`class_weight` 维持基线设置以保证可比。
- 特征化参数固定 radius=2 / n_bits=2048（与基线一致）；target 指示列是**唯一**新增特征。

## 3. 执行与产物

- 实现位置：`modeling/train.py` 增加 `--pool <csv,…>` 与 `--pool-targets <names,…>`（或在 `data/pool.py` 生成 pooled dataset 后复用现有 CLI——实现期二选一，倾向后者，避免训练器复杂化）。
- 产物：`pooled/models/xgboost/`（metrics.json 注明 pooled）、`pooled/predictions.csv`、锁定测试经评测器出 `metrics_test_locked_pooled.json`。
- 报告口径：三靶点 × {A, B} 的 AUROC/AUPRC 表 + Δ 及 CI；**EF@1% 只对 A/B 各自的靶点内排序有意义**。

## 4. 结论的表述规则

- 正迁移：Δ > 0 且 CI 不含 0 → "pooled 提升了该靶点"；
- 无差异：CI 含 0 → "未观察到差异"（禁止写成"没有影响"）；
- 负迁移：按 §1 判定 → 记录进经验库（applicability 注明"该 pooled 口径对该靶点为负迁移"），并作为 Phase 4 多靶点扩展的前置警告。

## 5. 不做的事

- 不做跨终点（Ki/IC50/EC50）pooled —— §9.2 第 2 条禁止；
- 不做超参搜索后挑口径 —— 口径已在本文锁定；
- 不用 validation 结果挑选报告数字 —— 只看锁定测试。

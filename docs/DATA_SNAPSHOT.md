# DATA_SNAPSHOT — ChEMBL_37 / OPRM1

> 生成命令：`scientific/.venv/bin/python -m evovs_science.data.chembl --outdir .artifacts/chembl/oprm1 --max-pages 20`
> 产物在服务器 `scientific/.artifacts/chembl/oprm1/`（33 MB，**不入 Git**），元数据如下。

## 快照身份

| 项 | 值 |
|---|---|
| 数据源 | ChEMBL 公共 API `https://www.ebi.ac.uk/chembl/api/data` |
| 版本 | **ChEMBL_37** |
| 发布日期 | 2026-05-01 |
| 靶点 | `CHEMBL233` — Mu-type opioid receptor（人源 OPRM1） |
| 拉取时间 | 2026-11-05T09:28Z |
| 终点 | `Ki, Kd, IC50, EC50`（**分开存储，不跨终点平均**） |
| 分页 | 1000 条/页 × 20 页 |
| 原始页 | `raw/page-0000.json … page-0019.json`，每页 sha256 记入 `artifact_manifest.json` |

## 数量与审计（`dataset_audit.json`）

| 指标 | 值 |
|---|---|
| 拉取 | 16,240 |
| 保留（SMILES 可解析） | 16,131 |
| 丢弃 | 109（无 SMILES 或不可解析，**不修复不猜测**） |
| Ki | 8,763 |
| IC50 | 3,571 |
| EC50 | 3,755 |
| Kd | 42 |
| 关系符 `=` | 11,106 |
| 关系符 `>` | 2,369 |
| 关系符 `<` | 282 |
| **无关系符（NULL）** | **2,367** |
| 单位 `nM` | 14,059 |
| **单位缺失** | **2,055** |
| 非 nM 单位 | 13（`Ke nM-1`、`/s`、`%`、`10^-x microM/nM` 等） |
| 结合测定 `B` | 12,135 |
| 功能测定 `F` | 3,827 |
| 其他 `A` / `T` | 129 / 40 |
| 完全重复组 | 1,345 |

## 结论与已知问题（Phase 2 必须先处理）

1. **2,367 条无关系符**：不能当作精确值使用，必须单列 `censored_unknown` 或不进入回归。
2. **2,055 条无单位**：无法换算，必须排除或单独审计；**绝不能默认 nM**。
3. **13 条非 nM 单位**（含 `10^-4microM` 这类字符串）：需要显式单位解析表，不得盲目乘法。
4. **1,345 组重复**：同一分子同一终点同一数值多次出现，训练前须去重（保留 provenance），但**不同 seed/不同 assay 不算重复**。
5. **`assay_type=F`（3,827 条）是功能测定**（激动/拮抗），与结合活性语义不同；混用会重演蓝图 §9.2 第 6 条的错误。
6. **Kd 仅 42 条**：不足以单独建模，只能在方法学说明后并入 Ki 或单列小样本分析。

**当前状态：这是"原始快照 + 审计"，不是可训练数据集。** 上述 6 项处理完之前，任何 MOR 模型结果都不具备科学意义。

---

## 归一化结果（Ki 单终点，2026-11-05）

命令：`.venv/bin/python -m evovs_science.data.normalize --input .artifacts/chembl/oprm1/activities_normalized.csv --outdir .artifacts/chembl/oprm1/ki --endpoint Ki`

| 项 | 值 |
|---|---|
| 输入行 | 16,131 |
| 保留 | **6,339**（Ki + assay 置信度 9 + assay_type B/F） |
| 排除 | 其他终点 7,368；置信度 8 共 2,388；assay_type 其他 36 |
| 通道 | exact 5,310 / **censored 903** / 无关系符 126 |
| 分子（有精确值） | 4,472 |
| 带标签 | 3,281（**正 2,575 / 负 706**） |
| 冲突分子（同分子同终点极差 ≥10×） | 84（标记，不平均） |
| 划分 | train 2,297 / validation 493 / test 491 分子 |
| scaffold 数 | 463 / 476 / 491 |
| 检查 | `no_molecule_in_two_splits: true`、`no_scaffold_crosses_splits: true` |

标签规则（预先声明）：`pX ≥ 7`（≤100 nM）为正、`pX ≤ 6`（≥1 µM）为负；**灰区与全部 censored 行不标注**；未测定对永不作为负例。

产物：`measurements.csv`（逐行通道）、`dataset.csv`（每分子一行，仅精确值）、`split_manifest.json`、`dataset_audit.json`、`artifact_manifest.json`。

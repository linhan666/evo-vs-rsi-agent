# PHASE3_REPORT（部分：P3-01/03/04/05；P3-02 部分完成）

> 本阶段无新外部依赖；venv 不变。所有脚本为 operator/CLI 级执行，服务保持停止。

## 数据（P3-03，靶点 ID 经 API 核实，非凭记忆）

| 靶点 | ChEMBL ID | UniProt | 快照（拉取/保留/丢弃） | Ki 行 | 归一化→分子→标签 | 划分 train/val/test |
|---|---|---|---|---|---|---|
| MOR | CHEMBL233 | P35372 | 16,240/16,131/109 | 8,763 | 6,339→4,472→3,281 | 2,297/493/491 |
| **KOR** | **CHEMBL237** | P41145 | 13,456/13,330/126 | 6,261 | 4,174→3,100→2,233 | 1,564/335/334 |
| **DRD2** | **CHEMBL217** | P14416 | 19,662/19,564/98 | 14,783 | 10,753→6,606→3,873 | 2,712/581/580 |

三靶点 `no_molecule_in_two_splits` / `no_scaffold_crosses_splits` 全部为 true。
**本阶段修复的缺陷**：split manifest 写在 outdir mkdir 之前（首跑必现 FileNotFoundError，KOR/DRD2 首跑暴露）。

## 模型与锁定测试（xgboost，scaffold-manifest 训练；测试仅评测器可读）

| 靶点 | train/val | val AUROC | **test AUROC** | test AUPRC | test EF@1% | test n |
|---|---|---|---|---|---|---|
| MOR | 2,297/493 | 0.9021 | **0.9339** | 0.9722 | 1.379 | 491 |
| KOR | 1,564/335 | 0.8765 | **0.8685** | 0.9263 | 1.459 | 334 |
| DRD2 | 2,712/581 | 0.9214 | **0.9015** | 0.9260 | 1.824 | 580 |

## 100k 库复用筛选（P3-04）与三靶点矩阵（P3-05）

- 同一 `library_100k.smi`（sha256 记录在 `library_manifest.json`）筛 MOR/KOR/DRD2 三次：耗时 83.6 / 65.7 / 69.8 s。
- `screening/matrix.py`：按分子 id **inner join** → **100,000 行 × 三靶点 score+rank**（`.artifacts/matrix/three_targets.csv`；样例入 `docs/evidence/phase3/`）。
- 明确边界：跨靶点分数**不可直接比较**，矩阵不衍生 selectivity 列（§9.6 要求校准后输出才可比较）。

## 经验库（P3-01）

`experience/store.py`：`record`（dataset/model/screening 三类，payload 摘要 + sha256 + **applicability 一句话**）与 `retrieve`（按 target/kind 过滤）。当前 9 条记录（3 靶点 × 3 类），每条明确"跨靶点迁移不成立"等边界。

## P3-02 状态（不宣称完成）

检索 CLI 完成；**Agent 侧注入未做**——如何把经验以"事实 + 适用性限制"的形式进入 prompt、并防止硬编码结论，需要 Phase 3 后半的机制设计。

## 防再发机制（承接 Gate 2 两缺陷）

1. **缺陷 1（改源码未重建 lib）**：`ops/check_build_freshness.py` 启动门禁——`src/**.ts` 任一比 `lib/index.js` 新即拒绝启动（实测通过）。
2. **缺陷 2（TS schema 与 Python CLI 漂移）**：`tests/research.spec.ts` 新增契约测试——三个工具 argv 的**每一个 flag** 必须出现在对应模块 `--help` 中（13/13 通过）。
3. **新缺陷（本阶段发现并修）**：normalize 首跑目录创建顺序（见上）。

## Known failures / not done

- B-002 上游 Feishu 用例（与本阶段无关）；
- P3-02 的 Agent 侧接入；
- P3-05 的 selectivity 列与 OOD/不确定性列（§9.6 全量字段）——待校准模块；
- 经验库当前为文件存储，并发写未加锁（单人 operator 场景可接受）。

## Next phase

- Phase 3 后半：Memory 注入机制设计 → 经真实 Ticket 的 KOR/DRD2 执行（复用经验库）；
- §12 的跨靶点迁移实验设计（负迁移检测）；
- B-005 专用账号（建议在 Phase 4 前落实）。

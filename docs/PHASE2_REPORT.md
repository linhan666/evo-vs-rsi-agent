# PHASE2_REPORT（部分：P2-04 + P2-05）

> 格式遵循蓝图 §21。这是 Phase 2 的**前半段**：数据隔离 + 模型适配器。
> P2-01/02/03 的 ChEMBL 快照部分见 `docs/DATA_SNAPSHOT.md`。

## Upstream and environment

- Upstream commit: `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`（未变）
- DSH version: `@deepseek-ai/dsh@0.2.1-rc.5`
- Python/Node versions: Python 3.12.3（venv）/ Node v22.23.4 / pnpm 11.7.0
- Environment lock: venv 新增 `xgboost==2.1.4`、`catboost==1.2.8`（连带 pandas/matplotlib/graphviz 等，全部来自清华镜像）
- 数据快照: ChEMBL_37 / OPRM1（`docs/DATA_SNAPSHOT.md`）

## Files changed

| 文件 | 为什么 |
|---|---|
| `scientific/src/evovs_science/data/normalize.py` | **P2-04 核心**：`--protected-dir` 把最终测试集标签写到 agent 不可读的位置（目录 700 / 文件 600）；`dataset.csv` 只含 train+validation 分子；灰区分子不进任何建模表 |
| `scientific/src/evovs_science/modeling/train.py` | 重写：`--split-manifest` 支持（训练只用 scaffold-train 分子、指标只算 scaffold-validation 分子）；模型注册表 logreg/rf/xgboost/catboost（懒加载）；标签列名可配；灰区空标签跳过 |
| `scientific/src/evovs_science/evaluation/evaluate.py` | **新增**：独立评测器，唯一允许读最终测试标签的组件；输出 `metrics_test_locked_*.json`（含模型与测试集的 sha256） |
| `scientific/src/evovs_science/chemistry/featurize.py` | `--id-column/--smiles-column`；CSV 读取改 `utf-8-sig` |
| `src/research/registry.ts` | 工具改名 `sklearn.train` → `ml.train`（现在背后有四个模型库）；可选模型枚举扩展 |
| `tests/research.spec.ts`、`.gitignore`（`protected/`）、`scientific/requirements.txt` | 随动 |

## Executed commands (real, not assumed)

| 命令 | 结果 |
|---|---|
| `pip install xgboost==2.1.4 catboost==1.2.8` | PASS（清华镜像） |
| `data.normalize … --protected-dir /home/linhan_cluster/evo_vs_rsi/protected/chembl37_ki` | PASS — `dataset.csv` 2,790 分子（train+val）；`protected/final_test_Ki.csv` 491 行（700/600） |
| `chemistry.featurize --id-column molecule_chembl_id --smiles-column canonical_smiles …` | PASS |
| `modeling.train --split-manifest … --model logreg/rf/xgboost/catboost` | PASS ×4（`split_strategy: "scaffold-manifest"`） |
| `evaluation.evaluate …` ×4 | PASS ×4，输出在 protected 目录 |
| `pnpm check` / `pnpm build` | 60/61（唯一失败 B-002）/ PASS |

## Acceptance tests

- **P2-04（隔离）：PASS（构造级）。** `dataset.csv` 中不存在任何 test 分子；最终测试标签只存在于 `protected/`（在 `EVOVS_DATA_ROOT` 之外，科学工具的 `DataPath` schema 会拒绝其它绝对路径）。
- **T-011（Agent 无法读 heldout 标签）：构造级通过** —— 受保护路径不在任何工具可达范围内。**尚未**用真实 Ticket 做一次"Agent 尝试读取被拒"的现场验证。
- **P2-05（模型适配器）：PASS。** 四种模型均以 scaffold manifest 训练并完成独立评测（下表）。
- **验证协议修正**：此前 `train.py` 自做随机划分、忽略 scaffold manifest——已重写为"manifest 优先"，随机划分仅作无 manifest 时的回退并在 `split_strategy` 中如实标注。
- **Known failures**：`tests/sources.spec.ts` Feishu 用例（B-002，上游缺陷）。

## 双轨指标（validation = scaffold 划分；test = 锁定最终测试，仅评测器可见）

| 模型 | val AUROC | val AUPRC | **test AUROC** | **test AUPRC** |
|---|---|---|---|---|
| logreg | 0.8348 | 0.9246 | 0.8632 | 0.9310 |
| rf | 0.9070 | 0.9631 | 0.9281 | 0.9699 |
| **xgboost** | 0.9021 | 0.9539 | **0.9339** | **0.9722** |
| catboost | 0.8920 | 0.9516 | 0.9128 | 0.9637 |

测试集构成：491 分子（正 356 / 负 135）。**解读边界**：这是 ChEMBL_37 的 Ki 数据、阈值 pX≥7/≤6 的预测难度指标，**不是**虚拟筛选命中率；100k 库无标签，EF@1% 在测试集上计算、在筛选时不可计算。

## Scientific / security integrity

- Data split changes: **yes, pre-registered** — scaffold split 0.7/0.15/0.15、阈值 pX≥7/≤6，已写入 `docs/DATA_SNAPSHOT.md` 与 `dataset_audit.json`，此后不再改。
- Protected test access: 评测器独立进程读取；Agent 工具面不可达（构造级）。
- Permission changes: none。
- 遗留：`dsh-fs-sandbox` 可写根的显式验证；专用 OS 账号（B-005）。

## RSI classification

不适用。本阶段是数据与模型能力，不是 Harness 自修改。

## Gate 2：端到端（2026-11-05 20:55，PASS）

真实 Ticket `science_007` → Ticket `d94f469b0b6c12a952a99d2c4ee6ce92`（**无 shell** 模式）：

| 步骤 | Agent 动作 | 作业结果 |
|---|---|---|
| 1 | `scientific_tools` 发现 3 个工具 | — |
| 2 | `rdkit.featurize`（输入=数据根绝对路径，列名覆盖） | SUCCEEDED → `runs/features.npz` |
| 3 | `ml.train`（xgboost + `split_manifest`，label 列覆盖） | SUCCEEDED → `runs/models/xgboost/` |
| 4 | `screening.rank`（用自己的模型 + 100k 库） | SUCCEEDED → `runs/screening/` |
| 5 | 回复 | `2790 molecules featurized, validation AUROC 0.9021, 100,000 library molecules ranked, top-1 score 0.998451` |

独立评测器对 **Agent 自训模型** 的锁定测试结果：**AUROC 0.9339 / AUPRC 0.9722 / EF@1% 1.379** —— 与 operator 训练的模型完全一致（同数据同参数同种子，确定性可复现）。证据：`docs/evidence/phase2/`（22 个文件）。

### 排序库（ZINC250k）

| 项 | 值 |
|---|---|
| 来源 | `aspuru-guzik-group/chemical_vae` 的 `250k_rndm_zinc_drugs_clean_3.csv` |
| 来源 sha256 | `35e3f1a52b1badc0697e373d73a18ad773f415936ff992f4c6baa2e067b3e6ae` |
| 解析 / 规范化去重 | 249,455 / 249,455（RDKit，全部合法） |
| 抽样 | **种子 17 确定性抽样 100,000**（`library_100k.smi`，KOR/DRD2 复用同一文件） |
| 筛选耗时 | 83.6 s（100k 全量特征化 + 打分 + 排序） |

### 排查记录（两次失败，均为真实缺陷）

1. **science_005**：lib/ 是在 `screening.rank`、label 列、split_manifest 之前构建的——**改了源码没重建**（操作顺序失误）。
2. **science_006**：暴露真正的源码缺口——`FeaturizeInput` 缺列名字段、`TrainInput.model` 枚举只有两个。Agent 两次都准确诊断并写下了 `runs/BLOCKER.md`，且**主动请示**是否可以自己打补丁（被拒：harness 源码不在 worker 可写面内，由 operator 修复）——这正是三类修改面隔离应有的行为。

## Next phase

1. **P2-06**：MOR 完整可追溯任务（经真实 Ticket、无 shell 模式）+ 100k 库排序（需要 `screening/` 模块与 100k 库文件——**库文件需要你指定来源**）；
2. `evaluation/` 接入真实 Ticket 流程的授权方式（谁触发评测、结果如何回传）需要一次设计确认；
3. `dsh-fs-sandbox` 可写根验证 + B-005 专用账号。

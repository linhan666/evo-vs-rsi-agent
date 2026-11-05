## Phase 1 Implementation Report

> 格式遵循蓝图 §21。凡未运行或未通过的事项均显式标注；`NOT DONE` 不写成"部分完成"。

### Upstream and environment

- Upstream commit: `dsh-superagent-prototype` = `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`（本阶段未变）
- Local commits: `f3621c7`（registry / runner / tools）、本次补充（lossless-JSON 修复 + 文档）
- DSH version: `@deepseek-ai/dsh@0.2.1-rc.5`
- Python/Node versions: Python 3.12.3（venv）/ Node v22.23.4 / pnpm 11.7.0
- Environment lock: `scientific/.venv`，`pip freeze` 等价于 `scientific/requirements.txt`：
  `numpy==2.1.3`、`scikit-learn==1.5.2`、`joblib==1.4.2`、`rdkit==2024.9.5`（+ scipy 1.18.1、Pillow 13、threadpoolctl 3.7）
- 解释器暴露方式：`EVOVS_PYTHON=/home/linhan_cluster/evo_vs_rsi/scientific/.venv/bin/python`（服务启动时注入，未写 shell rc）

### Files changed

| 文件 | 为什么 |
|---|---|
| `scientific/src/evovs_science/manifest.py` | sha256 / 环境指纹 / `artifact_manifest.json`（§8.4） |
| `scientific/src/evovs_science/chemistry/featurize.py` | SMILES → ECFP + 2D 描述符；非法 SMILES **跳过并记录**（T-004） |
| `scientific/src/evovs_science/modeling/train.py` | 小模型训练与 AUROC/AUPRC/EF@1% 指标；单类测试折时指标写 `null` 而非 0 |
| `scientific/scripts/bootstrap_env.sh` | 无 pip 主机的 venv + pip 引导 + 依赖 pin + `.pth` 挂载 |
| `scientific/requirements.txt`、`examples/molecules.fixture.csv` | 依赖锁定；24 条合法 + 1 条故意非法 SMILES 的**合成** fixture |
| `src/research/registry.ts` | 白名单工具：`tool_id`、能力、失败码、zod 输入、**固定 argv**、产物清单 |
| `src/research/job-runner.ts` | 沙箱 runner：`shell:false`、独立进程组、墙钟强杀、stdout/stderr、sha256 清单、`INTERRUPTED` |
| `src/research/tools.ts` | worker 工具：`scientific_tools`、`scientific_run_job`、`scientific_job` |
| `src/app/tools/executor.ts` | 在每个 Executor Session 注册上述工具（一行接入） |
| `tests/research.spec.ts` | 9 个测试：schema 拒绝、路径越界、成功/失败/超时/缺产物、`INTERRUPTED`、JSON 往返 |
| `tests/model-surface.spec.ts` | 工具集合与字符预算断言随新工具同步（预算内：40,685 → 通过） |
| `docs/007-architecture.md`、`.gitignore`、`ops/wire_scientific_tools.py`、`ops/register_research_docs.py` | 索引、忽略 venv、可重放的接线脚本 |

### Executed commands (real, not assumed)

| 命令 | 结果 | 输出位置 |
|---|---|---|
| `bash scientific/scripts/bootstrap_env.sh` | PASS — rdkit 2024.09.5 / sklearn 1.5.2 / numpy 2.1.3 | `scientific/.dl/bootstrap.log` |
| `.venv/bin/python -m evovs_science.chemistry.featurize …` | PASS — `rows_valid=24, rows_invalid=1` | `scientific/.artifacts/feat/` |
| `.venv/bin/python -m evovs_science.modeling.train …` | PASS — AUROC 0.8 / AUPRC 0.9429 / EF@1% 1.4 | `scientific/.artifacts/model/` |
| `npx tsc --noEmit` | PASS | — |
| `npx vitest run tests/research.spec.ts` | PASS — 9/9 | — |
| `pnpm check` | 60/61 文件通过；唯一失败为 B-002（Feishu） | `docs/evidence/phase0/pnpm_check_phase1.log` |
| `pnpm build` | PASS | — |
| 真实 Ticket `science_001` / `science_002` | 两个作业均 SUCCEEDED；回复 `24 valid rows, 1 invalid row, AUROC 0.80` | `docs/evidence/phase1/` |

### Acceptance tests

- **Gate 1：PASS。** Agent 在真实 Ticket 中先调用 `scientific_tools`（列出 `rdkit.featurize` 0.1.0 与 `sklearn.train` 0.1.0），再调用 `scientific_run_job` 两次；两次运行产物齐全（`runs/features.npz`、`runs/feature_meta.json`、`runs/model/{metrics.json,predictions.csv,model.joblib,artifact_manifest.json}`），无预编排 DAG。
- **T-004（非法 SMILES 不被静默替换）：PASS。** fixture 中 `NOT_A_SMILES` 计入 `rows_invalid=1` 并写入 `feature_meta.json.invalid`，训练集只看到 24 条。
- **T-008 / T-009（不同 seed 不错去重、同 seed 命中缓存）：NOT DONE。** 运行器没有实现 idempotency 缓存；`idempotency_key` 只在 schema 中占位。属 Phase 4 的"重复实验"诊断前提，此处不宣称通过。
- **T-010（超预算被拒绝/停止）：部分。** 墙钟超时会 `SIGKILL` 整个进程组（单测覆盖）；**内存上限未强制**，`cpu_seconds/gpu_seconds` 未计量（记为 `null`，不编造）。
- **Known failures**：`tests/sources.spec.ts` 的 Feishu 用例（B-002，上游缺陷，与本阶段无关）。

### Scientific / security integrity

- Data split changes: **no**（仅合成 fixture；未接触任何真实活性数据）
- Protected test access: **none**（无 heldout）
- Permission changes: **none**（未改系统包、未改 `~/.bashrc`；venv 与 `.pth` 均在 `scientific/` 内）
- **标签语义**：fixture 标签是合成的，`metrics.json` 明确写 `label_source: "fixture"` 且 `notes` 声明"描述流水线，不代表 GPCR 活性"。报告中不得把它当作 MOR 结果。
- **路径约束**：工具参数只接受工作目录内的相对路径，`../` 与绝对路径被拒（单测覆盖）。
- **凭据**：worker 环境变量白名单（PATH/HOME/LANG/TMPDIR/TZ + 数值型线程变量）；`EVOVS_PYTHON` 由宿主注入。

### Artifact links and reproducibility

- Dataset manifests: fixture 的 sha256 在每个 job 的 `artifact_manifest.json` 的 `inputs` 中
- Job/trace logs: 每个作业目录 `.jobs/<job_id>/` 下 `job.json`、`stdout.log`、`stderr.log`、`result.json`、`artifact_manifest.json`
- Code commit: `f3621c7` + 本次文档/修复提交
- Result artifacts: `docs/evidence/phase1/`（8 条 outbox 消息、4 份 result/manifest、metrics、state）

### RSI classification (only for Evolution phases)

不适用：本阶段没有任何 Harness 候选或影子评估。`scientific_*` 工具是新能力，不是"进化"。

### Post-Gate verification（2026-11-05 19:02，两个教训与一次复验）

**science_003 启动失败（根因：我自己的推送配置）**

- 现象：worker 回了 acknowledgement 后 assignment 立即失败，无任何作业。
- 根因（store 中 assignment 报告原文）：`The git configuration of the repository in <ticket dir> sets credential.helper, which the agent's git would also read; remove them.` —— 我为推送 GitHub 在**仓库本地** `.git/config` 写入了 `credential.helper`，而 ticket 目录在该仓库内；`docs/003-execution.md` 明确规定 ticket 目录所在仓库不得携带凭据配置。
- 修复：撤掉仓库级配置，凭据只在推送命令上以 `git -c credential.helper=…` 临时传入（`ops/push.sh`，永不落盘）。**教训：任何会改变仓库配置的全局性操作，都要先对照 docs/003 的 ticket 目录规则。**

**science_004（无 shell + 只读数据根）：PASS**

| 项 | 值 |
|---|---|
| Ticket | `5eb61a30e3975893fa2cdd97a47c5290` |
| Worker 动作 | `scientific_tools` → `scientific_run_job`（输入为 `EVOVS_DATA_ROOT` 下的**绝对路径**，未复制文件） |
| 作业 | `rdkit.featurize` SUCCEEDED，产物 `runs/features.npz`、`runs/feature_meta.json` |
| 回复 | `valid rows 24, invalid rows 1.`（与 fixture 完全一致） |
| 意义 | worker 与主 Session 均已无 shell；读取只读数据根、产出带 sha256 的工件，链路仍然完整 |

### Next phase

- **Recommended tasks（Phase 2，P2-01…P2-06）**：
  1. ChEMBL/BindingDB 固定快照导入器（先读已下载文件，不在线抓取）；
  2. SMILES 标准化、endpoint/unit/relation 处理、冲突报告（`<` `>` 截断值单独通道）；
  3. 标准化分子去重 + Scaffold Split manifest；
  4. 训练/验证/最终测试隔离 API（最终测试只经独立评测器）；
  5. RF / XGBoost / CatBoost 适配器（可选，不强制全跑）；
  6. MOR 完整一次可追溯任务 + 100k 排序。
- **Blocking decisions requiring operator authorization**：
  - **B-005**（隔离）仍未解决：worker 以操作者身份 `danger-full-access` 运行，能读整个 `$HOME`。Phase 2 要接触真实活性数据，建议在此之前先建专用 OS 账号或容器边界。
  - 真实数据来源与许可（ChEMBL 快照版本、是否使用 BindingDB）需要你确认后我再落盘。
- **本阶段已知缺口（不计入 Gate 通过）**：无 idempotency 缓存、无内存 rlimit、无 GPU 计时、`scientific/` 无 `data/` 与 `screening/` 模块、工具结果未做跨作业的全局 artifact registry。

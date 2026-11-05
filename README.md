# EvoVS-RSI

面向跨靶点药物虚拟筛选的自主 Agent Harness 与递归自进化（RSI）系统。

> **本项目的本体不是"自动选择最优 QSAR 模型"，而是"让通用科研 Agent Harness 在持续执行不同靶点任务时，对自身完成科研任务的运行机制进行证据驱动、可验证、可回滚的递归改进"。**
> —— 蓝图 §23 最终一句话

- 设计蓝图：`EvoVS_RSI_Harness_Codex_Blueprint.md`（v0.1.0，2026-11-05）
- 代码基底：`deepseek-ai/dsh-superagent-prototype`（MIT，研究原型）
- RSI 机制参考：`pzs19/HarnessPro`（仅参考，不替代基底）
- 当前阶段：**Phase 5 — 自修改闭环与科学面板扩展（尾段）**
- 状态（2026-11-06 02:55 实测）：**Phase 0–3 的 Gate 全部通过；Phase 4/5 已跑通一次真实的"候选→影子→晋升→生产冒烟"全链条，并两次用预注册规则拒绝了不该上线的候选。**
  Agent 在真实 Ticket 中自主完成 featurize → train → 100k 筛选 → 经验检索 → 锁定评测；Harness 已完成一次证据驱动的自我修改（candidate1 并行特征化，加速 2.1×/3.3×、工件等价率 1.0）并写入生产默认。
  **尚未完成**（见 `docs/PHASE5_REPORT.md` 末节）：Agent 自主提出候选（P4-04）、Pareto 集与 VersionManager；评测自动触发（Engine pass）已实现、待真实 Ticket 确认。

## 阶段映射（项目阶段 ≠ 蓝图阶段，务必对照）

项目推进过程中把蓝图的 P4 与 P5 合并成了"项目 Phase 4/5"，编号与蓝图不一致。**引用 Gate 时以本表为准。**

| 项目阶段 | 覆盖的蓝图工作项 | 内容 | 状态 |
|---|---|---|---|
| Phase 0 | P0-01…06 | 上游审计、运行环境、真实 Ticket 生命周期、重启恢复 | ✅ Gate 0 |
| Phase 1 | P1-01…06 | 科研 Python 环境、JobSpec/JobResult、工具注册、工件 sha256 | ✅ Gate 1 |
| Phase 2 | P2-01…06 | 数据审计/归一化/scaffold split/测试隔离/MOR 100k | ✅ Gate 2 |
| Phase 3 | P3-01…05 | 经验库、KOR/DRD2、三靶点矩阵、§12 迁移实验 | ✅ Gate 3 |
| Phase 4 | P4-01/02/03/05/06 + P5-01/02/05/06 | trace 语料、Intake 校验、影子评估、晋升门禁、评测器垫片 | ✅ 核心完成（缺 P4-04） |
| Phase 5 | P4-02 续 + P5-03（部分）+ P6 数据面预置 | 并发锁、失败聚类、IC50 独立通道、双端点分歧、descv2 裁决 | ✅ 本阶段交付（含 1 处结论更正，见报告 §6） |
| 下一阶段 | P4-04 / P5-03 / P5-04 / P5-05 | 自动提候选、统一硬门禁、Pareto 集、VersionManager | ⬜ 未开始 |
| Phase 6/7 | P6 / P7 | 四组对照（Workflow / Fixed / Memory-only / RSI）、扩展工具 | ⬜ 未开始 |

## 关键事实（实测，非推测）

| 项 | 值 |
|---|---|
| 上游 commit | `8c32a9dc5d72c033816c6a8110b37f40cf94fba4` |
| DSH runtime | `@deepseek-ai/dsh@0.2.1-rc.5` |
| Node / pnpm | v22.23.4 / 11.7.0（用户态 `~/software`） |
| 运行主机 | **172.25.16.37**（8×H100 / 128 核；`172.25.18.26` 为迁移前存档） |
| `pnpm typecheck` | PASS |
| `pnpm test` | **60/61 文件、1216/1217 用例**；唯一失败为 B-002（上游 Feishu 竞态，非主链路） |
| Agent 工具面 | **5 个**：`rdkit.featurize` / `ml.train` / `screening.rank` / `experience.retrieve` / `evaluation.locked` |
| 锁定测试 AUROC（Ki，xgboost） | MOR **0.9339** / KOR **0.8685** / DRD2 **0.9015**（test n=491/334/580） |
| 锁定测试 AUROC（IC50 独立通道） | MOR **0.9188** / KOR **0.8954** / DRD2 **0.9157**（test n=99/159/63） |
| 筛选库 | ZINC250k 规范化去重 → 种子 17 抽样 **100,000**（`library_100k.smi`） |
| Evolution 语料 / 经验库 | **20 traces** / **24 条经验记录**（model 7、screening 7、transfer 6、dataset 3、harness 1） |
| 已晋升候选 | **candidate1**（featurize 分块并行，默认 `EVOVS_FEAT_JOBS=8`，回滚=改回 1） |
| 被拒绝候选 | candidate2（pooled 重校准，负迁移恶化至 −0.0614）；candidate3（descv2，Ki 三条 CI 全含 0；IC50 通道 Δ +0.0035/+0.0037/−0.0011，同为持平 → 保持 v1） |

## 快速开始

```sh
source env.sh                 # Node 22 + pnpm + 模型凭据（凭据在仓库外，600）
pnpm install --frozen-lockfile
pnpm check                    # typecheck + test + build

# 科研 Python 包（venv 已装 rdkit / sklearn / xgboost / catboost）
PYTHONPATH=scientific/src python3 -m unittest discover -s scientific/tests -v
```

启动 Harness 服务需三件套环境变量（服务默认停止）：

```sh
EVOVS_PYTHON=scientific/.venv/bin/python \
EVOVS_DATA_ROOT=$PWD/scientific/.artifacts \
EVOVS_GPU=2 scripts/dsh-superagent start
```

## 目录

```
├── src/                 上游 TypeScript + src/sources/local.ts、src/research/（工具注册与 job runner）
├── scientific/          Python 科研环境：data / chemistry / modeling / evaluation / screening / experience
├── evolution/           【新增】RSI 闭环：trace_export、spec 校验、shadow 重放、失败聚类、候选 spec
├── protected/           锁定测试标签（700/600），仅 evaluation.locked 可读
├── ops/                 运维脚本（远程控制、推送、金丝雀、语料同步、经验记录）
├── docs/                上游 001-008 + 本项目审计/架构/日志/阻塞/阶段报告
├── prompts/ skills/ scripts/ tests/ examples/ locale/   上游原样
├── reference/           【gitignored】HarnessPro 只读参考
└── logs/                【gitignored】运行日志
```

## 必读文档

| 文档 | 内容 |
|---|---|
| `docs/PHASE5_REPORT.md` | **最新阶段报告**：IC50 双端点、descv2 裁决、语料与失败聚类基线、未完成项 |
| `docs/PHASE4_REPORT.md` | 自修改闭环：影子评估、candidate1 真实晋升、candidate2 拒绝、评测器垫片 |
| `docs/PHASE4_DESIGN.md` | Intake/Evaluator 循环与晋升门禁（预注册口径） |
| `docs/PHASE3_REPORT.md` | KOR/DRD2、三靶点矩阵、§12 跨靶点迁移实验 |
| `docs/PHASE2_REPORT.md` | 数据质量门禁、测试隔离、MOR 全链 |
| `docs/PHASE1_REPORT.md` | 科研 job 执行与工件契约 |
| `docs/PHASE0_REPORT.md` | 上游审计与 Gate 0（蓝图 §21 格式） |
| `docs/UPSTREAM_AUDIT.md` | 上游真实接口、版本、构建与测试证据 |
| `docs/ARCHITECTURE.md` | 分层、三类修改面隔离、计划新增模块 |
| `docs/BLOCKERS.md` | B-001…B-007 阻塞与处置（B-005 已由迁机解决） |
| `docs/DATA_SNAPSHOT.md` | ChEMBL_37 快照与归一化审计 |
| `docs/TRANSFER_DESIGN.md` | §12 迁移实验预注册口径（负迁移判定、聚类 bootstrap） |
| `docs/EVALUATOR_TRIGGER_DESIGN.md` | 锁定评测触发三案与垫片等价能力说明 |
| `docs/LOCAL_SOURCE.md` | 本地任务文件 Source 的格式与已验证行为 |
| `AGENTS.md` / `UPSTREAM.md` | 开发规则 / 基线 SHA 与合并策略 |

## 边界（不可违反）

1. 本机只编辑，所有执行在内网 GPU 服务器；
2. 单卡，只用空闲卡，不碰他人进程与项目；
3. 任务工作区 / 可进化 Harness / 受保护信任根三者物理隔离；
4. 不训练 Meta-Policy，不改基础 LLM 权重；下游 QSAR/DTI/DTA 训练属科研任务，允许；
5. 候选永不直接改 `src/`/`lib/`，晋升必须经 operator 人工裁决。

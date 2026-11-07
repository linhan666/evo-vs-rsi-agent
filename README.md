# EvoVS-RSI

面向跨靶点药物虚拟筛选的自主 Agent Harness 与递归自进化（RSI）系统。

> **本项目的本体不是"自动选择最优 QSAR 模型"，而是"让通用科研 Agent Harness 在持续执行不同靶点任务时，对自身完成科研任务的运行机制进行证据驱动、可验证、可回滚的递归改进"。**
> —— 蓝图 §23 最终一句话

- 设计蓝图：`EvoVS_RSI_Harness_Codex_Blueprint.md`（v0.1.0，2026-11-05）
- 代码基底：`deepseek-ai/dsh-superagent-prototype`（MIT，研究原型）
- RSI 机制参考：`pzs19/HarnessPro`（仅参考，不替代基底）
- 当前阶段：**Phase 7 — 九靶点顺序协议的四臂对照（进行中）**
- 状态（2026-11-08 03:20 实测）：**R 臂 9/9 完成；A 臂 7/9 进行中；M、W 两臂待跑。**
  Harness 侧 Phase 0–5 的 Gate 全部通过，自我修改闭环已跑通真实"候选→影子→晋升→生产冒烟"，并三次用预注册规则拒绝了不该上线的候选（v6 `特征形状预检` 为当前 active 版本）。

## Phase 7：九靶点顺序协议

**协议**：9 个 GPCR/酶靶点按活性数据量排序，**逐靶点串行**跑完再进下一个；每个臂单独清库后从头积累经验。
四臂 = W（固定工作流，无 agent）/ A（agent，无经验库）/ M（agent + 经验库）/ R（agent + 经验库 + 自我修改）。

**为什么要顺序跑**：经验迁移的前提是"第 N+1 个靶点开始时第 N 个的经验已经落库"。并行跑会摧毁这个前提。

### 已实测的关键结果（R 臂 9/9 + A 臂 7/9）

| 发现 | 证据 |
|---|---|
| **记忆把"探索广度"从"数据规模"上解耦** | R 臂作业数与样本数 ρ=0.03（p=0.94，n=9）；A 臂 ρ=0.90 |
| **记忆省成本但降质量** | 配对 5 个靶点：A 平均 AUROC **+0.039**（4 胜 1 负），代价是 3–15 倍墙钟 |
| **固定预算下 R 仍然落后** | 同样 64 个作业：A 0.951 vs R 0.925；同样 8 个作业：0.906 vs 0.899 —— 差距随预算**扩大**，不是"R 只是停得早" |
| **"冷启动更贵"不成立** | R 三次冷启动 2255/1147/406 s，跨 5.6 倍；与热靶点比 1.51×，置换检验 p=0.200 |
| **成本-质量前沿面积** | A 0.834 vs R 0.416（log10(作业数) 为横轴的梯形积分） |

> **当前最重要的负面结论**：R 臂的策略在 5/9 个靶点上**任何预算下都没达到过** A 臂的终态质量。
> 也就是说瓶颈不是预算，而是**记忆先验把搜索收窄导致的过早收敛**。这是下一轮要改的地方。

### 复现口径（重要）

- 只统计 **scaffold 切分**的模型；`final`/`refit` 重训模型的 `metrics.json` 是**在样本**指标（D2 上 AUROC=1.0），必须排除。
- 经验传递只传 scaffold 切分的最佳配置；随机切分会让近重复骨架跨集泄漏、AUROC 虚高。
- 靶点顺序与数据量高度共线，**"沿序列成本下降"不能直接解读为学习**（A 臂 ρ=−1.0 就是纯粹的规模效应）。


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
| Phase 6 | P6 | 三靶点（MOR/KOR/DRD2）四组对照初版：W 固定工作流 ×3 重复、M/R agent 对照 | ✅ 完成（`phase6/w/` 9 条记录） |
| **Phase 7** | P7 | **九靶点顺序协议四臂对照**；经验库读写链路修复；成本-质量前沿分析 | 🔄 **进行中**（R 9/9、A 7/9、M/W 待跑） |

## 关键事实（实测，非推测）

| 项 | 值 |
|---|---|
| 上游 commit | `8c32a9dc5d72c033816c6a8110b37f40cf94fba4` |
| DSH runtime | `@deepseek-ai/dsh@0.2.1-rc.5` |
| Node / pnpm | v22.23.4 / 11.7.0（用户态 `~/software`） |
| 运行主机 | **172.25.16.37**（8×H100 / 128 核；`172.25.18.26` 为迁移前存档） |
| `pnpm typecheck` | PASS |
| `pnpm test` | **60/61 文件、1216/1217 用例**；唯一失败为 B-002（上游 Feishu 竞态，非主链路） |
| Agent 工具面 | R/M 组 **5 个**：`rdkit.featurize` / `ml.train` / `screening.rank` / `experience.retrieve` / `evaluation.locked`；**A 组只有 4 个**（`EVOVS_GROUP=fixed` 摘掉 `experience.retrieve`） |
| 锁定测试 AUROC（Ki，xgboost） | MOR **0.9339** / KOR **0.8685** / DRD2 **0.9015**（test n=491/334/580） |
| 锁定测试 AUROC（IC50 独立通道） | MOR **0.9188** / KOR **0.8954** / DRD2 **0.9157**（test n=99/159/63） |
| 筛选库 | ZINC250k 规范化去重 → 种子 17 抽样 **100,000**（`library_100k.smi`） |
| Evolution 语料 / 经验库 | **20 traces**；Phase 6 的 29 条经验已归档为 `experience_phase6_archive_20261107.json`，Phase 7 R 臂重新积累了 **18 条**（9 靶点 × dataset/model） |
| 已晋升候选 | **v6**（active，特征形状预检）+ 前序 v1–v5：并行特征化、列名别名解析、路径解析、manifest 布局；每次晋升都绑定 git SHA 与回滚方案 |
| 版本账本 | `evolution/versions.json`：v2 active、v1 superseded，均绑 git SHA；`versions.py check` 用祖先判定 |
| 被拒绝候选 | candidate2（pooled 重校准，负迁移恶化至 −0.0614）；candidate3（descv2，Ki 三条 CI 全含 0；IC50 通道 Δ +0.0035/+0.0037/−0.0011，同为持平 → 保持 v1）；**auto-latency-share-screening-rank**（首个自动提案，实测更慢：10k 行 9.0s → 21.5s） |

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

**跑实验臂时还要设三项**（`EVOVS_GROUP` 决定经验工具是否可见，`EVOVS_USAGE_LOG` 是 token 台账，
`env.sh` 会自动挂 `NODE_OPTIONS=--require ops/usage_hook.cjs`，缺了就没有 token 数据）：

```sh
. ./env.sh
export EVOVS_GROUP=rsi          # rsi | memory | fixed
export EVOVS_USAGE_LOG=$PWD/scientific/.artifacts/usage_seq_r.jsonl
```

> ⚠️ `EVOVS_GROUP` 不在 tmux 的 `update-environment` 列表里。切换分组时必须让 tmux server
> 完全退出（`tmux ls` 报 "no server running"）后再 `start`，否则新 session 会**静默沿用上一组的配置**。
> 重启后务必用 `/proc/<node pid>/environ` 核实。

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
| `HANDOFF.md` | **当前状态与下一步**：四臂进度、切换服务的操作步骤与风险点、已修复的 harness 缺陷清单 |
| `ops/phase7_design.md` | Phase 7 顺序实验设计（两个比较、宏观/微观指标、经验 schema） |
| `ops/phase7_runs/analysis.md` | 初步统计分析：描述统计、置换检验、序列趋势、成本-质量相关、统计功效 |
| `ops/phase7_runs/frontier.md` | **两个正式比较**：固定预算下的质量、达到同一质量所需成本、前沿面积 |
| `docs/PHASE5_REPORT.md` | IC50 双端点、descv2 裁决、语料与失败聚类基线、未完成项 |
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

## Phase 7 运维脚本

| 脚本 | 用途 |
|---|---|
| `ops/phase7_seq.py` | **顺序驱动器**：幂等可断点续跑，只在上一靶点到达终态后才投下一个；自动写经验记录（dataset + model 两类）并采集宏观指标 |
| `ops/phase7_texts.py` | 批量重写任务文本：给经验库绝对路径、A 组改为"无经验库"措辞、修 `/n` 笔误 |
| `ops/phase7_workflow.py` | **W 臂固定工作流**：9 靶点 split→featurize→train→screen，不经过 agent |
| `ops/phase7_analysis.py` | 初步统计：描述统计、精确置换检验、序列趋势、成本-质量相关、统计功效 |
| `ops/phase7_frontier.py` | **两个正式比较**：固定预算下的质量曲线、等质量成本（含删失处理）、前沿面积 |
| `ops/code_metrics.py` | 微观代码指标：特征化种类、模型族、分割策略、失败→首成耗时 |
| `ops/usage_session_audit.py` | 从 DSH 会话转录反推 token，并与 ledger 校准口径（`ledger/transcript ≈ 1.156`） |
| `ops/rctl.py` | 远程控制（SOCKS5 + 代理）；`exec` / `put` / `putdir` / `get` |

## 边界（不可违反）

1. 本机只编辑，所有执行在内网 GPU 服务器；
2. 单卡，只用空闲卡，不碰他人进程与项目；
3. 任务工作区 / 可进化 Harness / 受保护信任根三者物理隔离；
4. 不训练 Meta-Policy，不改基础 LLM 权重；下游 QSAR/DTI/DTA 训练属科研任务，允许；
5. 候选永不直接改 `src/`/`lib/`，晋升必须经 operator 人工裁决。

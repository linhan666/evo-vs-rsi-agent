# RSI 药物筛选 Agent Harness — 新会话交接文档

> **项目根目录**：`D:\RSI_AutoML`（Windows 本地）+ 远程服务器 `172.25.16.37`（`linhan_cluster`）
> **Git 仓库**：`/home/linhan_cluster/evo_vs_rsi`（远程），HEAD = `5967302`
> **交接时间**：2026-11-07 21:20

---

## 一、项目目标（用户原话）

> 给定一个新靶点及其活性数据集，系统能否利用历史靶点的建模经验，以更少的计算开销、更少的人工干预，自动构建具有可靠虚拟筛选性能的靶点特异性预测模型，并持续改进这一过程。

**RSI 不只是药物筛选 harness，同时是代码编写 harness。** 微观优势 = 代码复用（特征编码参数、模型选择、分割策略等）。

---

## 二、实验设计（Phase 7）

### 双重比较

| 维度 | 问题 | 指标 |
|---|---|---|
| **预算效率** | 达到最优性能时 RSI 省多少预算？ | 时间/tokens/作业数 → 同 AUROC 下的成本 |
| **固定预算质量** | 同预算下 RSI 是否得到更优模型？ | 同成本下的 AUROC/AUPRC/EF@1% |

### 宏观 + 微观双层指标

| 层 | 指标 | 工具 |
|---|---|---|
| **宏观** | 模型数 / 作业数 / 墙钟 / tokens | `ops/phase7_seq.py` 采集 |
| **微观-内容** | 特征编码参数 / 模型选择 / 分割策略 / 超参 | `ops/code_metrics.py` |
| **微观-效率** | 代码行数 / 失败→首成耗时 / 经验复用率 | `ops/code_metrics.py` |

### 四组

| 组 | `EVOVS_GROUP` | 配置 | 变量 |
|---|---|---|---|
| **W** | 无（不走 agent） | 固定工作流 `ops/phase7_workflow.py` | baseline |
| **A** | `fixed` | Agent（无经验库，工具被隐藏） | 自主性 |
| **M** | `memory` | Agent + 经验库 | +记忆 |
| **R** | `rsi` | Agent + 经验库 + 自我修改 | +自我改进 |

### 9 个靶点（顺序编号即任务文本里的 `target #N`）

| # | slug | 简称 | 样本 | 阳性率 | 类型 |
|---|---|---|---|---|---|
| 1 | d(2)_dopamine_recept | D2 | 6811 | 96.2% | GPCR |
| 2 | 5-hydroxytryptamine_ | 5HT | 4828 | 98.0% | GPCR |
| 3 | adenosine_receptor_a | ADR | 3376 | 95.9% | GPCR |
| 4 | drd2 | DRD2 | 3293 | 66.6% | GPCR |
| 5 | oprm1 | MOR | 2790 | 79.5% | GPCR |
| 6 | cannabinoid_receptor | CBR | 2309 | 98.2% | GPCR |
| 7 | oprk1 | KOR | 1899 | 79.0% | GPCR |
| 8 | carbonic_anhydrase_2 | CA2 | 7301 | 92.9% | 酶 |
| 9 | prothrombin | PT | 2824 | 80.7% | 酶 |

---

## 三之一、无人值守链（2026-11-08 05:00 启动）

`ops/p7b_run_all.sh` 已在 tmux `p7b-all` 里运行，日志 `ops/p7b_runs/orchestrator.log`。

| 阶段 | 内容 | 失败处理 |
|---|---|---|
| 0 | 等 round-7 的 M 驱动器退出 + 工单清零 | 60 min 后仍未清零则 abort |
| 1 | `p7b_patch.py --include-ts` → `pnpm typecheck` → `pnpm build` | 任一步失败立即 abort |
| 2 | 依次跑 **R(rsi) → M(memory) → A(fixed) → W(无 agent)** | 每次重启校验 `/proc/<pid>/environ` 的 `EVOVS_GROUP` 与 usage hook，不符即 abort；每臂结束校验工单清零 |
| 3 | `analysis --round p7b` / `locked --round p7b` / `cv_repeat --batch --round p7b` | 单份失败只记录，不阻断其余 |

**为什么每次重启都要硬校验**：`EVOVS_GROUP` 不在 tmux 的 `update-environment` 列表里。若 tmux server 没死透，新会话会**静默沿用上一组的配置**——那就会用错的臂跑完 9 个靶点，事后无法补救。

**手动接管**：
```bash
tmux kill-session -t p7b-all     # 停编排器（当前臂的驱动器不受影响）
tmux kill-session -t p7b-rsi     # 停某个臂的驱动器
tail -f ops/p7b_runs/orchestrator.log
```

### 启动前预先排除的两个问题

1. **`pnpm typecheck` 其实一直是失败的**（README 声称 PASS 已过时）：`screening.rank` 的 argv 引用 `args.desc_set`，但 `RankInput` 从未声明该字段。运行时因为 `undefined` 被丢弃而侥幸可用，predict 走默认 v1。已在 `p7b_patch.py` 补上声明，typecheck 现通过。
2. **补丁脚本破坏了 CRLF**：`registry.ts` 是 CRLF，用默认 `read_text/write_text` 往返会把整个文件改成 LF，一行改动变成 318 行 diff。已改用 `newline=""`，现在 diff 只有 2 行。

## 三、当前实验状态（2026-11-08 00:15）

### 正在运行：M 组 #2–#9

2026-11-08 03:46 切 `EVOVS_GROUP=memory`（PID 1596279，已核实），经验库为空（A 组不写记录）。
驱动器 tmux `phase7-seq-m`，日志 `ops/phase7_runs/seq_m.log`。

- **M#1（D2）已完成**：3472 s / 34 作业 / 18 模型 / **2.04 M token** / AUROC 0.9675
  （对比 R 冷启动 1147 s / 64 作业 / 4.31 M / 0.9218；A#1 3778 s / 101 作业 / 10.13 M / 0.9784）
- 经验库已积累 2 条（`dataset_D2_001`、`model_D2_002`）

### phase7b 重设计：数据层已就绪（2026-11-08 04:50）

**诊断**（本轮新增的两个硬事实）：

1. `data.split --strategy scaffold` 的**验证集与 `--seed` 完全无关**（种 17/23/42/7/2024 下 100% 重叠）。
   真正改变验证集的是 `test_fraction`：R 用 0.2、A 用 0.3 → **两臂 DRD2 验证集重叠为 0**。
   所以「固定验证集」要固定的是**比例**，固定种子是无效的。
2. 5 折分组 CV 是更好的估计器。MOR 三方对照：

| 估计器 | R | A | 差（R−A） | 与锁定排序 |
|---|---|---|---|---|
| 单次切分（各自） | 0.9196 | 0.9089 | **+0.0107** | ❌ 相反 |
| **5 折分组 CV** | 0.9278 | 0.9293 | **−0.0015** | ✅ |
| 锁定测试集 | 0.9375 | 0.9386 | −0.0011 | 基准 |

折间 sd ≈ **0.015**，是单个 10% 切片的抽样噪声，比两臂真实差异 0.001 大一个数量级。

**已完成的准备**（`ops/phase7b_prepare.py`，非破坏性，原 `dataset.csv` 不动）：

| 产物 | 位置 | 说明 |
|---|---|---|
| 6 个新受保护测试集 | `protected/chembl37_ki_<slug>/final_test_Ki.csv` | 按整组骨架挖 15%，600 权限，已 gitignore |
| 去泄漏训练池 | `scientific/.artifacts/chembl/<slug>/ki/dataset_p7b.csv` | 实测每个靶点泄漏均为 0 |
| 冻结切分清单 | `.../ki/splits/frozen_<slug>.json` | 9 靶点齐备，train/val/test 全按骨架分 |

冒烟测试（D2）：featurize 5789 行，train 4950 / val 579 与清单完全一致，AUROC 0.9496。

> 切分用**固定种子的随机骨架抽样**，不用 harness 现有的「最大骨架优先」——后者正是验证集与 seed 无关且系统性偏难的原因。

**phase7b 已完成的准备**（截至 05:00）：

| 步骤 | 状态 |
|---|---|
| 6 个新受保护测试集 | ✅ 目录已规范命名为 `chembl37_ki_{d2,5ht,adr,cbr,ca2,pt}` |
| `evaluation/locked.py` 的 `CHANNELS["Ki"]` | ✅ 已扩到 9 个靶点，`--target {MOR,KOR,DRD2,D2,5HT,ADR,CBR,CA2,PT}` 验证通过 |
| 27 份任务文本（3 臂 × 9 靶点） | ✅ `ops/phase7b_custom/`，task_id 与驱动器 `ORDER` 对齐（校验 0 缺失） |
| 驱动器 `--prefix` / `--tasks-dir` / `--store` | ✅ 支持新一轮而不改代码 |
| `registry.ts` 的 `LockedInput.target` 枚举 | ⬜ **待做**（需 `pnpm build` + 重启，不能在有工单时做） |
| W 臂新协议脚本 | ⬜ 待做（用户已确认要重跑） |

**phase7b 部署顺序**（等 M 跑完）：
1. `scientific/.venv/bin/python ops/p7b_patch.py --include-ts`
2. `pnpm build`（typecheck 必须过）
3. 停服务 → 确认 `tmux ls` 无 server → 起服务（相应分组）
4. 驱动器：`python3 ops/phase7_seq.py --group r --prefix p7b --tasks-dir ops/phase7b_custom --store .../experience_r.json --label p7b`

> ⚠️ phase7b 的运行记录文件名会带 `_p7b` 后缀（`r_01_d2_p7b.json`），与旧轮的 `r_01_d2.json` 并存。
> 分析脚本目前按 `[ramw]_\d\d_*` glob，会把两轮混在一起——**必须先加轮次过滤再用**。


### 正在运行：M 组 #1–#9（旧协议）

2026-11-08 03:46 切 `EVOVS_GROUP=memory`（PID 1596279，已核实），经验库为空（A 组不写记录）。
驱动器 tmux `phase7-seq-m`，日志 `ops/phase7_runs/seq_m.log`。A 组已在 03:31 全部完成。

### A 组已完成 9/9（2026-11-08 03:31）

| seq | 靶点 | 墙钟 s | 作业 | 模型 | token | AUROC（自选验证集） | EF@1% |
|---|---|---|---|---|---|---|---|
| 1 | D2 | 3778 | 101 | 53 | 10.13 M（估） | 0.9784 | 1.019 |
| 2 | 5HT | 4017 | 78 | 38 | 8.84 M | 0.9756 | 1.014 |
| 3 | ADR | 1096 | 86 | 50 | 5.07 M | 0.9506 | 1.040 |
| 4 | DRD2 | 648 | 32 | 18 | 1.75 M | 0.9452 | 1.645 |
| 5 | MOR | 236 | 14 | 8 | 0.87 M | 0.9089 | 1.229 |
| 6 | CBR | 1252 | 93 | 36 | 8.66 M | 0.9402 | 1.007 |
| 7 | KOR | 267 | 24 | 13 | 1.22 M | 0.9456 | 1.235 |
| 8 | CA2 | 2120 | 23 | 10 | 1.38 M | 0.9885 | 1.031 |
| 9 | PT | 1103 | 71 | 46 | 3.94 M | 0.9576 | 1.047 |

合计 **14517 s = 242 min / 522 作业 / ~33 M token**。

### ⚠️ 重大更正：跨臂「质量差」是测量假象

**此前所有跨臂 AUROC 比较都无效**。每张工单自选 scaffold 验证集，不同臂的 AUROC 不在同一批分子上。DRD2 上同一对臂：

| 指标 | R | A | 差 |
|---|---|---|---|
| 自选验证集 AUROC | 0.8649 | 0.9452 | −0.080（A 领先） |
| **锁定测试集 AUROC** | **0.9327** | **0.9206** | **+0.012（R 领先）** |

同一对模型，两种标尺给出**方向相反**的结论。原因是验证集只有 300–700 分子，跨切分种子的方差足以重排两臂。

**用锁定测试集重算（唯一合法标尺，`ops/phase7_locked.py`）**：

| 靶点 | R | A | 差（R−A） |
|---|---|---|---|
| DRD2 | 0.9327 | 0.9206 | **+0.0121** |
| KOR | 0.9100 | 0.9100 | 0.0000 |
| MOR | 0.9375 | 0.9386 | −0.0011 |
| **均值** | | | **+0.0037** |

→ **R 与 A 在质量上不可区分**。此前说的「A 平均 +0.039」必须撤回。

KOR 那对两臂的模型 `sha256` **完全相同**（同切分清单、同特征文件、同 seed、同算法），所以锁定指标一致是真实收敛，不是缓存 bug。

**仍然成立的结论只有成本**：A 是 R 的 3–15 倍墙钟、2–9 倍 token。

### 由此暴露的三个真问题（按严重度）

1. **9 个靶点里只有 3 个有受保护测试集**。`evaluation.locked` 的 target 是硬枚举 `['MOR','KOR','DRD2']`，其余 6 个靶点的跨臂质量比较**在方法上不成立**。这是实验设计的缺口，不是 RSI 的缺陷。
2. **固定预算比较同样失效**：`phase7_frontier.py` 的前沿用的是验证 AUROC，需重建在锁定指标上。
3. **记忆锚定导致搜索变窄**（真实存在）：4/9 靶点只用 1 种特征化。但现有证据不足以说明它损害了质量。

### 第 3 个 D2 冷启动复现（已完成，2026-11-08 01:34）

因为 A 组占着服务，做这个复现需要临时切回 `rsi` 两次。流程：停 A 驱动器 → 等 A#2 完成 → 切 rsi → 跑复现 → 切回 fixed → 恢复 A 链（`--from adr`）。

```
python3 ops/phase7_seq.py --group r --only d2 \
  --task-id seq_r_d2_coldstart2 --label coldstart2 --no-record
```

D2 现在有 4 次观测：

| 观测 | 墙钟 s | 作业 | 模型 | token | AUROC |
|---|---|---|---|---|---|
| R#1 原始（坏 harness） | 2255 | 36 | 16 | 1.87 M | 0.9511 |
| R 冷启动复现 1 | 1147 | 64 | 34 | 4.31 M | 0.9218 |
| **R 冷启动复现 2** | **406** | **16** | **7** | **1.19 M** | **0.9597** |
| A#1 | 3778 | 101 | 53 | 10.13 M（估） | 0.9784 |

> ⚠️ **这个复现推翻了「冷启动更贵」的结论**：R 臂三次冷启动跨越 **5.6 倍**（2255 / 1147 / 406 s），其中 406 s 那次比多数热靶点（中位 513 s）还便宜。取两次 clean 复现均值 776.8 s 对热靶点 513 s 只有 **1.51×**，置换检验 **p = 0.200 不显著**（n=2 vs 8，最小可达 p = 0.022，说明不是组数问题，是差异本身太弱）。
>
> 功效重算：log 尺度合并 sd = 0.611、效应 1.51× → **每组需 n ≈ 35**，不可行。
>
> 所以：**Phase 7 的稳健信号是「A vs R 的臂间差」，而不是「R 臂内的边际成本递减曲线」**。后者在数据上不成立，不要在论文里主张。

### R 组 9/9 已完成 ✅

### A#1 的 token 是「估算」不是「缺失」（口径已校准）

原因：`ops/usage_hook.cjs` 靠 `NODE_OPTIONS=--require` 挂载，而 `env.sh` 里**没有**这一行。R 组是上一会话手工 export 的，我切 A 组时漏了，导致 A#1 全程没有 ledger。

**但我先前说"永久缺失"是错的**：DSH 会话记录（`~/.dsh/sessions/<workdir>/worker-*/session.v4.jsonl.zstd`）里每条 assistant 消息都带 `usage` 块（`inputTokens`/`cacheReadTokens`/`cacheWriteTokens`/`outputTokens`/`totalTokens`），可以直接反推。

已写 `ops/usage_session_audit.py` 做口径校准：在 10 个既有 ledger 又有会话的 R 工单上比对，`ledger / transcript` 比值 **均值 1.1555（范围 1.0416–1.3320）**。据此

- A#1 会话原始合计 **8,765,069**（82 次调用）
- 换算 **≈ 10,128,037**，区间 **[9,129,695, 11,675,071]**
- 落在 `ops/phase7_runs/a_01_d2.tokens_estimated.json`，标注为 estimated

所以**不需要为 token 重跑 A#1**。

已修：把挂载逻辑写进 `env.sh`（幂等、带存在性判据），现在任何一次 `. ./env.sh` 都会自动设置。验证：PID 1016961 的 `NODE_OPTIONS` 含 `--require`，`usage_seq_a.jsonl` 首行有 `hook-installed`，A#2 的 ledger 正常增长。

### A 组为什么这么慢（预期 7–10 h）

A 臂**没有记忆**，所以不存在「后续靶点变快」的机制——每个靶点都要从零走一遍冷启动。A#1 实测 63 min，8 个后续靶点按 55–70 min 估，**还需 7.5–9.5 h**。

对照 R 臂：R#1（冷启动）19.5 min，R#2–#9 均值 8 min，因为经验让 agent 直接收敛。A 不会出现这个下降——**这个差别本身就是实验结论的一部分**。

进度校准：A#2（5HT）开工 7 分钟已 29 作业、ledger 1.39 M token，已超过 R 整个 5HT 工单的 1.11 M。

### A 组服务切换记录（2026-11-07 23:08 / 00:16 两次）

| 项 | 值 |
|---|---|
| 切换前预检 | 0 未完成工单 / 无运行中的科学作业 / inbox 空 |
| R 组经验库 | 归档 `experience_group_r_archive.json`（33 KB，18 条） |
| 服务进程 | 第一次 PID 835346；重启后 PID 1016961（均核实 `EVOVS_GROUP=fixed`） |
| A 组 usage | `scientific/.artifacts/usage_seq_a.jsonl` |
| 切换验证 | A#1 **零次** `experience.retrieve` 调用 |

> ⚠️ **重启经验（重要）**：`scripts/dsh-superagent stop` 后 tmux server 会因为没有会话而退出，`start` 时新建的 server 才继承当前 shell 的 `EVOVS_*`。若 tmux server 还活着，新 session 的 pane **拿不到** `EVOVS_GROUP`（不在 tmux 的 `update-environment` 列表里），会静默沿用上一组配置。重启前必须确认 `tmux ls` 报 "no server running"，重启后用 `/proc/<node pid>/environ` 核实。

### R 组 9/9 已完成 ✅

驱动器已退出（`sequence complete`）。总耗时 **103.5 min / 228 作业 / 373 次 LLM 调用 / 1680 万 token**。

**主表（#1 用干净冷启动复现，见下）**

| seq | 靶点 | 墙钟 s | 作业 | 模型 | tokens | scaffold AUROC | EF@1% |
|---|---|---|---|---|---|---|---|
| 1 | D2（冷启动复现） | 1147 | **64** | 34 | 4,308,194 | 0.9218 | 1.019 |
| 2 | 5HT | **268** | 16 | 7 | 1,110,329 | 0.9184 | 1.010 |
| 3 | ADR | 566 | 24 | 9 | 2,345,234 | 0.9380 | 1.040 |
| 4 | DRD2 | 471 | 31 | 16 | 1,622,079 | 0.8649 | 1.509 |
| 5 | MOR | 406 | 27 | 15 | 1,929,021 | 0.9196 | 1.341 |
| 6 | CBR | 580 | 33 | 14 | 2,858,619 | 0.8235 | 1.007 |
| 7 | KOR | **214** | **12** | 4 | 1,085,645 | 0.9431 | 1.235 |
| 8 | CA2 | 891 | 16 | 5 | 908,137 | **0.9885** | 1.031 |
| 9 | PT | 555 | 33 | 11 | 3,079,259 | 0.9031 | 1.124 |

**边际成本是「阶跃」不是「渐进下降」**：#1 是陡峰（64 作业 / 4.31 M token / 1147 s），#2–#9 落在 **12–33 作业 / 0.91–3.08 M token / 214–891 s**。相对冷启动，#2–#9 均值作业 −62%、token −54%、墙钟 −57%。之后就在这个平台上下波动，**没有继续下降**。

### 冷启动复现（方案 B，已完成）

因为 R#1 跑在未修复的 harness 上，用当前 harness 重跑了一次 D2 作为干净原点：

```
tmux session phase7-coldstart
python3 ops/phase7_seq.py --group r --only d2 \
  --task-id seq_r_d2_coldstart --label coldstart --no-record
```

- 独立记录：`ops/phase7_runs/r_01_d2_coldstart.json` + `r_d2_coldstart.code.json`，**未覆盖** `r_01_d2.json`，经验谱系 18 条未变
- 空复现库：`scientific/.artifacts/experience/replay_coldstart.json`（内容 `[]`），不污染主库
- **只发 1 次检索**（R#1 是 5 次），确认修复生效

| 指标 | R#1（坏 harness） | 冷启动复现（好 harness） |
|---|---|---|
| 墙钟 | 2255 s | **1147 s** |
| 作业 | 36 | **64** |
| 失败 | 2 | 7 |
| 模型 | 16 | 34 |
| LLM 调用 | 40 | 64 |
| tokens | 1.87 M | **4.31 M** |
| scaffold AUROC | 0.9511 | 0.9218 |

**关键解读**：坏 harness 的 catboost（单次 ~28 min）**压住了探索预算**，agent 只在 36 个作业里收敛；修好后作业变小变快，agent 把省下的时间花在更多探索上（14 次特征化 vs 5 次、34 次训练、用了 `ml.fuse`、2 次 `evaluation.locked` 打锁定测试集）。所以墙钟减半但作业/token 翻倍，**模型反而略差**。

> 结论：单靶点单次运行的方差极大（D2 冷启动：1147–2255 s、36–64 作业、1.9–4.3 M token）。任何「R 组内部逐靶点趋势」都不足以支撑结论，必须靠 A/M 对照。且 R#1 原始那次的 0.9511 高于复现，说明那次是**有利抽样**。

### 微观复用证据（这才是 RSI 的强信号）

| 靶点 | 作业 | 失败 | 特征化种类 | 采用的特征化 |
|---|---|---|---|---|
| D2 #1 | 36 | 2 | **5** | r2/256, r2/1024, r2/2048, r2/4096, r3/4096 |
| 5HT #2 | 16 | 0 | **1** | 仅 r2/2048 |
| ADR #3 | 24 | 0 | **1** | 仅 r2/2048 |
| DRD2 #4 | 31 | 0 | 4 | 扩到 v2 + r2/4096 + r3/2048 |
| MOR #5 | 27 | 1 | 4 | 同上 |
| CBR #6 | 33 | 2 | 3 | 扩到 v2 + r3/2048 |
| KOR #7 | 12 | 0 | **1** | 仅 r2/2048 |
| CA2 #8 | 16 | 1 | **1** | 仅 r2/2048 |
| PT #9 | 33 | — | — | — |

- **7 个后续靶点里有 4 个（5HT/ADR/KOR/CA2）只用了 1 种特征化**，即逐字复用了 D2 经验里的 `r2/2048/v1`
- 另外 3 个（DRD2/MOR/CBR）扩到了 `desc_set v2` 和更大半径——恰恰是 scaffold AUROC 最低的三个（0.865 / 0.920 / 0.824），说明 agent 是**在经验不够用时才扩展**，不是盲目照抄
- 失败率从 D2 的 5.6% 降到整体 3.1%

### 经验库当前谱系（18 条 = 9 靶点 × 2）

```
1 D2    xgboost scaffold r2/2048/v1  AUROC 0.9511 EF 1.024
2 5HT   logreg  scaffold r2/2048/v1  AUROC 0.9184 EF 1.010
3 ADR   rf      scaffold             AUROC 0.9380 EF 1.040
4 DRD2  catboost scaffold            AUROC 0.8649 EF 1.509
5 MOR   rf      scaffold             AUROC 0.9196 EF 1.341
6 CBR   rf      scaffold r2/2048/v2  AUROC 0.8235 EF 1.007
7 KOR   xgboost scaffold             AUROC 0.9431 EF 1.235
8 CA2   rf      scaffold             AUROC 0.9885 EF 1.031
9 PT    rf      scaffold r2/2048/v1  AUROC 0.9031 EF 1.124
```

### 待执行

- **A 组 #1–9**：正在跑（驱动器自动串）
- **M 组 #1–9**：等 A 组完成后，切 `EVOVS_GROUP=memory` + `usage_seq_m.jsonl`，`--group m`（M 组**需要**清库后重新积累，不要继承 R 组的库）
- **W 组 9 靶点**：`ops/phase7_workflow.py --all`，不需要服务；必须在没有 agent 作业时跑（否则墙钟被 CPU 争用污染）。可以等 A/M 都跑完之后再跑

---

## 四、本轮修复的 harness 缺陷（重要，写论文时要声明）

Phase 7 首次启动时，**记忆机制在读写两端都是坏的**，R/M 组会和 A 组无差别。已修：

| # | 缺陷 | 后果 | 修复 |
|---|---|---|---|
| 1 | 任务文本没给经验库路径，`experience.retrieve` 的 `store` 是必填参数，**路径错会静默返回 0 条** | R#1 猜了 5 次路径（`experience/store.json` 等），全部空 | `ops/phase7_texts.py` 把绝对路径写进 Constraints |
| 2 | **没有任何写入口**：registry 只有 `experience.retrieve`，无 `record` 工具，也无自动记账 | R#2–9 永远检索空库 | `ops/phase7_seq.py` 在每靶点完成后自动写 2 条记录（dataset + model） |
| 3 | 经验库未按设计文档"每组清库"，带着 Phase 6 的 29 条 | 序列内部条件不一致 | 归档为 `experience_phase6_archive_20261107.json` |
| 4 | `ops/code_metrics.py` 少 `import sys` | 一跑就 `NameError` | 补 import |
| 5 | `code_metrics.py` 对 argv 里的 `None` 调 `.startswith` | 已完成的靶点跑不出指标 | 加 `isinstance(item, str)` |
| 6 | A 组文本要求调 `experience.retrieve`，但 `fixed` 组该工具被隐藏 | A 组白撞错误、污染成本基线 | A 组文本改为"本臂无经验库" |
| 7 | 驱动器重启会**重复记账**（同一靶点再写一遍） | 后续靶点检索到重复/矛盾记录 | `already_recorded()` 按 (group, seq, target, kind) 幂等跳过 |
| 8 | 切分分类过于宽松：模型没传 `--split-manifest` 时默认算作 scaffold | 5HT 把 `logreg/internal-random`（AUROC 0.9485，虚高）当成最佳经验 | 严格按 manifest 名判定，无 manifest 归 `internal` 并从排名排除 |

**记账口径**：经验记录用 **scaffold 切分**的最佳模型，不用 random 切分——随机切分会让近重复骨架跨集泄漏，AUROC 虚高，传给下一个靶点会污染整条序列。判定只能看 `ml.train` 的 `--split-manifest` 文件名：`metrics.json` 的 `split_strategy` 字段对随机切分也写 `scaffold-manifest`，不可信。

**5HT 记账修正**：第一版把 `model_probe`（logreg，internal-random，0.9485）当最佳，已删掉重记为 `model_logreg_scaffold`（0.9184）。修正前快照存 `experience_before_5ht_fix.json`。

**已知不一致**：R#1 用的是旧任务文本（无 store 路径、`/n` 笔误未修），且浪费了 5 次检索作业。R#2 起才用新文本。分析时需注明 R#1 是"无经验冷启动"，这本身符合序列第 1 个靶点的语义，但它的宏观成本含了这 5 次无效调用。

---

## 五、技术架构

### 远程服务器

- **地址**：`172.25.16.37`，用户 `linhan_cluster`
- **工作目录**：`/home/linhan_cluster/evo_vs_rsi`
- **接入**：SOCKS5 代理 `47.238.155.196:14842`（账号 lurq）
- **调用**：`D:/anaconda3/python.exe ops/rctl.py exec "..." --host 172.25.16.37`
- **传文件**：`ops/rctl.py put` / `putdir`（SFTP 不可用，走 tar 管道）
- **Git Bash 必须**：`export MSYS2_ARG_CONV_EXCL='*' MSYS_NO_PATHCONV=1`（否则远程路径被转成本地 Windows 路径，会写错位置）

### 服务管理

```bash
scripts/dsh-superagent stop; source env.sh
export EVOVS_GROUP=rsi          # rsi | memory | fixed
export EVOVS_PYTHON=$PWD/scientific/.venv/bin/python
export EVOVS_DATA_ROOT=$PWD/scientific/.artifacts
export EVOVS_MODEL=deepseek-flash
export EVOVS_USAGE_LOG=$PWD/scientific/.artifacts/usage_seq_r.jsonl   # 每组换一个
scripts/dsh-superagent start
```

### 本轮新增/修改的脚本

| 文件 | 用途 |
|---|---|
| `ops/phase7_seq.py` | **顺序驱动器**（幂等、可断点续跑），自动记账 + 采集宏观指标 |
| `ops/phase7_texts.py` | 批量重写任务文本（给 store 路径 / 改写 A 组措辞） |
| `ops/phase7_workflow.py` | **W 组固定工作流**，9 靶点，split→featurize→train→screen |
| `ops/phase7_analysis.py` | **初步统计分析**，输出 `ops/phase7_runs/analysis.md` + `.json`（描述统计、置换检验、功效、复用、每靶点明细） |
| `ops/usage_session_audit.py` | 从会话转录反推 token，并与 ledger 校准口径（ledger/transcript ≈ 1.156） |
| `ops/code_metrics.py` | 微观代码指标（已修 2 个 bug） |

### 关键路径

| 路径 | 内容 |
|---|---|
| `ops/phase7_runs/r_XX_<target>.json` | 每靶点采集记录（宏观 + model_table） |
| `ops/phase7_runs/r_XX_<target>.report.md` | agent 原始报告 |
| `ops/phase7_runs/r_<target>.code.json` | 微观代码指标 |
| `scientific/.artifacts/experience/experience.json` | 经验库（R 组当前 2 条） |
| `scientific/.artifacts/experience/payloads/` | 每条经验的可审计 payload |
| `.artifacts/state/work/<ticket>/` | 工单工作空间 |

---

## 六、RSI 自我改进机制（已验证）

```
v1 featurize 并行     superseded
v2 列名别名           superseded
v3 ml.train 列名      superseded
v4 路径解析           superseded
v5 manifest 布局      superseded (non-regression 门禁首例)
v6 特征形状预检       ACTIVE (non-regression + expected_failures)
```

门禁三种判据：等价 / non-regression / expected_failures

---

## 七、重要教训（用户纠正过的设计错误）

| 错误 | 纠正 |
|---|---|
| 把 bug fix 当 RSI 贡献 | bug fix 是工程还债，不是 harness 学习 |
| 比绝对 AUROC | 应比**边际成本递减**和**固定预算下的质量** |
| 只看宏观指标 | 还要看**微观代码指标** |
| 3 个靶点太少 | 扩展到 9–10 个 |
| 并行跑 | **顺序跑**（经验迁移的前提） |
| topK 当质量指标 | topK 是完成度，质量看 **EF@1%** |
| 忽略代码编写本身 | RSI 是**代码编写 harness** |
| 全量重训模型的在样本 AUROC 当性能 | `final_*` 必须排除（本轮新增） |
| random 切分的最佳模型当经验传递 | 传 scaffold 切分的最佳（本轮新增） |

---

## 八、下一步

### 1. ~~等 R 组跑完~~ ✅ 已完成（103.5 min，9/9）

### 2. ~~切 A 组~~ ✅ 已完成（2026-11-07 23:08，见第三节的切换记录）

### 3. 切 M 组（下一步）

和 A 组同一套流程，只需换两个值：`EVOVS_GROUP=memory`、`EVOVS_USAGE_LOG=usage_seq_m.jsonl`，驱动器用 `--group m`。

**M 组必须从空库开始积累**：把 A 组的库归档（A 组不写记录，所以 A 期间库一直是空的），确认 `experience.json` 不存在后再启动 M。

```bash
export MSYS2_ARG_CONV_EXCL='*' MSYS_NO_PATHCONV=1

# a. 确认无 open 工单（同 A 组的预检）
# b. 确认 tmux 无 server：tmux ls 应报 "no server running"
# c. stop → 确认停止 → start（换 memory + usage_seq_m.jsonl）
# d. 核实 /proc/<node pid>/environ 的 EVOVS_GROUP=memory
# e. tmux new-session -d -s phase7-seq-m ... 'phase7_seq.py --group m'
```

### 4. W 组（不需要服务，但必须在没有 agent 作业时跑，否则墙钟被 CPU 争用污染）

```bash
cd /home/linhan_cluster/evo_vs_rsi && source env.sh && \
  scientific/.venv/bin/python ops/phase7_workflow.py --all 2>&1 | tee ops/phase7_runs/seq_w.log
```

### 5. 出图与分析

- 边际成本曲线：**用 `r_01_d2_coldstart.json` 作 #1**，不要用 `r_01_d2.json`（坏 harness）
- 代码复用率：`ops/phase7_runs/r_<target>.code.json` 的 `n_featurizations` 与 `featurizations`
- 双重比较：预算效率 + 固定预算质量
- 四臂在 `sequence_index` 上对齐；W 组的 `jobs_run` 是 4（固定 DAG），与 agent 臂不可直接比作业数，要比墙钟和 AUROC

---

## 九、注意事项

1. **不要用 `/tmp`**——服务器空间受限，数据放工作目录
2. **LLM API 可能不稳定**（`LlmError: DeepSeek Messages stream ended`）
3. **任务 id 幂等**——重投相同 `task_id` 会被跳过；驱动器重试用 `_r1` 后缀
4. **工单命名**——服务用 title slugify，不是 task_id
5. **GPU0/1 被占**——只用 GPU2/3，不 kill 他人进程
6. **门禁会拒绝**——没完整影子不记账，这是设计而非 bug
7. **catboost 极慢**——D2 上跑了 ~28 min（cap 1800 s），agent 自己记了"10x cost, marginal gain"
8. **驱动器靠 tmux 常驻**：`tmux ls` 看 `phase7-seq-r`，kill 后重跑是幂等的

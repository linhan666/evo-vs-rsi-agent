# RSIAutoML / evo-vs-rsi-agent — 交接文档（P8 执行中）

更新时间：2026-11-10 17:05（GMT+8）
仓库：`github.com/linhan666/evo-vs-rsi-agent`，HEAD `462ec8e`
执行主机：**172.25.16.37 (H100b)**，工作目录 `/home/linhan_cluster/evo_vs_rsi`

---

## 0. 一句话状态

**p7 轮（81 条记录）已结束并出结论；p8 的机制已落地；AutoGluon 独立环境已建成、W 基线已端到端跑通（D2 锁定 0.9063，与四臂同量级）。还剩两件事未做：加"交互形式"轴（B④）、校准预算折算口径（C）。做完即可跑单档验证 → 全量。**

---

## 1. 用户的原始意图（逐字保留，勿改写）

> 我来描述一下理论上最理想的实验表现：
>
> （1）**W 是 automl 基线，没有 LLM 参与，限定算法类型和特征类型范围进行穷举，比如 100 个不同模型的穷举（这部分可以使用已有的开源的且权威的 automl 模型）**。结果应该是耗时最长，但确实可以得到第一或者较高的性能排名；
>
> **A 是 LLM 编排的 automl workflow 类 agent，不使用已有的开源的且权威的 automl 模型，而是由 LLM 编排决策**，同样限定算法类型和特征类型范围进行穷举，比如 100 个不同模型的穷举。结果应该是消耗 token，耗时较 W 有所下降，但是性能表现应该和 W 几乎一致；
>
> **M 是由 LLM 决策编排的带有记忆库的 agent**，同样限定算法类型和特征类型范围进行穷举，比如 100 个不同模型的穷举。经过单靶点的每折实验或者多靶点的轮流实验后，有记忆的情况下，LLM 开始会自主决策哪些特征和算法**以及交互形式**，进而不一定要 100 个不同模型，就可以自主决策停止，但是**只复用记忆，不会修改自身内容**。结果应该是消耗大量的 token，耗时较 W 有更明显下降，但是性能表现不稳定；
>
> **R 是自进化（RSI，针对于 harness 的自进化）的基于 LLM 的药物筛选 agent harness**，同样限定算法类型和特征类型范围进行穷举，比如 100 个不同模型的穷举。经过单靶点的每折实验或者多靶点的轮流实验后，有记忆且自进化的情况下，LLM 开始会自主决策哪些特征和算法以及交互形式，以及**灵活复用任何可用内容**，以及**根据所有反馈修改（或者说纠正）记忆、修改（或者说纠正、改善）harness**，进而不一定要 100 个不同模型，就可以自主决策停止……结果应该是**相比于 M 甚至 A 消耗较少的 token，耗时较 W 有更大幅下降（这里所有的耗时，指的是总耗时，而不是单靶点单轮的耗时），同时性能应该和 W 几乎一致**。
>
> （2）除了（1）的情况，可以看出 harness 自进化的 RSI 药物筛选 agent harness 速度极快和 token 消耗极低以及自动化程度极快，**可以匹配极高的搜索预算（也就是（1）限定的"100 个不同模型的穷举"）的性能，因此我们还可以逐轮减少搜索预算，理论上是预算越低，……性能可能还会超过 W\A\M 三组**。

### 1.1 对 W 的关键限定（用户反复强调三次）

> 强调的 automl 基线做法是"W 是 automl 基线，没有 LLM 参与，限定算法类型和特征类型范围进行穷举……（这部分可以使用已有的开源的且权威的 automl 模型）"，**这意味着不是"logreg、rf、xgboost、catboost"和"v1/v2/r1/b4096/r3b4096"这么简单的范围组合，也不是自建的 automl 基线，应该是使用"已有的开源的且权威的 automl 模型"**。

### 1.2 四组预期（结构化）

| 组 | LLM | 记忆 | 自进化 | 总耗时 | token | 性能 |
|---|---|---|---|---|---|---|
| **W** | 无 | 无 | 无 | **最长** | 0 | **第一/前列** |
| **A** | 编排 | 无 | 无 | 比 W 短 | 消耗 token | **≈ W** |
| **M** | 编排 | 有（只复用） | 无 | 比 W 明显短 | 大量 token | **不稳定** |
| **R** | 编排 + 改造自身 | 有（会纠正） | **有** | **比 W 大幅下降** | **比 M 甚至 A 少** | **≈ W** |

### 1.3 指标口径（用户强调）

- **耗时 = 跨靶点/跨轮次的累计总耗时**，不是单靶点单轮中位数。
- 性能 = 受保护**锁定测试集** AUROC（各臂共享同一批分子）。
- 效率 = 给定**试验预算**下达到的质量。

### 1.4 用户明确纠正过的三点（不要重犯）

1. **不要人为设作业超时**打断合法训练（曾把 catboost 在 1200 s 杀掉，改变了某臂的模型集合）。
2. **W 不能是弱基线**，必须是权威开源 AutoML，不能自建网格。
3. **框架选型由用户拍板**，我只做检索清单与实测（已选定 **AutoGluon**，用户并明确"集成保留"）。

---

## 2. p7 轮：已结束，结论如下

### 2.1 记录（81 条，`ops/phase7_runs/`）

| 标签 | 内容 | 条数 |
|---|---|---|
| `p7b` | 四臂 r/m/a/w × 9 靶点 | 36 |
| `p7c` | R′（v7 晋升后复跑） | 9 |
| `p7d`/`p7e` | M 臂重复两次（噪声标定） | 18 |
| `p7f`/`p7g` | W 臂重复两次（噪声标定） | 18 |

### 2.2 四臂描述统计（中位数，H100b）

| 臂 | 墙钟 s | 作业 | 模型 | token（实测） | 验证 AUROC |
|---|---|---|---|---|---|
| R | 484.9 | 22 | 11 | 1,285,191 | 0.980 |
| A | 347.4 | 20 | 12 | 1,315,823 | 0.982 |
| M | 278.0 | 16 | 8 | 1,275,072 | 0.978 |
| W | 30.8 | 0 | 0 | — | 0.942 |

### 2.3 测量层三个发现

| 发现 | 数据 | 后果 |
|---|---|---|
| 臂内噪声大 | M 三重跑锁定 AUROC 池化 **SD=0.0308**，CBR 单靶极差 **0.1543** | 臂对臂 δ≈0.012 **小于噪声** |
| 验证集无区分度 | 同臂重复 validation SD **0.0005**，同批模型锁定极差 0.154 | "择优"在锁定集看来近乎抽签 |
| W 确定性 | 3 次 × 9 靶极差全 **0.0000** | "vs W"的误差棒只来自 agent 一侧 |

### 2.4 结论（与 `CONCLUSIONS.md` 一致）

**支持**：记忆臂（R/M）优于 W —— M **+0.0447（4.3σ）**、R **+0.0275（2.7σ）**，t(8) 临界 2.31；自我改进回路可跑通、门禁能拒绝不合格候选。

**不支持**：记忆相对无记忆 agent 提升质量（R vs A **+0.0118** ≪ SD 0.0308，需 n≈103）；自我修改提升质量（R≡M，v7 是纯吞吐改动，5/9 逐位相同）；无记忆 agent 优于流水线（A **+0.0157，1.5σ**）。

**已撤回**：❌"记忆省 8 倍 token"（10.13M 是单条估算值，实测三臂均 ~1.28M）；❌"agent 慢 9–16 倍"（被 catboost 超时污染，剔除后 R 79 s / M 77 s / A 130 s）。

---

## 3. p8 机制：已落地并验证

| 机制 | 位置 | 状态 |
|---|---|---|
| **冻结搜索空间** 100 配置（4 算法 × 5 特征表示 × 5 **种子**） | `scientific/.../search/space.py`，`p8-100-v2`，指纹 `656e58db` | ✅ 但第三轴是**种子，不是交互形式** → 见 §7 B④ |
| **预算强制**（工具级） | `search/budget.py` + `train.py --config-id/--workspace/--budget-limit` | ✅ 实测 limit 5 → `used=5/5`，第 6 次抛 `SEARCH_BUDGET_EXHAUSTED`；重复同配置不重复扣 |
| `search.space` 工具 | 紧凑 TSV + `--json`；接受 id 或序号（`7`、`cfg000`） | ✅ |
| `harness.propose` 工具（P4-04） | `evovs_science/harness/propose.py` | ✅ agent 可写 CandidateSpec，晋升仍走 shadow/gate |
| **p8 切分**（验证集 10%→30%） | `ops/p8_splits.py` → `frozen_p8_<slug>.json`，验证 570–1862 | ✅ 锁定集未动 |
| **交付重评** | `ops/p8_finalize.py`（配合 `locked.py --recheck`） | ✅ 见 §5 缺陷表 |
| **门禁 early_rejection** | `evolution/gate.py` | ✅ 合成验证 10× 通过 / 1.11× 拒绝 |
| 135 份 p8 任务文本 | `ops/p8_texts.py` → `ops/p8_tasks/p8b<budget>_<arm>_<code>.json` | ✅ |
| 调度器 | `ops/p8_sweep.sh <budgets...>` | ✅ 语法通过，未跑全量 |

### 3.1 冻结空间的真实内容（重要，勿再简化）

| 轴 | 取值 |
|---|---|
| 算法族（4） | `logreg` / `rf` / `xgboost` / `catboost` |
| 特征表示（5） | `v1`=desc v1,r2,2048 · `v2`=desc v2,r3,2048 · `r1`=v1,r1,2048 · `b4096`=v1,r2,4096 · `r3b4096`=v2,r3,4096 |
| 第三轴（5） | **种子** 17/23/42/7/101 ← 应为交互形式，待改 |

排序为**种子最外层**：预算 4 覆盖四算法，预算 20 覆盖全部算法×特征组合。不要改回算法优先。

---

## 4. AutoGluon 基线：已建成并验证（本轮最重要的进展）

### 4.1 独立环境（`.venv-automl`）

| 项 | 值 |
|---|---|
| 路径 | `scientific/.venv-automl`（**1.2 GB**） |
| autogluon.tabular | **1.6.3**（`[lightgbm,catboost,xgboost]`，**不含** torch/spacy/fastai） |
| 依赖 | scikit-learn **1.9.1**、numpy 2.5.4、pandas 2.3.3、rdkit 2026.9.1 |
| 构建脚本 | `ops/p8_make_automl_venv.sh` |
| 版本指纹 | `ops/p8_venv_automl.freeze.txt` |

**必须独立**：该 venv 的 sklearn 是 **1.9.1**，agent 臂的 `scientific/.venv` 是 **1.5.2**（跨 4 个大版本）。原地升级会让 p7 的 81 条记录失去可复现性。

**安装坑**：该机无 ensurepip → `--without-pip` 建 venv，再从 `.venv` 拷 pip/setuptools/wheel 引导。`[all]` 会拉 torch（526 MB）+spacy+fastai，而模型类型里没有神经网络 → 只装 GBM 扩展。

### 4.2 W 脚本（`ops/p8_automl_ag.py`）

- 运行在 `.venv-automl`；模型族限定 `{GBM, CAT, XGB, RF, XT, LR}`（与 agent 可选项同集合）
- `num_bag_folds=0`、`num_stack_levels=0`、`auto_stack=False`、**`fit_weighted_ensemble=True`（集成保留，用户已拍板）**
- **锁定评分在本地复刻**：AutoGluon 产出预测器目录而非 `model.joblib`，现有 `evaluation.locked` 加载不了 → 在 `.venv-automl` 内用**同一 `featurize` 参数、同一指标函数**（`roc_auc_score`/`average_precision_score`/`enrichment`）算出同 schema 的受保护指标文件与收据
- 筛库同理内置（写 `runs/<tag>_all.csv` 与 `<tag>_topK.csv`）

### 4.3 实测结果

**探针（D2、v1、6 族）**：wall 60.9 s，val **0.9529**，枚举 7 个模型

| 模型 | val AUROC |
|---|---|
| WeightedEnsemble_L2 | **0.9529** |
| RandomForest | 0.9337 |
| ExtraTrees | 0.9210 |
| XGBoost | 0.9168 |
| CatBoost | 0.9150 |
| LinearModel | 0.9139 |
| LightGBM | 0.9101 |

对照：sklearn logreg 0.9383、rf 0.9133 → **管线正确**（FLAML 那次 0.58 的异常未再现）。

**端到端（D2、预算 5、每表示 15 s）**：

| 表示 | 选中 | val |
|---|---|---|
| **v1** | WeightedEnsemble_L2 | **0.9477** ← 选中 |
| r1 | WeightedEnsemble_L2 | 0.9446 |
| v2 | WeightedEnsemble_L2 | 0.9297 |
| b4096 | WeightedEnsemble_L2 | 0.9157 |
| r3b4096 | WeightedEnsemble_L2 | 0.8779 |

枚举 14 个模型，wall 161 s，**locked 0.9063**。

**对照 p7 同靶点锁定值**：W 0.8993 · R/M 0.9064 · A 0.9094 · **AutoGluon@b5 0.9063** → 同量级，包装器评分路径与 agent 臂可比。

---

## 5. 已修复缺陷清单（含根因，勿重犯）

### 5.1 编排与运维

| 缺陷 | 后果 | 修法 |
|---|---|---|
| tmux `-t` 前缀匹配（`p7b-a` 命中 `p7b-all`） | A→W 卡死 60 分钟 | 全改 `-t "=p7b-<arm>"` |
| `stores cleared` 无条件执行 | 续跑清空经验库 | 仅 `START_FROM=r` 时清 |
| watchdog 哨兵 `99999` | 被判"空闲 27 小时"，反复误报 | 未知返回空 + `stuck=0` 跳过，**未知绝不累计** |
| watchdog 无驱动时退出 | 臂切换窗口失去监控 | 改为继续待命 |
| 进度快照只计四臂 | 饱和后无法表达增量；`analysis_p7c.json` 被误计为记录 | 改 `round_counts`，严格文件名模式 |
| 作业超时 600/3600 s | catboost 被 SIGKILL，删掉某臂配置 | 默认 7200 s、上限 21600 s |
| **锁定评测限流挡住 finalize** | 交付重评**静默失败**，只记 `locked_rerun_error` | `locked.py --recheck`：越过 marker、输出加 `_recheck` 后缀、marker 仍写回 |
| **`rctl.py` 默认主机静默**（A800f） | 漏写 `--host` 把活派到另一台且无提示 | 每次连接在 stderr 打印 `[host] <ip>` |

### 5.2 测量与统计

| 缺陷 | 后果 | 修法 |
|---|---|---|
| `best_scaffold_auroc` 是 **max-over-N** | 奖励"训得多"，跨臂不可比 | 只用于同臂内；跨臂用锁定 AUROC |
| 锁定评测硬编码 `radius=2/n_bits=2048` | r1/b4096/r3b4096 **无法重建** | `--radius/--n-bits` 可传并写进收据名 |
| 交付模型 ≠ 最优模型（R 6/9、M 5/9、A 6/9） | 各臂被不同程度低估 | `p8_finalize.py` 强制用最优模型重评 |
| token 用单条估算值当中位 | 得出"省 8 倍"的错误结论 | 补齐台账重算；估算文件改名 `.superseded` |
| `--config-id` 可缺 `--split-manifest` | 回落到随机切分，`best` 变 None | 强制要求，否则 `MISSING_SPLIT_MANIFEST` |

### 5.3 第三方

| 问题 | 证据 | 规避 |
|---|---|---|
| **FLAML 2.8.0 的 `rf`/`extra_tree` 直接崩** | `AttributeError: 'RandomForestEstimator' object has no attribute '_t1'`；装 psutil 无效；设 `_t1` 的分支被内层守卫跳过 | 已弃用 FLAML，改 AutoGluon |
| AutoGluon 无 torch 时告警刷屏 | 预期内（模型类型不含 NN） | 后续静音，不影响结果 |

---

## 6. 环境与运维手册

### 6.1 主机拓扑（关系到墙钟可比性）

| 主机 | hostname | GPU | 角色 |
|---|---|---|---|
| **172.25.16.37** | `H100b` | 2× H100 80GB | **p7/p8 唯一执行主机** |
| 172.25.18.26 | `A800f` | 2× A800 80GB | NFS 服务端；用户记录里的"运行主机"，但本次未用 |

两者**共享同一份** `/home/linhan_cluster`（`.16.37` 上挂载自 `172.25.18.26:/nfs/linhan_cluster`，41 T / 50%）。故"代码落地 vs 实验测试"是**执行节点**的区别，不是文件位置的区别。**但墙钟是机器相关的**：p7 的 81 条全部在 H100b 测得。

### 6.2 跨节点共享状态（隐患）

| 共享状态 | 位置 | 后果 |
|---|---|---|
| 限流 marker | `<workdir>/.evaluation/<TARGET>_<ENDPOINT>.done` | 另一台的残留会让本台评测被拒 |
| 预算账本 | `<workdir>/.search_budget.json` | 另一台的消耗会污染 `used` |

**投全量前必须双机检查**：

```bash
for h in 172.25.16.37 172.25.18.26; do
  D:/anaconda3/python.exe ops/rctl.py exec \
    "hostname; tmux ls 2>&1|head; ps -eo pid,cmd|grep -E '[e]vovs_science|[p]hase7_seq|[p]8_'|head" --host $h
done
```
只允许执行主机上有会话；另一台必须完全静默（2026-11-10 17:00 实测：A800f 无 tmux 无进程）。

### 6.3 连接与环境

```bash
export MSYS2_ARG_CONV_EXCL='*' MSYS_NO_PATHCONV=1
cd D:/RSI_AutoML
D:/anaconda3/python.exe ops/rctl.py exec "<cmd>" --host 172.25.16.37
```
代理 `47.238.155.196:14842`。

| 项 | agent 臂 | AutoGluon 臂 |
|---|---|---|
| 解释器 | `scientific/.venv/bin/python`（3.12） | `scientific/.venv-automl/bin/python` |
| sklearn | **1.5.2** | **1.9.1** |
| 体积 | 1.8 G | 1.2 G |
| flaml | 2.8.0（已弃用） | — |

磁盘：`/home/linhan_cluster` NFS **21 T 可用**；`/home` 仅 647 G（96%）**别写**。pip 缓存曾达 7.5 G（可 `pip cache purge`）。

### 6.4 命名与去重（易踩）

- 记录文件 `<arm>_<seq>_<target>_<label>.json`
- 任务 id `<prefix>_<arm>_<code>`；**重跑必须换 prefix**，否则被判"已处理"卡住
- 锁定评测限流 marker：同一工单同一靶点只能评一次（operator 用 `--recheck` 例外）

---

## 7. 已批准但**尚未完成**的两项

### B④ 增加"交互形式"轴（`space.py` 第三轴）

**现状**：第三轴是**种子**，交互形式完全缺失（`grep interaction` 0 命中）。用户设计明确要求 M/R 能自主决定"哪些特征和算法**以及交互形式**"。

**要做**：
1. `rdkit.featurize` 增 `--interactions {none, desc-8, desc-16, and-64, and-128+desc8}`
   - `desc-k`：前 k 个描述符两两乘积（8→28 列，16→120 列）
   - `and-k`：方差最高 k 个位两两 AND（64→2016 列，128→8128 列）
   - **筛选只在训练折上做**，避免泄漏
2. 空间改 **4 算法 × 5 特征 × 5 交互 = 100**，种子固定 17（另设 ×2 种子做稳定性复核）
3. 同步更新 `p8_texts.py`（任务文本要告知可选交互形式）
4. AutoGluon 侧：把交互作为**特征表示的一部分**（同 5×5 组合喂给 W），保证两边同空间

### C 预算口径（已有实测数据，需定规则）

**问题**：agent 的预算是 **draw 数**（一次 `ml.train --config-id`），AutoGluon 却只能按 **时间**（`time_limit`）控制，无法限制试验数。

**实测**：D2 上名义预算 5（每表示 15 s）实际枚举 **14 个模型**，约 **5.4 秒/模型**。

**要做**：
1. 按 5.4 s/模型重新标定 `--seconds-per-model`
2. 记录里同时写明三个量：**目标预算 / 实际枚举数 / 哪个约束先触发**
3. 分析时按**实际枚举数**配对（而非名义预算），并在报告里显式说明这一折算

---

## 8. 已冻结的判定规则（2026-11-10，出结果前写定）

| 项 | 冻结值 |
|---|---|
| 执行主机 | **172.25.16.37 (H100b)** |
| 最小可主张效应（锁定 AUROC） | **≥ 0.031**（= 实测噪声地板 0.0308） |
| 主分析 | 各档内四组**配对**比较，每档独立，不跨档混池 |
| 预算递减判据 | 只看 **R 相对 W 的优势量是否随预算单调上升**（5 点趋势），不做逐点显著性 |
| 结论措辞 | 只能主张 ≥0.03 量级；**不得声称能检出 0.012**（需 n≈103） |
| 靶点数 | 维持 9 |
| W 定义 | **AutoGluon 1.6.3**，限定模型类型 × 5 特征表示；**集成保留**；枚举由 AutoGluon 完成 |

---

## 9. 下一步执行顺序

1. **标定预算折算**（按 5.4 s/模型；记录三量）
2. **加交互形式轴**（B④）→ 空间改 4×5×5 → 重出 135 份任务文本 → W 侧同步
3. **单档验证**（预算 5，四组全跑）：确认 ①预算被遵守 ②交付的是最优模型 ③finalize 能重评（`--recheck`）④四组锁定值同量级
4. **投全量**：100/50/20/10/5，预计 **15–20 小时**（AutoGluon 单档约 4–5 h）
5. **出报告**：每档四组的总耗时、总 token、锁定 AUROC；重点看"预算越低 R 优势是否越大"

---

## 10. 陷阱清单（照抄给新会话）

1. **别在实验运行期改 `train.py`**——四臂会跑在不同版本上。
2. **tmux 判断一律 `=name`**，`-t name` 是前缀匹配。
3. **重跑必须换 prefix**，否则 task_id 去重卡死。
4. **agent 可能猜错 config id**（`000`/`cfg000`），已兼容序号；异常 id 看工具报错示例。
5. **FLAML 的 rf/extra_tree 是库缺陷**，已弃用；别浪费时间排查自己的代码。
6. **`Path("")` 等于 `.`**——读记录目录前必须判空（曾导致遍历全仓库错配收据）。
7. **锁定评测有速率限制**；operator 重评必须带 `--recheck`。
8. **AutoGluon 产出的是预测器目录**，不是 joblib；别试图喂给 `evaluation.locked`。
9. **`/home` 只剩 647 G**，大文件落 `/home/linhan_cluster`。
10. **两个 venv 的 sklearn 差 4 个大版本**，别交叉调用。

---

## 11. 文件索引

| 路径 | 用途 |
|---|---|
| `CONCLUSIONS.md` | p7 轮完整科学结论（已定稿） |
| `HANDOFF_P8.md` | 本文档 |
| `scientific/src/evovs_science/search/{space,budget}.py` | 冻结空间 + 预算强制 |
| `scientific/src/evovs_science/harness/propose.py` | P4-04 agent 自主提案 |
| `ops/p8_make_automl_venv.sh` | 建 `.venv-automl` |
| **`ops/p8_automl_ag.py`** | **W 基线（AutoGluon，含同口径锁定评分与筛库）** |
| `ops/p8_automl.py` / `p8_workflow.py` | 旧 FLAML 版 / 旧手搭网格版（**均已作废**，保留对照） |
| `ops/p8_automl_probe.py` | AutoGluon 单靶点探针 |
| `ops/p8_splits.py` | 30% 验证集的 p8 切分 |
| `ops/p8_texts.py` | 生成 135 份任务文本 |
| `ops/p8_finalize.py` | 交付重评 + 预算字段补齐 |
| `ops/p8_sweep.sh` | 预算递减调度 |
| `ops/p8_trace_one.py` | 逐靶点导出四组执行轨迹 |
| `ops/p7b_noise_floor.py` / `p7b_noise_w.py` | 噪声地板与 agent-vs-W 误差棒 |
| `ops/phase7_locked.py` / `phase7_analysis.py` | 跨臂报告 |
| `evolution/gate.py` / `versions.json` | 门禁（含 `early_rejection`）/ 版本账本 v1–v7 |

---

## 12. 新会话建议开场（可直接粘贴）

> 接手 `D:/RSI_AutoML` + 远端 `172.25.16.37:/home/linhan_cluster/evo_vs_rsi`。
> 先读 `HANDOFF_P8.md`（尤其 §1 用户意图、§4 AutoGluon 现状、§7 未完成两项、§8 冻结规则）。
>
> 实验设计：四组（W=AutoGluon 基线 / A=LLM 编排 / M=LLM+记忆 / R=RSI 自进化）在同一冻结搜索空间
> 与试验预算下比较**累计总耗时、总 token、锁定 AUROC**，并做预算递减（100→50→20→10→5）。
>
> 已完成：p7 的 81 条记录与结论；p8 机制（冻结空间、预算强制、交付重评、门禁语义）；
> AutoGluon 独立环境（`.venv-automl`，1.6.3）与 W 基线端到端跑通（D2 锁定 0.9063）。
>
> 待完成：① 预算折算标定（实测 5.4 s/模型，名义 5 却枚举 14）② 加交互形式轴（空间改 4×5×5）
> ③ 单档验证 ④ 全量 ⑤ 报告。
>
> 硬约束：不动 `scientific/.venv`（sklearn 1.5.2，p7 记录的可复现性依赖它）；
> 只用 H100b；判定规则已冻结，改写需留带日期的修订记录。

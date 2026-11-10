# RSIAutoML / evo-vs-rsi-agent — 交接文档（P8 起点）

生成时间：2026-11-10 15:20（GMT+8）
仓库：`github.com/linhan666/evo-vs-rsi-agent`，HEAD `024c3b5`
远端主机：`172.25.18.26`（A800f），用户 `linhan_cluster`，工作目录 `/home/linhan_cluster/evo_vs_rsi`

---

## 0. 一句话状态

**p7 轮（四臂 36 条 + R′ 9 条 + M/W 各两次重复共 36 条 = 81 条记录）已全部结束并出结论。p8 轮的机制（冻结空间、预算强制、交付重评、门禁语义）已落地并验证。用户已批准 A②+B④+C 三项改造，但要求先不实施——本文档即为此准备。**

---

## 1. 用户的原始意图（务必按此执行，不要自行简化）

研究对象：**RSI 药物筛选 Agent Harness**（可自我演化的 LLM agent harness，用于分子活性预测与库筛选）。

### 1.1 四组对比设计

| 组 | 是什么 | LLM 角色 | 搜索方式 | 记忆 | 自进化 | 预期总耗时 | 预期 token | 预期性能 |
|---|---|---|---|---|---|---|---|---|
| **W** | **AutoML 基线，用权威开源 AutoML**（不是自建网格） | **无** | 限定算法族×特征类型穷举，如 100 个模型 | 无 | 无 | **最长** | 0 | **第一或前列** |
| **A** | LLM 编排的 AutoML workflow agent，**不用**现成 AutoML | 编排决策 | 同样穷举 100 | 无 | 无 | 比 W 短 | 消耗 token | **≈ W** |
| **M** | LLM 编排 + **记忆库** | 编排决策 | 多靶点轮转后有记忆，自主判断该试哪些特征/算法/交互，**不必跑满，可自主停止** | 有，**只复用** | 无 | 比 W 明显短 | 大量 token | **不稳定** |
| **R** | **RSI 自进化** harness | 编排 + 改造自身 | 同上，且**灵活复用任何可用内容、按反馈纠正记忆、修改/改善 harness 本身**，更早停 | 有，且**会纠正** | **有** | **比 W 大幅下降** | **比 M 甚至 A 更少** | **≈ W** |

### 1.2 第二轮：预算递减实验

R 既然又快又省，就能在**更低搜索预算**下逼近 100 配置的性能。逐轮压预算（100 → 50 → 20 → 10 → 5），**预算越低，R 相对 W/A/M 的优势应越大**，性能甚至可能反超。

### 1.3 指标口径（用户明确强调过）

- **耗时 = 跨靶点/跨轮次的累计总耗时**，不是单靶点单轮的中位墙钟。
- 性能 = 受保护**锁定测试集**上的 AUROC（各臂共享同一批分子）。
- 效率 = 在给定**试验预算**下达到的质量，即"用多少次拟合换多少分"。

### 1.4 用户反复纠正过的三点（不要重犯）

1. **不要人为设作业超时**打断合法训练（曾把 catboost 在 1200 s 杀掉，直接改变某臂的模型集合）。
2. **W 不能是弱基线**——必须是权威开源 AutoML，不能是我自建的 4 算法×5 特征网格。
3. **框架选型由用户决定**——我只负责检索清单与实测，不擅自定。

---

## 2. p7 轮：已完成、已出结论

### 2.1 记录清单（81 条，全部在 `ops/phase7_runs/`）

| 标签 | 内容 | 条数 |
|---|---|---|
| `p7b` | 四臂 r / m / a / w × 9 靶点 | 36 |
| `p7c` | R′（v7 晋升后复跑） | 9 |
| `p7d` / `p7e` | M 臂重复两次（噪声标定） | 18 |
| `p7f` / `p7g` | W 臂重复两次（噪声标定） | 18 |

### 2.2 四臂描述统计（p7b，中位数）

| 臂 | 墙钟 s | 作业数 | 模型数 | token（实测） | 验证 AUROC |
|---|---|---|---|---|---|
| R | 484.9 | 22 | 11 | 1,285,191 | 0.980 |
| A | 347.4 | 20 | 12 | 1,315,823 | 0.982 |
| M | 278.0 | 16 | 8 | 1,275,072 | 0.978 |
| W | 30.8 | 0 | 0 | — | 0.942 |

### 2.3 测量层三个发现（决定结论怎么读）

| 发现 | 数据 | 后果 |
|---|---|---|
| 臂内噪声大 | M 三重跑，锁定 AUROC 池化 **SD = 0.0308**，CBR 单靶极差 **0.1543** | 臂对臂待检效应 δ≈0.012 **小于噪声** |
| 验证集无区分度 | 同臂重复中 validation SD **0.0005**，而同批模型锁定极差 0.154 | agent 的"择优"在锁定集看来近乎**抽签** |
| W 确定性 | 3 次 × 9 靶，极差全 **0.0000** | "vs W"的误差棒只来自 agent 一侧，检验力充分 |

### 2.4 结论（分层，与 `CONCLUSIONS.md` 一致）

**支持**
- 记忆臂（R/M）在锁定集上优于 W：M **+0.0447（4.3σ）**、R **+0.0275（2.7σ）**，t(8) 临界 2.31。
- 自我改进回路可端到端跑通，门禁能拒绝不合格候选。

**不支持**
- 记忆相对无记忆 agent 提升质量：R vs A 仅 **+0.0118**，远小于 SD 0.0308。功效分析需 **n≈103** 靶点。
- 自我修改提升质量：R ≡ M（工具面相同，P4-04 当时未实现），v7 是纯吞吐改动，5/9 逐位相同。
- 无记忆 agent 优于流水线：A **+0.0157（1.5σ）**，不过线。

**已撤回的错误结论**
- ❌ "记忆省 8 倍 token"：10.13M 来自单条估算侧文件，补齐台账后 A 实测 1,315,823，三臂基本相同。
- ❌ "agent 比流水线慢 9–16 倍"：被 catboost 超时污染（R 丢 3000 s、M 丢 900 s），剔除后工具时间 R 79 s / M 77 s / A 130 s。

### 2.5 v7 晋升（已落地，可作为"自我修改生效"的机制证据）

- 变更：`EVOVS_TRAIN_JOBS` 默认 `1 → 8`（RF/XGB 的 `n_jobs`、CatBoost 的 `thread_count`）
- 门禁六项全过：equivalence 1.0 / cost 1.394× / success / failure n-a / quality n-a / safety canary
- shadow 重放 11 个真实 `ml.train` 步：57.38 s → 41.22 s
- 记录于 `evolution/versions.json` 的 **v7**

---

## 3. p8 轮：机制已落地（可直接复用）

### 3.1 冻结搜索空间

` scientific/src/evovs_science/search/space.py`，版本 `p8-100-v2`，指纹 `656e58db`。

| 轴 | 取值 |
|---|---|
| 算法族（4） | `logreg` / `rf` / `xgboost` / `catboost` |
| 特征表示（5） | `v1`(desc v1, r2, 2048) / `v2`(v2, r3, 2048) / `r1`(v1, r1, 2048) / `b4096`(v1, r2, 4096) / `r3b4096`(v2, r3, 4096) |
| 第三轴（5） | **种子** 17/23/42/7/101 ← **注意：这不是"交互形式"，见 §6 B④** |

**排序是「种子最外层」**：预算 4 覆盖四个算法族，预算 20 覆盖全部算法×特征组合。不要改回算法优先，否则低预算只试得到同一算法。

### 3.2 预算强制（工具级，非约定）

- `search/budget.py` + `train.py --config-id/--workspace/--budget-limit`
- 每张新配置扣一次；第 N+1 次抛 `SEARCH_BUDGET_EXHAUSTED`；**重复同一配置不重复扣**（复现检查）
- 账本 `.search_budget.json` 落在工单目录，字段 `{space_version, limit, used, ids}`
- 实测：limit 5 时 `used=5/5`，其后所有 draw 被拒

### 3.3 新工具

| 工具 | 作用 |
|---|---|
| `search.space` | 列出 100 配置（紧凑 TSV；`--json` 全量）。id 形如 `rf-v1-s17`，也接受序号（`7`、`cfg000`） |
| `harness.propose` | agent 自己写 CandidateSpec（P4-04 落地），晋升仍走 shadow/gate/operator |

### 3.4 p8 切分（验证集 10% → 30%）

`ops/p8_splits.py` 生成 `frozen_p8_<slug>.json`，各靶验证集 570–1862 个分子（原 190–621）。**受保护锁定集未动**，跨轮质量仍可比。

### 3.5 交付重评

`ops/p8_finalize.py --label <label>`：若锁定评测所用模型 ≠ 最优模型，自动用最优模型重跑并标 `locked_reevaluated: true`；同时补齐 `configs_used / budget_limit / stop_reason`。幂等（已 finalized 则跳过）。

### 3.6 门禁语义

`evolution/gate.py` 新增 `early_rejection`：判据从"失败消失"改为"同样失败但显著更快"（`min_rejection_speedup`，默认 2.0）。合成报告验证：10× 通过、1.11× 拒绝。

### 3.7 调度

`ops/p8_sweep.sh <budgets...>`：对每个预算依次跑 W（AutoML）、A、M、R，并在每档后 finalize。

### 3.8 任务文本

`ops/p8_texts.py` 生成 `ops/p8_tasks/p8b<budget>_<arm>_<code>.json`，共 135 份（5 预算 × 3 臂 × 9 靶）。

---

## 4. 已修复的缺陷清单（新会话务必知道，别重犯）

### 4.1 编排与运维

| 缺陷 | 后果 | 修法 |
|---|---|---|
| **tmux `-t` 是前缀匹配**，`p7b-a` 匹配到 `p7b-all` | A→W 切换卡死 60 分钟（等一个永不退出的会话） | 全部改 `-t "=p7b-<arm>"` 精确匹配 |
| `stores cleared` 无条件执行 | 续跑时清空经验库（R 的库被清、M 的差点被清） | 仅 `START_FROM=r` 时清 |
| watchdog 用哨兵 `99999` 表示"未知" | 被判成"空闲 27 小时"，反复误报（未真触发，纯侥幸） | 未知返回空 + `stuck=0` 跳过，**未知绝不累计** |
| watchdog 在无驱动时退出 | 臂切换窗口失去监控（第二次发生） | 改为继续待命 |
| 进度快照只计四臂 | 四臂饱和后无法表达增量；`p7c_records` 把 `analysis_p7c.json` 也算进去 | 改 `round_counts`，按严格文件名模式统计 |
| 作业超时 600/3600 s | catboost 被 SIGKILL，直接删掉某臂的配置 | 默认 7200 s、上限 21600 s |

### 4.2 测量与统计

| 缺陷 | 后果 | 修法 |
|---|---|---|
| `best_scaffold_auroc` 是**训练过的模型取 max** | 奖励"训得多"（A 13 个、R 7 个、M 5 个），跨臂不可比 | 只用于同臂内比较；跨臂用锁定 AUROC |
| 锁定评测硬编码 `radius=2 / n_bits=2048` | r1/b4096/r3b4096 三种表示**无法重建**，p7 大量锁定评测缺失 | `--radius/--n-bits` 可传，并写进收据文件名 |
| 交付模型 ≠ 最优模型（R 6/9、M 5/9、A 6/9） | 各臂质量被不同程度低估 | `p8_finalize.py` 强制用最优模型重评 |
| token 用了单条估算值当九条中位 | 得出"省 8 倍"的错误结论 | 补齐台账后重算；估算侧文件改名 `.superseded` |
| `--config-id` 可缺 `--split-manifest` | 回落到随机内部切分，与冻结切分不可比，`best` 变 None | `--config-id` 必配 `--split-manifest`，否则 `MISSING_SPLIT_MANIFEST` |

### 4.3 第三方

| 问题 | 证据 | 规避 |
|---|---|---|
| **FLAML 2.8.0 的 `rf`/`extra_tree` 直接崩** | `AttributeError: 'RandomForestEstimator' object has no attribute '_t1'`；装 `psutil` 无效；源码里设 `_t1` 的分支被内层守卫跳过 | 见 §6 A②：改用 AutoGluon；或剔除这两族；或降级 FLAML |

---

## 5. 环境与运维手册

### 5.1 连接

```bash
export MSYS2_ARG_CONV_EXCL='*' MSYS_NO_PATHCONV=1
cd D:/RSI_AutoML
D:/anaconda3/python.exe ops/rctl.py exec "<远程命令>" --host 172.25.16.37
D:/anaconda3/python.exe ops/rctl.py put <本地> <远端> --host 172.25.16.37
```

代理 `47.238.155.196:14842`（账号见用户提供）。**每次调用都要带 `export MSYS2_ARG_CONV_EXCL='*'`**，否则 `/home/...` 被转成 Windows 路径。

### 5.1b 主机拓扑（关系到墙钟可比性，必读）

| 主机 | hostname | GPU | 角色 |
|---|---|---|---|
| **172.25.16.37** | `H100b` | 2× H100 80GB | **本次会话全部计算实际运行在这台** |
| **172.25.18.26** | `A800f` | 2× A800 80GB | 用户记录中标注的"运行主机"；**同时是 NFS 服务端** |

**关键事实：两者共享同一份存储。** `.16.37` 上 `/home/linhan_cluster` 挂载自 `172.25.18.26:/nfs/linhan_cluster`（41 T，50% 使用）。因此：

- 两台机看到的仓库、commit、数据**完全一致**（实测两台都在 `71372ca`，同一份 `ops/phase7_runs/`）。
- 所以"代码落地主机 vs 实验测试主机"在这套环境里**不是文件位置的区别，而是在哪个节点执行的区别**。
- **但墙钟是机器相关的。** p7 的 81 条记录全部在 `H100b` 上测得；若换到 `A800f` 跑，墙钟不可跨轮直接比较。
- 用户记忆里的执行规则写的是 `.18.26`，而本会话用的是 `.16.37`——**这一偏离已如实记录**。p7 全是 CPU 活（rdkit / sklearn），质量指标不受影响，但耗时数据带 H100b 的机器指纹。

**后续要求**：p8 全轮锁定在同一台机上跑；若改机，必须在报告里注明并重新建立墙钟基线。

### 5.2 Python 环境

| 项 | 值 |
|---|---|
| 解释器 | `/home/linhan_cluster/evo_vs_rsi/scientific/.venv/bin/python`（3.12） |
| 关键版本 | scikit-learn **1.5.2** · numpy **2.1.3** · flaml **2.8.0** · psutil 7.2.2 |
| venv 体积 | 1.8 G |
| 磁盘 | `/home/linhan_cluster` NFS **21 T 可用（50%）**；`/home` 仅剩 647 G（96%）——**别往 /home 写大数据** |
| pip | `scientific/.venv/bin/pip 24.2`，镜像 `https://pypi.tuna.tsinghua.edu.cn/simple` 可用 |

### 5.3 常用命令

```bash
# 服务（agent 需要）
scripts/dsh-superagent start|stop|status          # group: rsi / memory / fixed
tmux set-environment -g EVOVS_GROUP rsi          # 切组必须同时 set-environment 与 export
# 关键：切组后要验证 /proc/<pid>/environ 里 EVOVS_GROUP 与预期一致

# 驱动
python3 -u ops/phase7_seq.py --group r --prefix p8b5 --tasks-dir ops/p8_tasks \
        --label p8b5 --budget-limit 5 --usage-log usage_p8_rsi.jsonl

# 监控
tail -1 .artifacts/p7b_status.jsonl              # 每分钟快照（round_counts/sessions/science_processes）
bash ops/p7b_watchdog.sh                         # 看门狗（tmux 名 p7b-watch）
bash ops/p7b_progress.sh                         # 进度快照（tmux 名 p7b-progress）
```

### 5.4 命名与去重（极易踩）

- 记录文件：`<arm>_<seq>_<target>_<label>.json`，例 `r_01_d2_p8b5.json`
- 任务 id：`<prefix>_<arm>_<code>`，例 `p8b5_r_d2`；**重跑同一 label 会被判"已处理"而卡住** → 换新 prefix
- 锁定评测限流：`<workdir>/.evaluation/<TARGET>_<ENDPOINT>.done` 存在即拒绝

---

## 6. 用户已批准但**尚未实施**的三项改造

### A② 切 AutoGluon，装独立 venv

**决定**：改用 AutoGluon 作 W 基线；**装到独立 venv**（如 `scientific/.venv-automl`），不动 `scientific/.venv`。

**为什么必须独立**：AutoGluon 新版要求 `scikit-learn ≥ 1.6`，而当前是 1.5.2。一旦原地升级，**p7 的 81 条记录与全部锁定评测的环境就变了**，可比性受损。

**实施要点**
1. 建 `scientific/.venv-automl`（该机无 ensurepip，需 `--without-pip` + 从现有 venv 借 pip bootstrap）
2. `pip install autogluon.tabular`，`du -sh` 量体积并记录 `pip freeze` 指纹
3. `p8_automl.py` 增加 `--python` 参数，用该解释器跑 W；agent 臂仍用 `scientific/.venv`
4. 必须验证：能接受我们预计算的稠密特征、能限制模型族（与 agent 臂同空间）、能按**试验数**计预算（`auto_stack=False`、`num_bag_folds=0`、`holdout`/`num_stack_levels=0`，用 `fit(time_limit=..., presets='medium')` 时需记录折算规则）、能导出 `predict_proba` 模型供 `evaluation.locked` 评分

### B④ 增加"交互形式"轴

**背景**：用户设计里搜索空间是「算法类型 × 特征类型 × **交互形式**」，而当前第三轴是**种子**，交互形式完全缺失（`grep interaction` 在清单里 0 命中）。

**实施要点**
1. `rdkit.featurize` 增 `--interactions {none, desc-8, desc-16, and-64, and-128+desc8}`
   - `desc-k`：前 k 个描述符的两两乘积（8→28 列，16→120 列）
   - `and-k`：方差最高的 k 个位两两 AND（64→2016 列，128→8128 列）
   - **位/描述符的筛选只在训练折上做**，避免泄漏（或固定按列号取）
2. 空间改为 **4 算法 × 5 特征 × 5 交互 = 100**，种子固定 17（另设一个 ×2 种子的稳定性复核）
3. 同步更新 `p8_texts.py`（任务文本要告诉 agent 可以选交互形式）

### C 保留 5 表示 + 按试验数对齐预算

- 特征表示保持 5 种（不缩减）
- W 与 agent 臂的预算单位统一为**试验数（拟合次数）**；若 AutoGluon 只能按时间预算，则必须在记录里写明折算规则与"哪个约束先触发"

---

## 7. 下一步执行顺序（建议）

**0. 先锁定执行主机**（见 §5.1b）。p7 的墙钟是在 `172.25.16.37 (H100b)` 上测的；
p8 全轮应固定在**同一台**，否则总耗时不可跨轮比较。用户记录的运行主机是 `172.25.18.26`，
若要迁到 A800f，需重测一次基线并把机器标识写进报告。

1. 建独立 venv + 装 AutoGluon，量体积、锁版本、记 `pip freeze`
2. 单靶点（D2）对照验证：AutoGluon 的验证 AUROC 应落在 **0.90–0.95** 区间（与 sklearn logreg 0.938 / rf 0.913 同量级）；若出现 0.58 这种异常即为管线错误
3. 加 `--interactions` 与新的 100 配置空间，重出 135 份任务文本
4. 单档验证（预算 5）：确认 ①预算被遵守 ②交付的是最优模型 ③finalize 能重评
5. 通过后投 5 档全量（100/50/20/10/5）。按当前速度估计 **15–20 小时**
6. 出报告：每档 × 四组的总耗时、总 token、锁定 AUROC；重点看"预算越低 R 优势是否越大"

---

## 8. 陷阱清单（照抄给新会话）

1. **别在实验运行期间改 `modeling/train.py`**——四臂会跑在不同版本上。
2. **tmux 会话判断一律用 `=name`**，`-t name` 是前缀匹配。
3. **重跑必须换 prefix**，否则 task_id 去重会直接卡住。
4. **agent 可能猜错 config id**（`000`/`cfg000`），现已兼容序号；若再出现异常 id，看工具报错里的示例。
5. **FLAML 的 rf/extra_tree 不可用**（2.8.0 缺陷），别浪费时间排查自己的代码。
6. **`Path("")` 等于 `.`**——凡是"读记录里的目录"都要先判空，否则会遍历整个仓库（`phase7_locked.py` 曾因此错配全部收据）。
7. **锁定评测有速率限制**，同一工单同一靶点只能评一次；重评要换收据名或清 marker。
8. **`/home` 只剩 647 G**，大文件一律落 `/home/linhan_cluster`（NFS，21 T）。

---

## 9. 术语与口径

| 术语 | 定义 |
|---|---|
| **锁定 AUROC** | 受保护测试集上的 AUROC，按靶点固定、各臂共享，**唯一合法的跨臂标尺** |
| **验证 AUROC** | 内部冻结切分（p8 为 30%）上的分数，用于**同臂内**选模型，**不可跨臂比** |
| **draw / 试验预算** | 一次 `ml.train --config-id`（或 AutoGluon 的一次 trial） |
| **stop_reason** | `budget_exhausted`（用满）/ `stopped_early`（自主提前停） |
| **W 确定性** | 同数据同代码同种子，重跑逐位相同（实测极差 0.0000） |
| **噪声地板** | 同臂重跑的锁定 AUROC 池化 SD = 0.0308；任何小于它的臂间差异不可主张 |
| **墙钟口径** | **机器相关**。p7 全部在 `172.25.16.37 (H100b)` 测得，换机不可直接比较 |

---

## 10. 关键文件索引

| 路径 | 用途 |
|---|---|
| `CONCLUSIONS.md` | p7 轮的完整科学结论（已定稿） |
| `scientific/src/evovs_science/search/space.py` | 冻结搜索空间（100 配置、指纹、序号解析） |
| `scientific/src/evovs_science/search/budget.py` | 预算账本与强制 |
| `scientific/src/evovs_science/harness/propose.py` | P4-04：agent 自主提案 |
| `ops/p8_automl.py` | W 基线（当前是 FLAML 版，待换 AutoGluon） |
| `ops/p8_workflow.py` | 旧的手搭网格 W（**已作废**，保留仅作对照） |
| `ops/p8_splits.py` | 生成 30% 验证集的 p8 切分 |
| `ops/p8_texts.py` | 生成 135 份任务文本 |
| `ops/p8_finalize.py` | 交付重评 + 预算字段补齐 |
| `ops/p8_sweep.sh` | 预算递减调度 |
| `ops/p8_trace_one.py` | 逐靶点导出四组执行轨迹（分析行为差异用） |
| `ops/p7b_noise_floor.py` / `p7b_noise_w.py` | 噪声地板与 agent-vs-W 误差棒 |
| `ops/phase7_locked.py` / `phase7_analysis.py` | 跨臂报告生成 |
| `evolution/gate.py` | 门禁（含 `early_rejection`） |
| `evolution/versions.json` | 版本账本（v1–v7） |

---

## 11. 新会话建议开场

> 接手 `D:/RSI_AutoML` + 远端 `172.25.18.26:/home/linhan_cluster/evo_vs_rsi`。
> 先读 `HANDOFF_P8.md` 与 `CONCLUSIONS.md`。
> 用户的实验设计是四组（W=权威 AutoML 基线 / A=LLM 编排 / M=LLM+记忆 / R=RSI 自进化）
> 在同一冻结搜索空间与试验预算下比较**累计总耗时、总 token、锁定 AUROC**，并做预算递减（100→50→20→10→5）。
> 已批准待实施：A②（AutoGluon 装独立 venv）、B④（加交互形式轴，空间改 4×5×5）、C（保留 5 表示、按试验数对齐预算）。
> 实施前不要动 `scientific/.venv`；所有改动先单靶点验证再投全量。

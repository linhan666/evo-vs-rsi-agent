# PHASE5_REPORT — 科学面板扩展、双端点分歧与候选裁决（附一处结论更正）

> 覆盖蓝图 **P4-02 续 + P5-03（部分）+ P6 数据面预置**（项目把蓝图 P4/P5 合并后继续编号为"项目 Phase 5"）。
> 本阶段无新外部依赖；服务全程停止，动作是 operator/CLI + 真实 Ticket。
> **重要**：本报告 §6 更正了当日工作日志中一条关于 descv2 的结论——原结论建立在"跨端点错配"的数字上，不能作为证据使用。

## 1. 交付物

| 组件 | 作用 |
|---|---|
| `experience/store.py` 的 flock | `record()` 走 `<store>.lock` 的 `LOCK_EX`，operator 与 engine 双写不丢记录 |
| `evolution/trace_export.py`（扩展） | trace 步骤新增 `exit_code`，失败步骤进语料 |
| `ops/sync_traces.py` | 语料自动扩充（幂等，按 ticket 目录名导出），每轮收尾执行 |
| `evolution/failure_clusters.py` | 按 `tool_id + 错误类` 聚合失败模式（只"浮出模式"，不下诊断） |
| `chemistry/featurize.py` 的 `EVOVS_DESC_SET` | 描述符 7 维（v1）/ ~43 维（v2）单代码路径 |
| `data/normalize.py --endpoint IC50` | IC50 独立通道数据集（自带 split 与 protected 测试集） |
| `screening/predict.py`、`screening/matrix.py` | 100k 排序与跨靶点矩阵（复用） |
| `screening/dual_endpoint.py`、`screening/shortlist.py` | 双端点一致性分析 / top-K shortlist 对比 |
| `evaluation/locked.py` 的 `--desc-set` / `--endpoint` | 垫片支持特征代与端点（默认 v1 / Ki，行为兼容） |
| `src/research/engine-pass.ts` + `orchestrator_report` 钩子 | **Engine pass**：Ticket 报 `ready` 后由 Harness 自动触发锁定评测（不解析 Agent 文案，复用同一垫片与限频） |
| `evolution/propose.py` + `test_propose.py` | **P4-04（混合式）**：规则从语料挖候选机会并锁定 knob/验收，固定 LLM 只写 hypothesis/risk；产物过 `validate_spec` 才落盘 |

## 2. 语料与失败聚类基线

| 指标 | 值 |
|---|---|
| trace 语料 | **20 条**（55 步，5 个失败步；schema **v2**，每步带 `stderr_tail`） |
| 失败簇 | **3 个**：`experience.retrieve::FileNotFoundError`(2)、`rdkit.featurize::missing_column:smiles`(2)、`screening.rank::IsADirectoryError`(1) |
| 涉及工单 | `chembl-oprm1-e2e`、`chembl-oprm1-rerun`、`chembl-oprk1-check`（均为早期已修复毛刺） |

结论：**检测能力验证通过，但语料刚到门槛，3 个簇全部是"已修复的历史毛刺"，尚无可统计的模式**。聚类报告本身标注了 "Pattern surfacing only"。

> D-1 之前这三簇的键是 `::exit_1` 且 `sample_errors` 全为空——聚类"能跑"但不可诊断。修复后每一簇都能直接读出原因（缺输出目录、列名不匹配、把模型目录当文件）。
> 同时 `ops/sync_traces.py` 的收录条件从"至少一个科研作业**成功**"改为"**尝试过**科研工具"：全员失败的工单恰恰是失败分析最该看的那类，之前被排除在外（本次 19/22 个工单入语料）。

## 3. candidate3：描述符扩展（descv2）→ 方向性通过，**不上线**

**Ki 通道（垫片对 Ki 锁定测试，口径正确）**

| 靶点 | v1（默认） | descv2 | Δ | CI95（scaffold 聚类 bootstrap） |
|---|---|---|---|---|
| MOR | 0.9339 | 0.9343 | **+0.0004** | 含 0 |
| KOR | 0.8685 | 0.8742 | **+0.0057** | 含 0 |
| DRD2 | 0.9015 | 0.9070 | **+0.0055** | 含 0 |

按预注册的**点估计**口径（≥2 靶点 +0.005 且无下降）判定通过；**三条 CI 全部含 0，属方向性信号、非显著改善**。
**operator 决策：保持 v1 为默认**（`docs/evidence/phase4/decision_descv2.json`）。理由：收益未证实；下一个大工作（IC50 双端点 100k 排序）应在单一特征代上做；晋升窗口不关，而降级窗口会关。v2 保留在 `EVOVS_DESC_SET=v2` 分支，复活条件已写入设计文档与经验库。

## 4. candidate4：IC50 独立通道 → 通过，纳入面板

- **§9.2 口径审核**：`Ki+IC50 合并`变体**被拒绝且不实现**（不同标准类型不得直接合并）；**独立通道**允许——自带 normalize / split / protected locked test，永不与 Ki 数字合并或比较。
- 数据集：MOR 3,571 行 / KOR 4,337 / DRD2 2,442（IC50 快照），各自 scaffold split。

| 靶点 | 锁定测试 n（正/负） | AUROC | AUPRC | EF@1% |
|---|---|---|---|---|
| MOR | 99（56/43） | **0.9188** | 0.9332 | 1.768 |
| KOR | 159（35/124） | **0.8954** | 0.7069 | 2.271 |
| DRD2 | 63（41/22） | **0.9157** | 0.9638 | 1.537 |

三个通道均 ≥0.80 验收通过 → IC50 通道正式纳入面板（经验库 `model_MOR_022/KOR_023/DRD2_024`、`screening_HARNESS_018`）。
100k 三榜筛选各约 19 s（并行特征化生效），100,000/100,000、无效 SMILES 0。

## 5. 双端点分歧（**本阶段最硬的科学结论**）

同一 100k 库、同一特征代（v1），Ki 榜与 IC50 榜的排序一致性：

| 靶点 | jointly ranked | Spearman ρ | Kendall τ | Top100 重叠 |
|---|---|---|---|---|
| MOR | 100,000 | **0.054** | 0.035 | **2 / 100** |
| KOR | 100,000 | 0.4103 | 0.2781 | **0 / 100** |
| DRD2 | 100,000 | 0.2760 | 0.1860 | **0 / 100** |

**解读**：结合亲和力（Ki）与功能效价（IC50）的模型视图在候选空间**几乎不重合**——MOR 接近随机。
→ 双通道互补筛选成立；**单通道 shortlist 是端点特异的**，不能互相替代。
**边界**：两榜都是对无标签库的预测，一致性描述的是模型视图而非真实命中率（报告内已逐字标注）。

## 6. ⚠️ 结论更正：IC50 通道的 descv2 "验证"不成立

当日工作日志记录过一次"IC50-descv2 三工单，锁定 AUROC 大幅劣化（MOR 0.9188→0.7898、KOR 0.8954→0.7041、DRD2 0.9157→0.6937），故 descv2 收益不外推"，并据此认为"分代验证面拦住了一个会污染 IC50 线的晋升"。**本轮复核发现该结论不成立。**

**证据链（可复算）**

1. 三个工单（`chembl-{mor,kor,drd2}-ic50-*`）的 `ml.train` 输入是 **IC50 数据集**：
   `--labels …/chembl/oprm1/ic50/dataset.csv --label-source chembl37_ic50_pX7_6_descv2`；
2. 其 `evaluation.locked` 只传了 `--target`，而 `locked.py` 里 `TARGET_DIRS` **硬编码为 Ki 目录**，测试集固定 `final_test_Ki.csv`；
3. 因此 0.7898 / 0.7041 / 0.6937 的真实含义是 **"IC50 模型 对 Ki 标签"的跨端点 AUROC**，与 IC50 通道自身的 v1 基线（0.9188 / 0.8954 / 0.9157，评测在 `final_test_IC50.csv` 上）**不同标签、不可比较**。

**修复后的正确读数（F-1…F-3 已完成，2026-11-06 03:10）**

`--endpoint IC50` 生效后，把同一批 IC50 模型（desc_set=v2）评在 `final_test_IC50.csv` 上：

| 靶点 | IC50 v1（基线） | **IC50 descv2（重跑）** | Δ | 旧错误读数（对 Ki 标签） |
|---|---|---|---|---|
| MOR | 0.9188 | **0.9223** | **+0.0035** | 0.7898 |
| KOR | 0.8954 | **0.8991** | **+0.0037** | 0.7041 |
| DRD2 | 0.9157 | **0.9146** | **−0.0011** | 0.6937 |

→ **descv2 在 IC50 通道同样是"持平偏微升"**（与 Ki 通道的 +0.0004/+0.0057/+0.0055 一致），**没有劣化**。旧的 0.79/0.70/0.69 完全由端点错配造成。
三条结果已按正确 payload 入经验库（`model_MOR_025`、`model_KOR_026`、`model_DRD2_027`）。

**由此撤回的表述**

- ✗ "descv2 在 IC50 通道劣化 −0.13~−0.22" → 撤回；
- ✗ "descv2 收益不外推到 IC50 通道" → **已用正确口径重跑**：结论是"同样持平偏微升"，不是劣化（见上表）；
- ✓ 保留的表述：0.69–0.79 是**跨端点迁移**的一个观察值（IC50 训练的模型对 Ki 标签仍显著优于随机），但**不是 descv2 的证据**。

**对决策的影响**：`保持 v1 为默认` 的结论**不变**——它由 Ki 通道三条 CI 全含 0 支撑，与 IC50 无关（`decision_descv2.json` 的三条理由本来也没引用 IC50）。受影响的是证据链的一句话，不是上线状态。

**附带发现（同一处代码）**：`locked.py` 的输出名是 `metrics_test_locked_agent_{basename(workspace)}_{target}.json`。三个 IC50 工单与后续 Ki-descv2 复跑都以 `--workspace .` 调用 → 文件名坍缩成同一个 `…agent_._DRD2.json`，**后跑的 Ki-descv2（0.907）覆盖了先跑的 IC50 结果**。目前 IC50-descv2 的数字只存在于工单 `runs/evaluation/receipt.json`，protected 树里已被覆盖。

**修复项（P0，下一步第一件事）**

| # | 修复 |
|---|---|
| F-1 | ✅ `locked.py` 增加 `--endpoint {Ki,IC50}`，映射到正确目录与 `final_test_{Ki,IC50}.csv`；registry schema（`version 0.2.0`）与契约测试同步（13/13） |
| F-2 | ✅ 输出名改为 `…agent_{endpoint}_{desc_set}_{ticket}_{target}.json`，不同通道/代不再互相覆盖 |
| F-3 | ✅ 重跑三个 IC50-descv2 锁定评测（0.9223 / 0.8991 / 0.9146），入经验库 `model_*_025/026/027` |
| F-4 | ✅ `docs/PHASE4_DESIGN.md` 与 `docs/EVALUATOR_TRIGGER_DESIGN.md` 均已标注本次更正 |

## 7. 首个自动提案：实测否决（2026-11-06 15:10）

`auto-latency-share-screening-rank`（`EVOVS_SCREEN_JOBS=8`）由混合式提案器生成后，实现并实测：

| 场景 | 墙钟 | 结论 |
|---|---|---|
| 10k 行，`EVOVS_SCREEN_JOBS=1`（基线） | 9.0 s | — |
| 10k 行，`EVOVS_SCREEN_JOBS=4` | 21.5 s | **慢 2.4×** |
| 100k 行，`EVOVS_SCREEN_JOBS=1` | 21.4 s（二次 30.0 s） | 语料中位 73.7 s 已过时 |
| 100k 行，`EVOVS_SCREEN_JOBS=8` | 300 s 内未完成 | 终止 |

**根因**：`rdkit.featurize` 本身已是分块并行（`EVOVS_FEAT_JOBS=8`，candidate1 已晋升），而它才是主要成本；外层再并行会把内层强制串行（每个 worker 里 `EVOVS_FEAT_JOBS=1`），并给每个 worker 复制一份 822 MB 特征矩阵。进程池版本还会因 fork 后持有 xgboost/RDKit 状态而死锁（实测卡住，改用线程后不死锁但更慢）。

**两个方法学缺陷（已修）**

1. **语料跨晋升**：73.7 s 的中位来自 candidate1 之前的记录。`propose.py` 现在把 `corpus_window` 与 caveat 写进证据，并要求"调用来自至少两个工单"——单个工单（尤其是探针工单）不能代表工作负载。
2. **影子拿 trace 记录当基线**：陈旧数字会让候选"假赢"。`shadow.py` 新增 `--baseline-replay`：现跑一遍基线，延迟结论只认现测；顺带把超时记为 `exit_code=-9` 而不是让评估器崩溃。

**处置**：实现已回滚（`git checkout`），**未上线任何 knob、零行为变化**；spec 标 `rejected` 并附完整测量、根因与后续动作（`evolution/candidates/auto-latency-share-screening-rank.json`）。这是本项目第一次跑通"自动提案 → 实现 → 实测 → 否决"的完整闭环，也是蓝图 §19.2 要求的"报告被拒绝的候选"的第一条真实记录。

### 7.1 Engine pass 端到端验证（同日 15:36，真实 Ticket）

**任务**：`engine_pass_check_002` → Ticket `engine-check-exact-27505612356f`（任务里**明确禁止** Agent 自己调 `evaluation.locked`）。

| 项 | 结果 |
|---|---|
| 作业 | `rdkit.featurize` + `ml.train`，2 个全 SUCCEEDED，40 s 内完成 |
| **回执** | `runs/evaluation/engine_receipt.json` 自动出现：`target=MOR / endpoint=Ki / desc_set=v1` |
| 指标 | AUROC **0.9339**、AUPRC 0.9722 —— 与 operator 的 MOR 基线**逐位一致** |
| 限频标记 | `.evaluation/MOR_Ki.done`（与 Agent 工具共用） |
| 证据 | `docs/evidence/phase5/engine_pass_receipt.json`、`engine_pass_marker.json` |

→ **Engine pass 成立**：目标/端点/特征代全部从作业记录推导，Agent 全程未参与评测，回执与保护目录均由 Harness 写入。这是方案 3 第一次在真实 Ticket 上生效。

**同日的一个反例（也是闭环的一部分）**：第一次尝试 `engine_pass_check_001` 时，Agent 未按数据集表头传 `id_column/smiles_column`，`rdkit.featurize` 连续失败 **12 次**（同一错误反复重试）。该工单已进语料，`failure_clusters` 立刻出现 `missing_column:smiles ×6`；提案器据此自动生成两个候选（`auto-failure-recurrence-rdkit-featurize-61c653` / `-f80739`），证据直接引用该 Ticket。**真实失败 → 语料 → 自动提案**这条链路当天就闭合了。

## 8. 其他缺陷与教训

| 缺陷 | 处理 / 教训 |
|---|---|
| **D-1 失败诊断文本丢失**（✅ 已修） | 根因：`job-runner` 把 stderr 写 `stderr.log`，`result.json` 的 `error` 只在 spawn 失败 / 缺产出 / 主机中断时填写，`trace_export` 只读 `error` → 非零退出的文本全空。修复：trace schema **v2**，每步新增 `stderr_tail`（≤1200 字符，按字节尾部读）与失败步的 `stdout_tail`（仅当 stderr 静默）；`failure_clusters` 改为"结构化 error → stderr 末行 → stdout 末行 → exit_code"四级取值，并对 `has no 'X' column` 与未知参数给出具名类，未分类消息中的绝对路径折叠为 `<path>`（聚类键不能随机器变）。语料已按新 schema 重导，15 个 evolution 单测通过 |
| **D-2 经验记录 payload 错位**（✅ 已补） | `model_HARNESS_017` / `screening_HARNESS_018` 的 payload 误指向失败聚类报告。新增 `ops/record_evidence_bundle.py`：把"结论所依赖的多个工件 + 各自 sha256"打成证据包再入库（store 一条记录只挂一个 payload 是结构限制，证据包是诚实的绕法）。已追加 `harness_HARNESS_028`（descv2 决策 + 三个 Ki 锁定指标）与 `harness_HARNESS_029`（candidate4 + 三个 IC50 锁定指标），旧记录保留并在 `applicability` 标注 supersedes |
| 评测器 `--target-indicator` 误用 | 该参数是 pooled 模型专用（追加 one-hot）；per-target 模型误传会维度不匹配（2094≠2091）。已在文档标注 |
| RDKit 入口名 | 是 `Descriptors.CalcMolDescriptors`（`rdMolDescriptors.CalcMolDescriptors` 不存在） |
| 多字节/括号内容走 shell heredoc 必炸 | 一律写 `ops/*.py` 脚本文件执行 |
| 经验库路径 | 必须显式 `--store`（默认路径依赖 cwd 的历史缺陷已修，但显式传值仍是硬规则） |

## 9. Known failures / not done

- **P4-04 已实现（混合式）**：`evolution/propose.py` 用规则挖两类机会——①近 5 条 trace 内复发的失败类（旧的已修复簇会被 recency 过滤掉）；②占语料墙钟 ≥40% 且中位 ≥2s、且调用来自 ≥2 个工单的工具。**knob、验收阈值、风险红线由代码给定，LLM 只能写 hypothesis/risk 两句**，因此同一语料两次提案除措辞外一致；spec 落盘前必过 `validate_spec`，重复机会不再生成（幂等）。首个产出 `auto-latency-share-screening-rank` 已被实测否决（见 §7），随后 **当日真实失败自动生出两个失败类候选**（`auto-failure-recurrence-rdkit-featurize-61c653` / `-f80739`，待 Intake）。单测 12 个（`test_propose.py`），evolution 合计 28/28；语料 22 条 / 73 步。

- **Engine pass 已验证**（`src/research/engine-pass.ts` + `orchestrator_report` 事务后钩子）：真实 Ticket `engine-check-exact-27505612356f` 在 Agent 未调用评测工具的前提下产生 `engine_receipt.json`（MOR/Ki/v1，AUROC 0.9339），见 §7.1；8 个单测 + runtime 91/91 + research 13/13。
- **P5-03 未整合**：四类硬门禁（科学质量/成本/成功率/安全）仍散在各候选的 `acceptance` 里。
- **P5-04 / P5-05 未做**：无 Pareto 集（balanced/lite/heavy），无 VersionManager（晋升/回滚=改默认值 + JSON 记录 + git SHA 兜底）。
- **F-1…F-4 已完成**（见 §6）；`pnpm typecheck` / `build` / `tests/research.spec.ts` 13/13 通过。
- **D-1 / D-2 已完成**（见 §8）；`evolution` 单测 24/24，语料按 schema v2 重导、聚类重新出具。
- 语料 20 条仅达门槛；聚类尚无可操作结论。
- B-002（上游 Feishu 用例）仍失败，与本阶段无关；B-006（令牌轮换）仍待操作者执行。

## 10. Next（修订后的顺序）

1. ~~F-1…F-4：修端点参数与输出名，重跑 IC50-descv2 验证面~~ ✅ 已完成（2026-11-06 03:10）；
2. ~~D-1：trace 补 stderr 文本~~ ✅ 已完成（2026-11-06 03:20）；~~D-2 经验 payload~~ ✅ 已完成；
3. ~~**Engine pass**：评测自动触发，闭环脱离人工调用~~ ✅ 已实现（2026-11-06 03:15），待真实 Ticket 确认；
4. ~~**P4-04**：从 trace + 失败簇自动产候选~~ ✅ 已实现（2026-11-06 03:30，混合式），首个提案待 Intake；
5. P5-03 统一硬门禁 → P5-04 Pareto → P5-05 VersionManager。

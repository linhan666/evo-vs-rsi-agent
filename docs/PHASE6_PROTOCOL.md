# PHASE6_PROTOCOL — 四组对照实验（发表用）

> 目标：回答蓝图的核心主张——「RSI 让 Harness 比其它策略更会改自己」。没有对照，这只是一个个案。
> 产出：一张对照表 + 一组 trace 指标，可直接进论文的实验节。

## 1. 分组（同一批任务、同模型、同预算）

| 组 | 含义 | 差异点 |
|---|---|---|
| **Workflow** | 无 Harness，纯 LLM 直接做任务 | 只有 `python -m` 命令，无工具注册表、无沙箱作业记录 |
| **Fixed** | Harness 冻结在 Phase 5 结束时的代码，不跑进化 | 有工具/沙箱/锁定评测，但 `propose`/`record` 关闭，不允许任何自改 |
| **Memory-only** | 只开经验库（`experience.retrieve`），代码冻结 | 比 Fixed 多「读得懂自己以前踩过的坑」，仍不许改自己 |
| **RSI** | 全量自改循环 | 提案→影子→门禁→记账 全开 |

四组共用：同一模型与温度、同一任务集、同一 `EVOVS_DATA_ROOT`、同一每工单 token/墙钟预算、同一成功判据。

## 2. 任务集（建议 6 个，覆盖已知失败面）

| # | 任务 | 考的是什么 |
|---|---|---|
| T1 | 对 ChEMBL Ki 数据集建 MOR 模型（featurize→train→report） | 列名别名、路径解析 |
| T2 | 同上但给 IC50 通道 | 端点区分、输出命名 |
| T3 | 用训练好的模型筛 100k 库并出 top-100 | 模型路径、长耗时作业 |
| T4 | 只要求 featurize（故意给 `canonical_smiles` 表头） | 列名解析能否自动生效 |
| T5 | 给一个不存在的路径，要求报错可读 | 早失败与提示质量 |
| T6 | 读经验库并给出「上次踩过的坑」 | Memory/RSI 是否真的用了记忆 |

T5 的失败是**故意的**：测的是错误信息质量，不是成功率。

## 3. 指标（全部从 trace 读，不用模型自评）

| 指标 | 定义 | 脚本 |
|---|---|---|
| 成功率 | `report=ready` 的工单占比 | `evolution/metrics.py`（需配 report 元数据） |
| 失败重试数 | 每工单失败步数（均值/总计） | 同上 |
| 每工单墙钟 | step wall_seconds 求和 | 同上 |
| 失败类消除 | 相对 Fixed 组，后期 trace 里不再出现的失败类 | 同上（`--baseline fixed`） |

**主结论看后两项**：RSI 组的失败类消除数应当显著高于其它组；失败重试数应当更低。成功率与墙钟是约束（RSI 不应靠牺牲成功率换速度）。

## 4. 规模建议

| 项 | 建议 |
|---|---|
| 每组每任务重复 | **3 次**（LLM 非确定性，1 次不足） |
| 总工单 | 4 组 × 6 任务 × 3 = **72** |
| 先导 | 4 组 × 1 任务 × 1 = **4** 个工单，验证链路与指标脚本 |
| 预算 | 每工单 ~3–6 分钟、数千 token；72 个约 4–7 小时墙钟，需分批 |

## 5. 运行顺序

1. 每组起一个独立 state 目录（`EVOVS_STATE` 分开），避免组间污染；
2. 投任务 → 轮询 → 收 trace（`ops/sync_traces.py`）；
3. `python evolution/metrics.py --group rsi=... --group fixed=... --baseline fixed --output phase6.json`；
4. 出表，统计显著性（每组 n=18，Wilcoxon 或 bootstrap CI）。

## 6. 已知风险

- **组间任务难度不可比**是致命伤 → 必须同任务集、同随机种子；
- **Workflow 组无 trace** → 需在任务层记录墙钟与重试，否则该组只能比成功率；
- **LLM 非确定性** → 每格 ≥3 次；
- **B-002 上游竞态** 不影响本实验（Feishu 不参与）。

## 7. 前置项（已完成，2026-11-06）

| 前置 | 落地 | 用法 |
|---|---|---|
| 组开关 | `EVOVS_GROUP` + `toolsForGroup()`；`fixed` 隐藏 `experience.retrieve` | 每组独立 state 目录 + `EVOVS_GROUP=<workflow|fixed|memory|rsi>` 起服务 |
| 成本埋点 | `ops/usage_hook.cjs`（`NODE_OPTIONS=--require`，从 fetch/http 响应里抄 usage）+ `ops/cost_report.py` 计价 | 起服务前 `export EVOVS_USAGE_LOG=$PWD/scientific/.artifacts/usage.jsonl`，跑完按窗口聚合 |

已冒烟验证：mock 响应 → ledger 记下 `prompt_tokens/cached/completion` → 计价 ¥0.0011（闲时）。trace 导出时自动盖 `group` 戳。

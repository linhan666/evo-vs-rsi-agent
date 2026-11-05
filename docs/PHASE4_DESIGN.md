# PHASE4_DESIGN — Harness 自修改闭环：Intake/Evaluator 循环与影子评估（P4-01/02）

> 预注册文档：评估口径与晋升门禁在候选运行前锁定。所有候选**只在影子评估中运行**，永不直接改动线上 Harness。

## 1. 角色与循环

```
真实 Ticket（经验来源）
   │  trace_export
   ▼
Trace 语料（.jobs 序列 + 工件 digest）
   │
   ├─ Intake：候选以 CandidateSpec(JSON) 进入，schema 校验 + 风险声明
   ▼
Shadow Evaluator：在沙箱目录按 trace 重放候选工具链，比对工件 digest 与耗时
   │
   ▼
报告 → operator 审阅 → 晋升门禁（人工）→ 线上 lib（freshness gate + 金丝雀）
```

- **Intake**：候选 = `CandidateSpec`（JSON：id、changes、hypothesis、acceptance、risk）。入库不判优劣。
- **Evaluator**：无 LLM、确定性重放。工件等价性按类型校验（见 §3）；耗时纳入 acceptance。
- **晋升**：**永远人工**。operator 依据影子报告修改 registry/实现 → freshness gate → 重启 → 金丝雀 → 真实 Ticket 冒烟。影子报告是唯一依据，金丝雀/freshness 是唯一执行闸门。

## 2. Trace 语料

- 来源：真实 Ticket 的 `.jobs/*/result.json`（含 argv、工件 sha256、耗时）+ 各工件文件本体（digest 重算）。
- 导出器：`evolution/trace_export.py` → `trace.json`（steps 按 started_at 排序）。
- 现有语料：science_007（featurize → ml.train → screening.rank 全链）、science_008/010/011/012。语料随真实 Ticket 增长。

## 3. 工件等价性规则（预注册）

| 工件类型 | 比较方式 | 原因 |
|---|---|---|
| `.npz` | 数组内容 digest（按变量名排序：shape + dtype + 字节） | np.savez 的 zip 容器带时间戳，文件级 sha256 不稳定 |
| `.json` | 语义比较：剔除 `created_at/started_at/ended_at/elapsed_seconds` 后的规范 JSON | 时间戳字段天然不同 |
| `.joblib/.csv/.smi/其它` | 字节级 sha256 | 应当确定性 |

非确定性工件若字节不等 → 按上述规则降级为语义比较；仍不等 → 记 mismatch（候选不可晋升，除非 operator 明示接受并记录理由）。

## 4. 首个候选（candidate1-featurize-parallel）

- **动机（来自真实轨迹）**：100k 库特征化是全链最慢步（83.6s），而 Morgan 指纹逐分子计算天然可并行且结果确定性不变。
- **变更**：`chemistry/featurize.py` 引入 `EVOVS_FEAT_JOBS=N`（默认 1 = 基线路径；分块 + `multiprocessing.Pool`，块内顺序保持，结果按原序拼接——**单一代码路径**，并行只是调度差异）。
- **CandidateSpec**：`evolution/candidates/candidate1_featurize_parallel.json`。
- **acceptance（预注册）**：工件等价率 = 100%；耗时比（candidate/baseline）≤ 1.2；featurize 重步骤加速 ≥ 2×。
- **影子集**：science_007 trace 的 featurize（2,790）与 screening.rank（100k）两步；基线与候选各跑一遍。

## 5. 红线

1. 影子重放只在沙箱目录写入（`--sandbox`），禁止触碰 ticket 原目录与 protected；
2. 候选永不直接修改 `src/`/`lib/`——晋升由 operator 手工执行；
3. 语料 trace 只增不改；比较函数 determinism 规则改动 = 口径修订，须新增经验记录。

## §3 修订记录（运行中发现的规则缺陷，已按红线 3 记录）

1. **npz object 数组**：`tobytes()` 走 pickle，跨机器对相同内容编码不同（实证：ids 数组元素逐一相等但字节不等）→ object 数组改哈希**规范化字符串**。
2. **json 派生字段**：`artifact_manifest.json` 内嵌其它工件的文件级 `sha256`（npz 容器相关）→ 语义比较剔除 `sha256` 键（这些工件各自有独立等价校验，无信息损失）。
3. **派生清单排除**：`artifact_manifest.json` 本身是其余工件的索引 → 从等价集排除（报告单独计数 `derived_skipped`）。

## 6. 验收（Phase 4 第一片的 Gate 4-a）——**已通过（2026-11-05 23:55）**

trace：science_007（featurize → ml.train → screening.rank，真实 Ticket）。沙箱重放双跑：

| 步骤 | trace 基线 | 重放基线 | candidate1 | 加速（重放内对比） |
|---|---|---|---|---|
| rdkit.featurize（2,790） | 2.31s | 3.74s | **1.09s** | **2.1×** |
| ml.train | 3.54s | 8.63s | 7.97s | （非 featurize-heavy；机器噪声） |
| screening.rank（100k） | 69.35s | 65.52s | **19.90s** | **3.3×** |

- **等价率 = 1.0**（8/8 独立工件；3 个派生清单排除计数）
- acceptance：等价率 1.0 ✓；featurize-heavy 时间比 ≤1.2 ✓；加速 ≥2× ✓ → **candidate1 影子验收通过**
- ml.train 重放慢于 trace 基线是跨机冷缓存差异（.26 记录 vs .37 重放），与候选无关
- digest 规则单测 5/5；证据：`docs/evidence/phase4/`（trace + 双报告）

- trace_export 对真实 ticket 导出成功且 digest 可复算；
- candidate1 影子重放：等价率 100%、加速 ≥ 2×（或如实报告未达标）；
- 全部测试绿（60/61，唯一失败仍为 B-002）。

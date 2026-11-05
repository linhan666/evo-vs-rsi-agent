# PHASE4_REPORT — Harness 自修改闭环（Intake → 影子评估 → 晋升/拒绝）

> 覆盖蓝图 **P4-01/02/03/05/06** 与 **P5-01/02/05/06**（项目把蓝图 P4/P5 合并为"项目 Phase 4"）。
> 本阶段无新外部依赖；服务全程停止，所有动作是 operator/CLI 级执行 + 真实 Ticket 冒烟。
> 设计口径预注册在 `docs/PHASE4_DESIGN.md`，本报告只记录**实际发生了什么**。

## 1. 交付物

| 组件 | 作用 |
|---|---|
| `evolution/trace_export.py` | 从真实 Ticket 的 `.jobs/*/result.json` 导出 `trace.json`（argv + 工件 sha256 + 耗时 + exit_code） |
| `evolution/artifacts.py` | 工件等价性比较（按类型分派：npz 内容 digest / json 语义 / 其余字节 sha256） |
| `evolution/shadow.py` | 沙箱重放器：同一 trace 跑基线与候选，产出等价率与耗时报告 |
| `evolution/spec.py` + `test_spec.py` | **Intake 硬化**：`validate_spec()` 拒绝畸形候选；`shadow.py` 对无效 spec 拒跑 |
| `evolution/candidates/*.json` | 候选 spec（baseline、c1 已晋升、c2 已拒绝、c3 裁决不上线、c4 通过并入 IC50 面板） |
| `docs/PHASE4_DESIGN.md` | 预注册口径：角色循环、等价性规则、红线、晋升门禁 |

## 2. 候选 1：featurize 分块并行（**首个真实晋升**）

**动机来自真实轨迹**：science_007 的 100k 特征化是全链最慢步（83.6 s），而 Morgan 指纹逐分子可并行、结果确定性不变。

**实现**：`chemistry/featurize.py` 引入 `EVOVS_FEAT_JOBS`（默认 1 = 串行基线），分块 + `multiprocessing.Pool`，块内保序、按原序拼接——**单一代码路径**，并行只是调度差异。

**影子验收（science_007 trace，沙箱重放：基线跑一遍、候选跑一遍）**

| 步骤 | trace 记录 | 基线重放 | 候选重放 | 加速（vs trace / vs 基线重放） | 工件等价 |
|---|---|---|---|---|---|
| `rdkit.featurize`（2,790） | 2.31 s | 3.74 s | **1.09 s** | **2.1× / 3.4×** | 2/2 |
| `ml.train` | 3.54 s | 8.63 s | 7.97 s | —（非 featurize-heavy，跨机冷缓存噪声） | 3/3 |
| `screening.rank`（100k） | 69.35 s | 65.52 s | **19.90 s** | **3.5× / 3.3×** | 3/3 |

> 口径说明：`PHASE4_DESIGN.md` 的"重放内对比"列在 featurize 用了 trace 记录（2.31/1.09）、在 screening 用了重放基线（65.52/19.90），两处基准不一致。本报告把两个基准都列出，避免读者对"2.1×"与"3.3×"的基准产生误解。

- **等价率 = 1.0**（8/8 独立工件；1 个派生清单排除计数）
- acceptance 三条全过：等价率 1.0 ✓ / featurize 时间比 ≤1.2 ✓ / 加速 ≥2× ✓ → **Gate 4-a 通过（2026-11-05 23:55）**

**晋升（2026-11-06 00:45–00:47，全门禁）**

影子 pass → operator 批准 → 默认 `1 → 8` → freshness gate ✓ → rebuild ✓ → 金丝雀 ✓ → **生产冒烟 science_013（真实 Ticket，默认路径不带任何环境变量）`rdkit.featurize` 1.08 s（串行 3.7–3.9 s）**，Agent 回复 "2790 molecules featurized." → 经验库 `harness_HARNESS_013`。
**回滚**：默认值改回 `"1"` 即回到基线（单代码路径，无分支残留）。

## 3. 运行中修掉的 3 个 digest 规则缺陷（按红线 3 记为口径修订）

| # | 现象 | 修订 |
|---|---|---|
| 1 | npz 里 object 数组 `tobytes()` 走 pickle，跨机同内容编码不同（ids 逐元素相等但字节不等） | object 数组改哈希**规范化字符串** |
| 2 | `artifact_manifest.json` 内嵌其它工件的文件级 sha256（依赖 npz 容器时间戳） | 语义比较剔除 `sha256` 键 |
| 3 | `artifact_manifest.json` 本身是其余工件的派生索引 | 从等价集排除，报告单列 `derived_skipped` |

单测 5/5；**教训**：比较规则改动后必须重导 trace，否则 trace 与规则不同版本（已写入设计文档）。

## 4. 候选 2：pooled 重校准 → **被预注册规则拒绝**

- 假设：pooled 训练里把 MOR 降权（`pool.py --weights MOR:0.5`）可消除 §12 记录的负迁移。
- 实现 knob 后影子实跑：**MOR Δ 从 −0.0468 恶化到 −0.0614（CI 全负）**，KOR/DRD2 未获补偿。
- 判定：`status = rejected`，理由与影子结果入 spec 与经验库（`transfer_MOR_014/015/016`）。
- **结论**：跨靶点干扰是结构性的，**per-target 是安全默认**；不是调权重能解决的问题。

## 5. 评测器垫片：`evaluation.locked`（第 5 个工具）

worker 已无 shell（B-005 替代方案），原设计里的"外部垫片进程"无法执行，于是实现为**注册工具**，但保持等价能力边界：

- Agent 只传 `target` + `model`，测试集路径与输出路径**硬编码**；原始指标落 `protected/`（600），Agent 只拿到 receipt 摘要（指标 + 模型/测试集 sha256）。
- **每 Ticket 每靶点限频**，防止反复试探最终测试集（蓝图 §11.7）。
- 生产验证 **science_014**（DRD2 全链 + 自主触发）：回复 "validation AUROC 0.9214; locked-test AUROC 0.9015" —— 与 operator 模型完全一致。

## 6. Intake 硬化（P4-03 的最小可行部分）

`validate_spec()` 校验：必填字符串字段、`changes[].type ∈ {env, experiment}`、`key` 非空、`value` 必须存在、`acceptance.equivalence` 必须存在、`status ∈ {proposal, shadowed, promoted, rejected}`。
`test_spec.py` 4/4（含"拒绝 shell 类型变更""拒绝未知 status"）。**无效 spec 永远到不了沙箱**。

## 7. 缺陷与教训

| 缺陷 | 处理 |
|---|---|
| 3 个 digest 等价规则缺陷（见 §3） | 已修，规则 + 单测 + 文档同步 |
| 本机 Windows 用 Python 脚本改远端文件：CRLF + 缩进漂移导致锚断言静默失败两次 | 改用精确文本替换工具；**大文件/多字节内容一律走 ops 脚本文件，不走 shell heredoc** |
| `baseline.json` 的 `verdict.pass = false`（重放比 trace 慢 1.62×） | 属预期：基线自己与自己比不该过时间比；报告里只作参照列 |

## 8. Known failures / not done

- **P4-04 未做**：候选 1–4 全部由 operator 侧撰写 spec，**没有**"Evolution Agent 读 trace 自动提候选"。这是 RSI 主张最硬的缺口。
- **P4-03 只到 schema 校验**：没有独立候选 worktree，也没有 allowlist 级 patch validator。
- **P5-03 未整合**：科学质量/成本/成功率/安全四类硬门禁仍散落在各候选的 `acceptance` 里，没有统一 gate。
- **P5-04 未做**：无 balanced/lite/heavy Pareto 集。
- **P5-05 未做**：无 VersionManager，晋升/回滚是"改默认值 + 写 JSON 记录 + git SHA 兜底"。
- **Engine pass 只有草案**：评测器尚未由 Harness 在 report 阶段自动触发（草案见 `docs/EVALUATOR_TRIGGER_DESIGN.md`）。
- B-002（上游 Feishu 用例）仍失败，与本阶段无关。

## 9. Next

1. 文档一致性补齐（README/PROJECT 阶段标注 + 本报告 + Phase 5 报告）；
2. **Engine pass**：让评测在 report 阶段自动触发，闭环脱离 Agent 主动调用；
3. **P4-04**：从 trace + 失败聚类自动产候选（Phase 6 四组对照的前提）；
4. 统一硬门禁（P5-03）→ Pareto 集（P5-04）→ VersionManager（P5-05）。

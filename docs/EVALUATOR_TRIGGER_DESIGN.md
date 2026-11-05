# EVALUATOR_TRIGGER_DESIGN — 锁定评测的触发方式（Phase 4 前设计项，2026-11-05）

> 问题：锁定测试标签只有独立评测器能读（P2-04）。现在由 operator 手动触发；Phase 4 起需要"Ticket 流程可触发、但 Agent 仍读不到标签"的机制。本文比较三条路并给出推荐。

## 候选方案

### 方案 1：operator 手动（现状）

- 流程：Agent 报告完成 → operator 在服务器跑 `evaluation.evaluate` → 结果留在 protected 目录。
- 优点：零新攻击面。
- 缺点：不自动化；operator 是瓶颈；轨迹里评测与建模断开（需要人工把两者关联）。

### 方案 2：受批准的命令垫片（worker-bin 内的白名单 shim）★ 推荐（Phase 4 落地用）

- 在 `<stateDir>/worker-bin/evaluate-locked` 放一个垫片：**只**接受 `--model <file>` 与 `--ticket <id>` 两个参数，内部以固定参数调用评测器（测试集路径、输出路径都是写死的 protected 路径），拒绝任何其它参数。
- 关键性质：**Agent 能触发评测，但读不到标签，也改不了评测参数**。评测输出 600 权限写在 protected 目录，Agent 不可达；它只会从回复/通知里拿到指标摘要。
- 与上游机制兼容：worker-bin 本来就是"受控命令垫片"目录（`gh`/`lark-cli` 同模式）；`docs/003` 规定垫片自带来源校验（foreignFile 检查），垫片必须由 dsh-superagent 写入——实现时通过 blocked-commands/写环境路径注入，而不是手工放文件。
- 风险：Agent 可以**频繁触发**评测（资源骚扰）→ 垫片内加每 Ticket 一次的限频（状态记在 ticket 目录）。

### 方案 3：Orchestrator 侧 pass（最终形态）

- Engine 在 Ticket 进入 report 阶段且检测到模型工件时，由 orchestrator（不是 worker）发起评测，把指标作为 notice 回帖。
- 优点：全自动化、worker 完全不接触评测；缺点：需要改上游执行器/Engine（P0 审计定位过 `executor/dsh.ts` 的 report 钩子），侵入大，必须等 B-005 隔离到位、并有足够的测试覆盖后做。

## 推荐

- **现在**：维持方案 1（operator 手动）——本阶段所有评测都是单次、低频。
- **Phase 4 开始时**：实现方案 2（垫片 + 限频），作为"Agent 自治"与"标签隔离"的兼容点。
- **Phase 5（自修改闭环）**：迁移到方案 3。

## 方案 2 已实现（2026-11-06 00:15，适配说明）

**适配**：worker 无 shell（B-005 后裁剪），垫片从 worker-bin 脚本改为**注册工具** `evaluation.locked`——能力等价：
- Agent 只传 `target`（MOR/KOR/DRD2）、`endpoint`（Ki/IC50）、`desc_set`（v1/v2）与 `model`（workspace 内相对路径）；**测试集与输出位置按 (target, endpoint) 硬编码**在 `evaluation/locked.py`；
- 原始指标 600 写 protected（agent 不可达）；Agent 只拿到 workspace 内的 receipt 摘要（允许的"摘要数字"）；
- **限频**：每 Ticket 每 (target, endpoint) 一次（`.evaluation/<target>_<endpoint>.done` 标记）；
- 生产验证：science_014（Ticket `26cf2e58…`）——Agent 训练 DRD2 模型后自主触发，回复 "validation AUROC 0.9214; locked-test AUROC 0.9015"（与 operator 一致）。

> **2026-11-06 修订（F-1/F-2）**：初版把测试集写死成 `final_test_Ki.csv`、且没有 endpoint 参数，导致 IC50 通道的工单实际是"IC50 模型 vs Ki 标签"的跨端点错配；同时输出名依赖 `basename(workspace)`，多通道用 `.` 调用时会互相覆盖。现已加 `--endpoint {Ki,IC50}`（映射到各自 protected 目录与测试集），输出名改为
> `metrics_test_locked_agent_{endpoint}_{desc_set}_{ticket}_{target}.json`。详见 `docs/PHASE5_REPORT.md` §6。

### 方案 3 实现（2026-11-06，Engine pass 已落地）

- **触点**：orchestrator 工具 `orchestrator_report` 的 `execute` 里，`host.store.atomic(...)` **事务提交之后**，若 `state === 'ready'` 则 `void runEnginePass(ticketDir, EVOVS_PYTHON)`——不阻塞回帖，事务内不做异步 I/O。
  （草案原定点是 `src/executor/dsh.ts` 的 report 段；那是 Engine 内部状态迁移，异步副作用更难隔离。工具层"事务后钩子"能力等价且侵入更小，故改此处，`docs/ARCHITECTURE.md` 的"最小侵入"原则不变。）
- **计划推导**（`src/research/engine-pass.ts`，纯函数 `planEnginePass`）：读该 Ticket 自己的 `.jobs/*/result.json`，取**最新一个 SUCCEEDED `ml.train`**，从 argv 的 `--labels`（`.../chembl/<oprm1|oprk1|drd2>/<ki|ic50>/...`）与 `--label-source` 推出 target / endpoint / desc_set，从 artifacts 取 `model.joblib`。**不解析 Agent 的自然语言**。
- **复用同一垫片**：调用 `evovs_science.evaluation.locked`，因此测试集、protected 输出路径、限频标记与 Agent 主动触发完全一致——**同一 Ticket 同一 (target, endpoint) 只会评一次**，先触发者赢。
- **失败隔离**：`runEnginePass` 永不抛错（返回 `{ran:false, reason}`），调用处也不 await；评测出问题只影响收据，不会把已完成的 Ticket 变成失败。
- **测试**：`tests/engine-pass.spec.ts` 8/8（target/endpoint/desc_set 推导、取最新成功作业、未知靶点拒绝、标记共享、无解释器与重复触发的短路）；`runtime.spec.ts` 91/91、`research.spec.ts` 13/13。
- **尚未验证**：需要一次真实 Ticket 才能确认端到端（下一次工单顺带确认 `runs/evaluation/engine_receipt.json` 落盘）。

## 无论哪条路都不变的三条红线

1. 评测器是唯一读最终测试标签的组件；
2. 评测输出（含指标）对 Agent 的可见性仅限"通知里的摘要数字"，原始文件永远 600 + protected；
3. 评测记录必须带 model sha256 与测试集 sha256（已实现），否则不承认评测结果。

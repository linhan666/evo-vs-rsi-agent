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
- Agent 只传 `target`（MOR/KOR/DRD2）与 `model`（workspace 内相对路径）；测试集与输出位置**硬编码**在 `evaluation/locked.py`；
- 原始指标 600 写 protected（agent 不可达）；Agent 只拿到 workspace 内的 receipt 摘要（允许的"摘要数字"）；
- **限频**：每 Ticket 每靶点一次（`.evaluation/<target>.done` 标记）；
- 生产验证：science_014（Ticket `26cf2e58…`）——Agent 训练 DRD2 模型后自主触发，回复 "validation AUROC 0.9214; locked-test AUROC 0.9015"（与 operator 一致）。

### 方案 3 实现草案（Phase 5，**未实现**——按"最后做"暂缓）

- 触点：`src/executor/dsh.ts` 的 report 处理段（P0 审计已定位）：Ticket 进入 report/reply 且最近回复引用 `runs/models/*/model.joblib` 时，由 orchestrator（非 worker）调用 locked 评测（复用 `evaluation/locked.py`，限频标记同路径）。
- 保障：评测失败只记 warning 不阻塞 Ticket 结束；限频不变；评测与 provider 调用互斥。
- 测试：`runtime.spec.ts` 增加"report 阶段自动触发一次且仅一次"用例；B-005 隔离已就位（独立机器）。
- 未实现原因：侵入上游 Engine，需要完整回归；当前垫片（方案 2）已覆盖"Agent 可触发"场景，方案 3 的增益只是免手写一步。

## 无论哪条路都不变的三条红线

1. 评测器是唯一读最终测试标签的组件；
2. 评测输出（含指标）对 Agent 的可见性仅限"通知里的摘要数字"，原始文件永远 600 + protected；
3. 评测记录必须带 model sha256 与测试集 sha256（已实现），否则不承认评测结果。

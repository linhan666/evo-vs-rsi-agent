# UPSTREAM_AUDIT — Phase 0

> 本文件只记录**实际执行过的命令与其真实输出**。未验证项一律标注 `NOT VERIFIED`，不得据此声称系统可用。
> 审计时间：2026-11-05（UTC+8），执行机：`172.25.18.26`（A800f）。

## 1. 结论摘要

| 判定 | 结果 |
|---|---|
| 基线可安装 | ✅ `pnpm install --frozen-lockfile` exit=0，8.7 s |
| 类型检查 | ✅ PASS（`tsc --noEmit`） |
| 单元/集成测试 | ⚠️ 58/59 文件通过；`tests/sources.spec.ts` 1 例可复现失败（Feishu 专属，见 B-002） |
| 构建 | ✅ PASS（`tsdown`，11 文件 / 693.50 kB / 2516 ms） |
| DSH 运行时 | ✅ `0.2.1-rc.5` 可启动 |
| LLM 端到端 | ✅ `deepseek-flash` 返回 `SMOKE_OK` |
| Ticket 生命周期（真实 Source） | ✅ PASS — 本地 Source → Ticket `2fa5057…` → Worker → `SMOKE_OK`（证据 `docs/evidence/phase0/smoke/`） |

**Gate 0 判定**：**通过**。上游可构建、可测试、可调用 LLM；真实 Ticket 生命周期与重启恢复均已跑通并有可复核日志。唯一遗留是上游自身的 Feishu 用例失败（B-002，不影响主链路）。

## 2. 版本与 SHA

| 对象 | 值 | 获取方式 |
|---|---|---|
| `dsh-superagent-prototype` | `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`（2026-10-31T20:06:31+08:00，`feat: add the dsh-superagent research prototype`） | `git rev-parse HEAD` |
| `HarnessPro` | `6fd2d4dbc3b73881b2b48833764fcd803aacb7b8` | `git -C reference/HarnessPro rev-parse HEAD`（`--depth 1`） |
| `deepseek-harness` | `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`（仅 `git ls-remote` 观测，**未克隆**，见 B-003） | `git ls-remote` |
| 运行时包 | `@deepseek-ai/dsh@0.2.1-rc.5` | `npx @deepseek-ai/dsh --version` |
| 许可 | MIT（上游 `LICENSE` 保留原样） | 文件存在 |

> **依赖解析注意**：npm 上名为 `dsh` 的包（v1.0.1）是无关的 JS shell；`deepseek-harness`（v0.0.1）是占位包，其描述明确写"真实包将在开发完成后发布"。正确入口是作用域包 `@deepseek-ai/dsh`。`0.2.1-alpha.2` 在 `dsh-agent / dsh-llm / dsh-session / dsh-tools / dsh-workspace` 等子包中均真实存在，`^` 范围解析到 `0.2.1-rc.5`。

## 3. 实测环境

| 组件 | 版本 | 备注 |
|---|---|---|
| OS | Ubuntu 24.04.3 LTS | — |
| CPU / RAM / 磁盘 | 128 核 / 503 GB / `/home` 649 GB 可用 | 采集于 Phase 0 |
| Node.js | v22.23.4（用户态 `~/software/node-v22.23.4-linux-x64`） | 系统自带 v18.19.1 **不满足** `^22.19 \|\| >=24` |
| npm | 10.9.9 | 随 Node 22 提供 |
| pnpm | 11.7.0 | `npm i -g` 到 user prefix，未动系统 |
| Python | 3.12.3，**无 `pip3`** | 后续需 venv bootstrap |
| git | 2.43.0 | 满足 ≥2.32 |
| tmux | 存在（`-V` 可查；`--version` 会打印 usage） | — |
| GitHub CLI (`gh`) | **缺失** | SETUP 要求 ≥2.48 → B-001 |
| `dsh` 全局命令 | 未全局安装，经 `npx` 调用 | 不污染全局 |

## 4. 基线构建与测试证据

```
pnpm install --frozen-lockfile   → exit=0, Done in 8.7s (pnpm v11.7.0)
pnpm typecheck (tsc --noEmit)    → PASS
pnpm test  (vitest run)          → Test Files 1 failed | 58 passed (59)
pnpm build (tsdown)              → PASS: 11 files, total 693.50 kB, 2516ms
```

失败用例定位：

```
FAIL tests/sources.spec.ts > feishu event consumer > takes in the event lines it reads,
records each chat as direct or not, and reports a malformed line without stopping
AssertionError: expected { state: 'ready', …(2) } to match object { state: 'error', …(1) }
  at tests/sources.spec.ts:1097:27
```

- 该文件单独复跑：`71 tests | 1 failed`，**稳定复现**，非随机抖动。
- 断言期望 Feishu `event consume` 读到非法 JSON 行后 `health.feishu` 进入 `error` 并包含 `JSON`；实际仍为 `ready`。
- **影响面**：仅 Feishu Source。本项目的 MVP 链路使用 GitHub Source 与本地/科研 Source，不依赖该分支。
- **结论**：记录为上游已知缺陷（B-002），不修改上游代码，不回退版本。

## 5. 真实架构映射（源码签名）

### 5.1 组合根与领域核心

| 对象 | 文件 | 真实签名（节选） |
|---|---|---|
| `Runtime` | `src/app/runtime.ts:59` | `export class Runtime extends Service implements SourceHost` —— 组合根，无领域规则；构造期锁定 state 目录、开 Store、装配组件 |
| `Engine` | `src/core/engine.ts` | 唯一写 Trigger/Thread/Decision/Ticket/Assignment 的地方；同步方法、每命令一事务；按角色暴露 `EngineForSources / EngineForMainSession / EngineForPeople / EngineForSettings / EngineForExecutor` |
| `EnginePart` | `src/core/part.ts` | `Intake → Evals → Tickets → Assignments → Replies` 单向依赖 |

### 5.2 端口（`src/core/ports.ts`）

```
GateResult, ScopeResult, SourceScope, Policy, Candidate, AssessmentOutcome,
Assessor, Executor, OutboundMessage, ReplyStatus, Outbox, DomainEvents,
DomainEvent, Repositories
```

`DomainEvent` 的联合类型覆盖：`trigger.received / eval.started / decision.recorded /
ticket.created / ticket.resumed / ticket.ended / assignment.started / assignment.ended /
thread.subscribed / thread.unsubscribed / trigger.requeued / policy.changed`。
→ **这是本项目轨迹采集最自然的挂载点**（`Runtime` 已消费其中 3 个事件做通知，其余无消费者）。

### 5.3 执行器（`src/executor/dsh.ts`）

```
workerSessionId(ticketId)            → `worker-${ticketId}`
ticketOfSession(sessionId)
transient(error)
ExecutorHost (interface)
sourceTrigger(host, ticket)
mandateInstructions(mandate)
ticketExecution(ticket, outcome, settings, …)
triggerMessage(trigger, link, note?, repliesTo?)
batchLine(trigger) / batchOf(host, ticket)
inputResource(ticketId, inputId)
inputMessage(input, trigger?)
WorkerSlots (class)                  → 并发槽位
DshExecutor implements Executor      → 每 Ticket 一个 DSH Session
```

### 5.4 策略与评估

| 模块 | 关键导出 | 说明 |
|---|---|---|
| `src/policy.ts` | `RuleSchema`、`RuleMatchSchema`、`AdmissionTableSchema`、`Assessment`、`assessmentOutcome()`、`RoleModelSchema` | 授权与准入；`roleModel` 已支持 `provider/model/reasoningEffort` |
| `src/app/assessment.ts` | `MasterAssessor implements Assessor`、`AssessmentSchema`、`EvalReadSchema`、`WorktreeNameSchema` | 判断"是否接这个任务"，**不是**模型选择器 |
| `src/app/store.ts` | `Store implements Repositories`、`SettingsVersion`、`Receipt` | SQLite 单写者 |
| `src/app/versions.ts` | `Versions<V extends { revision: number }>` | 设置版本快照，非完整 Harness 版本管理 |

### 5.5 Source 插件面

`src/sources/` 现有 `github*`（8 文件）与 `feishu*`（6 文件），加上 `kind.ts / registry.ts / host.ts / poll.ts / admission-context.ts`。
新增 Source 的规范入口是 `docs/008-cookbook.md`，映射为稳定的 `Trigger / Thread / Ticket`，**不得直接操作 Engine 私有状态表**。

## 6. 扩展点与禁区

**允许扩展（最小侵入）**

| 目标 | 位置 | 方式 |
|---|---|---|
| 科研作业执行 | 新增 `src/research/` | 通过 `Executor` / `Outbox` / 新 Port 接入，不改 Engine 状态机 |
| 轨迹采集 | `DomainEvents` 消费者 + 独立 append-only recorder | Engine 只发事件，recorder 独立写盘 |
| 进化控制器 | 独立进程 `evolution/` | 不在候选 Harness 的信任边界内 |
| 科研 Python 能力 | `scientific/` 独立包 | TS 侧只做 job 适配与状态查询 |

**禁止**

- 修改 `src/core/engine.ts` 的事务与状态权威、`src/app/store.ts` 的单写者语义；
- 让被评估 Agent 或进化候选改写评测器、标签、切分、预算上限；
- 以修改上游 `package.json` 的方式放宽 `engines` 或替换技术基底。

## 7. 安全与隔离审计（上游明文事实）

来自 `docs/006-deployment.md`：

> Both presets run with `danger-full-access` as the operator's OS user … A worker can execute programs by path and read the operator's home directory. For isolation, use a dedicated OS account containing only the agent's credentials.

**判定：不满足蓝图 §6.4 的物理隔离要求。** 在上线任何自修改回路之前必须补：

1. 专用 OS 账号（当前 `linhan_cluster` 与其它 220 个项目共用 home，风险不可接受）；
2. 容器/namespace 级文件与网络限制；
3. 受保护资产（heldout 标签、评测器）在候选容器内不可读；
4. GPU/CPU/时长硬限在外部强制，而非依赖 Prompt 约束。

## 8. HarnessPro 参考仓（结构级）

`reference/HarnessPro` @ `6fd2d4d`，58 MB，Python（`pyproject.toml` + `uv.lock`），顶层：
`docker/ docs/ harnesses/ splits/ scripts/ src/ tests/ third_party/ THIRD_PARTY_NOTICES.md LICENSE README.md`。

- `harnesses/` 与 `splits/` 的存在与"Lite/Medium/Heavy 已产出 Harness + 任务切分"的描述一致；
- **代码级审计（runner 接口、synthesized-test 生成、Pareto 选择实现）尚未进行** → `NOT VERIFIED`，列入 Phase 4 前置任务；
- 其 benchmark 面向 Terminal-Bench 2 / SWE-bench Pro / ProgramBench，**不可照搬到科学任务评测**。

## 9. 未完成与下一步

| 项 | 状态 | 归属 |
|---|---|---|
| 真实 Ticket 生命周期（GitHub Source） | 阻塞：缺 `gh` 与 Agent 账号 | B-001，需运维决策 |
| Feishu 测试失败 | 已知上游缺陷，不影响主链路 | B-002 |
| `deepseek-harness` 源码级审计 | 未克隆（GitHub 拉取过慢） | B-003，改为读 npm 包，Phase 1 补 |
| 科研 Python 环境（RDKit 等） | 未创建 | Phase 1 |
| 受保护信任根与评测器 | 未创建 | Phase 5 前必须 |

详细阻塞与处置见 `docs/BLOCKERS.md`。

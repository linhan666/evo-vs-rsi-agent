# LOCAL_SOURCE — 本地任务文件 Source

> 代码：`src/sources/local.ts`；测试：`tests/local.spec.ts`；提交 `6433123`。
> 依据：蓝图 §7.2（"随后自然扩展 `ResearchTaskSource`（可选）"）、§19.1（"GitHub/本地授权 Source"）、`docs/008-cookbook.md` 的 11 步。
> 性质：**新增代码，不属于上游**。上游 `src/` 的 Engine / Store / Policy 语义未改。

## 1. 它解决什么

上游只有 GitHub 与 Feishu 两种 Source，两者都需要外部服务与凭据。
本地 Source 用**一个 JSON 文件 = 一次请求**，把 CLI/文件请求映射成与 GitHub 完全相同的域对象
（`Trigger` / `Thread` / `Actor` / `Channel`），因此 Engine、Ticket 生命周期、轨迹采集都不需要特例。

它不绕开授权：文件写权限就是授权边界；Source Policy 的 `allowed` 仍然生效并可审计。

## 2. 任务文件格式

```json
{
  "task_id": "mor_bind_001",
  "sender": "operator",
  "at": "2026-11-05T06:00:00Z",
  "title": "MOR binding activity screening",
  "text": "Task: build a reliable activity model for human MOR/OPRM1 ..."
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `task_id` | 是 | 稳定 id（`[A-Za-z0-9._-]`）。相同 id 视为同一 Trigger，重放安全 |
| `text` | 是 | 请求正文，等价于 Issue 正文 |
| `sender` | 否 | 默认 `operator`；作为 `actor.id`，与 Policy `allowed` 比对 |
| `at` | 否 | ISO 时间；缺省取扫描时刻 |
| `title` | 否 | 仅存进 `meta`，供检索/展示 |

## 3. 配置与行为

| 设置 | 默认 | 作用 |
|---|---|---|
| `inboxDir` | `''`（不接收） | 扫描 `*.json` 的绝对路径 |
| `outboxDir` | `''`（回复丢弃） | 回复写为 `<message id>.json`；空则 `gone` |
| `pollSeconds` | 10 | 轮询间隔（5–3600） |
| `archive` | `true` | 处理后移入 `<inboxDir>/.processed/` |

- **幂等**：Trigger id = `key('local', task_id)`；回复文件名 = `message.id`。重发不会产生第二条。
- **单条失败不影响整批**：非法 JSON 或缺字段计入 `unreadable` 并**留在原地**，等人修。
- **Thread**：一个任务文件是该 Thread 的唯一消息；`threadContext.read` 返回它自身（`parent` 为空）。
- **准入**：`scope` 只有在 `inboxDir` 非空时 `listened`，且 `observed: false`（文件永远是"直接请求"）；
  准入行 `inbox` 的 `unlistedAddressed: true`，即"能写文件的人即可发起"，这是文件系统权限的直接后果。
- **执行变量**：`DSH_SUPERAGENT_LOCAL_TASK_ID`、`DSH_SUPERAGENT_LOCAL_SENDER`。
- **健康**：`local` 一个条目；`setupPending` / `sourceOff` / `pollFailures` 复用上游固定文案，连续 3 次失败才报 `error`。

## 4. 已验证

| 项 | 结果 |
|---|---|
| `npx tsc --noEmit` | PASS |
| `npx vitest run tests/local.spec.ts` | **7/7 PASS**：翻译、单次入库与归档、坏文件留原地、scope、幂等回复 + `gone`、setupPending、sourceOff |
| `pnpm build` | PASS，产出 `lib/local-watch.js`（9,411 B） |
| `tests/docs.spec.ts` / `tests/bundle-patch.spec.ts` | PASS（模块表、测试表、patch 列表已同步） |
| 全量 `pnpm check` | 59/60 文件通过；唯一失败仍是上游 Feishu 用例（B-002） |
| 服务启动（未解锁 setup 时） | `GET state` 健康里出现 `"local": "paused"`（已过时的历史观察） |
| **端到端（2026-11-05 实测）** | `smoke_001.json` → Ticket `2fa5057…` → Worker 回 `SMOKE_OK`，产物 `smoke_output.txt` = `hello-from-worker`；重启后 `smoke_002` 回 `RESTART_OK`，旧任务未重放 |

## 5. 已知限制（实测，不是推测）

> **2026-11-05 更新：本条已解除。** 通过操作者本人账号的仓库级细粒度 PAT 解锁了 setup 门禁，本地 Source 已实际跑通（见 §4）。以下保留当时的分析与证据，作为「为什么必须解锁 setup」的记录。

**（历史）本地 Source 无法单独让系统进入可执行状态。** 上游 `Setup` 在启动时强制解析 GitHub 部署：

- `src/deployment.ts` → `resolveDeployment()`：`repository` 为空即 `throw new SetupError('repositoryUnset')`；
  有仓库还要求 `gh api user` 已登录、且对仓库 `permissions.push === true`。
- `src/app/setup.ts` → `configured()` 仅在 `resolved !== undefined` 时为真。
- 本地 Source 的循环以 `await ctx.ready; if (!ctx.configured()) { report('local', health('paused','setupPending')); return }` 开头
  （与上游 Source 相同的约定），因此 setup 未解析时它**不会读取收件目录**。

实测证据（`172.25.18.26`，profile `superagent`，port 3082）：

```json
"health": { "runtime": "paused", "github": "paused", "local": "paused", ... },
"setup": { "place": "github", "code": "repositoryUnset",
           "detail": "The GitHub Source names no repository." }
```

更细的耦合面：

| 位置 | 是否真的需要 repository |
|---|---|
| `ticketExecution()`（`src/executor/dsh.ts`） | **不需要**，Ticket 目录来自 `executionRoot(settings, stateDir)` |
| `writeEnvironment()`（`src/infra/environment.ts`） | 用 `github.cli` 生成 `gh` shim；`github.cli` 为空会生成一个必然失败的 shim，但不会在 setup 阶段抛错 |

即：**只要让 setup 在"无 GitHub"时解析成功，执行链路本身并不依赖仓库。** 这正是 B-001 的剩余决策点。

## 6. 启用步骤（setup 解析成功之后）

1. 在 Sources 设置里保存 `local` 实例：填 `inboxDir` / `outboxDir`；
2. 在 **Eval → On each Source** 里可填 `allowed`；
3. 把任务 JSON 放进 `inboxDir`；
4. 一个轮询周期内 Overview 出现 Ticket，回复写入 `outboxDir/<message id>.json`。

## 7. 未做

- 未实现"任务完成/失败"的写回文件名约定（回复按 `kind` 区分 `acknowledgement/reply/notice`）；
- 未做文件监听（`fs.watch`），仍是轮询；
- 未做多收件目录、任务优先级、取消信号文件——这些等 Phase 1 的 Job 契约落地后再定。

# BLOCKERS — Phase 0

> 原则（蓝图 §3.4）：任一 Gate 不通过先建此文件，停止破坏性集成；允许继续做独立、离线、可验证的部分，但**不得宣称已运行完整 Harness**。

## B-001 · 真实 Ticket 生命周期冒烟受阻（HIGH，需运维决策）

**现象**：P0-04 要求"Source → Engine → Executor → Report"跑通一次受限 Ticket。当前无法完成。

**根因**（实测）：
- 主机 `172.25.18.26` 无 `gh` CLI（`gh --version` → command not found）；SETUP 要求 GitHub CLI ≥ 2.48。
- 上游 Source 只有 `github` 与 `feishu` 两种；GitHub Source 需要一个**专用 Agent GitHub 账号**（`docs/006` 明确不能复用操作者本人账号）与一个可写仓库。
- 因此"真实 Trigger 进入 Engine"这一步缺少外部前提，不是代码缺陷。

**已完成的替代验证**（不冒充端到端）：
- 上游全部单元/集成测试（58/59 文件通过），其中 `tests/core-engine.spec.ts`、`runtime.spec.ts`、`queue.spec.ts`、`background.spec.ts`、`policy.spec.ts` 覆盖 Ticket/Assignment/重试/策略路径；
- DSH 运行时 + LLM 真实端到端：`deepseek-flash` 返回 `SMOKE_OK`，并从 `api.deepseek.com` 加载 2 个模型。

**需要你决策（三选一）**：
1. 提供专用 Agent GitHub 账号 + `gh auth login`（推荐，最贴近蓝图 MVP）；
2. 批准新增一个**本地 CLI Source**（`ResearchTaskSource`，蓝图 §7.2 列为可选），以本地文件/命令投递 Trigger，绕开 GitHub；
3. 暂接受集成测试为生命周期证据，把真实 Source 推迟到 Phase 1。

## B-002 · 上游 1 个测试可复现失败（LOW，Feishu 专属）

```
FAIL tests/sources.spec.ts > feishu event consumer > …reports a malformed line without stopping
expected { state: 'ready' } to match { state: 'error', detail: contains 'JSON' }
```

- 单文件复跑 `71 tests | 1 failed`，稳定复现；
- 影响面仅 Feishu Source 的健康上报，不触及 GitHub Source、Engine 状态机与科研链路；
- **处置**：不修改上游、不回退版本；在报告中如实标注。若后续需要 Feishu，再单独立项排查。

## B-003 · `deepseek-harness` 源码未克隆（MEDIUM）

- `git clone --depth 1` 拉取该 monorepo 超过 12 分钟未完成（GitHub 链路对该仓库明显受限），已终止并清理半成品。
- **绕行**：运行时改用 npm 包 `@deepseek-ai/dsh@0.2.1-rc.5`，其版本、模型列表与 CLI 行为均已实测。
- **代价**：`docs/007-architecture.md` 级别的运行时内部实现尚未逐文件核对；Phase 1 需在低峰期补克隆或改用 npm 包内 `node_modules` 源码审计。

## B-004 · 运行环境前置缺口（MEDIUM，可自行修复）

| 缺口 | 影响 | 处置 |
|---|---|---|
| 系统 Python 无 `pip3` | 无法直接装 RDKit 等 | Phase 1 用 `python3 -m venv --without-pip` + 清华镜像 bootstrap pip（已有成熟做法） |
| 无 `gh` | B-001 | 视 B-001 决策 |
| `dsh` 未全局安装 | 无（`npx` 可用） | 保持 `npx`/项目内安装，不污染全局 |

## B-005 · 隔离等级不满足蓝图要求（HIGH，Phase 5 前必须解决）

上游 `docs/006-deployment.md` 明文：worker 以**操作者 OS 用户**、`danger-full-access` 运行，可读整个 `$HOME`。
当前 `linhan_cluster` 的 home 下有 220 个既有项目目录，直接暴露给自修改 Agent 不可接受。

**Phase 5（自修改闭环）之前必须**：专用 OS 账号 / 容器边界 / 受保护资产不可读 / 外部硬预算。当前处于 Phase 0，暂不阻塞，但不得跳过。

---

## B-001 补记（2026-11-05，本地 Source 实现后的实测结论）

**已完成**：`src/sources/local.ts`（本地任务文件 Source）+ `tests/local.spec.ts`（7/7 通过）+ 四处注册，提交 `6433123`。
详见 `docs/LOCAL_SOURCE.md`。

**新证据：本地 Source 仍然无法单独打通 Gate 0。** 实测启动 profile `superagent`（port 3082）后：

```json
"health": { "runtime": "paused", "github": "paused", "local": "paused", ... },
"setup": { "place": "github", "code": "repositoryUnset",
           "detail": "The GitHub Source names no repository." }
```

代码路径（已逐行核对）：

- `src/deployment.ts:resolveDeployment()`：`repository` 为空 → `throw new SetupError('repositoryUnset')`；
  有仓库还要求 `gh api user` 已登录、`repos/<owner>/<name>` 的 `permissions.push === true`。
- `src/app/setup.ts:configured()`：仅当 `resolved !== undefined` 为真。
- 本地 Source 与上游 Source 遵守同一约定：`await ctx.ready; if (!ctx.configured()) → report('local','setupPending')`，
  因此 setup 未解析时**不扫描收件目录**。

**耦合面已确认（决定了补丁可以做得很小）**：

| 位置 | 是否依赖 repository |
|---|---|
| `ticketExecution()`（`src/executor/dsh.ts`） | 否，Ticket 目录来自 `executionRoot(settings, stateDir)` |
| `writeEnvironment()`（`src/infra/environment.ts`） | 仅用 `github.cli` 生成 `gh` shim；空值会生成必失败的 shim，但不抛错 |

**因此只剩两条路，必须由你裁定：**

- **(A) 提供 GitHub 仓库 + 专用 Agent 账号**：零上游语义改动，T-002 直接可跑；代价是外部账号与 `gh` 登录。
- **(B) 批准"本地部署模式"补丁**：给 `Config` 加 `mode: 'github' | 'local'`（默认 `github`），
  `resolveDeployment()` 在 `local` 下跳过仓库与账号校验，返回空 `repository` 与空 `github`；
  `writeEnvironment()` 把 `gh` shim 换成显式失败提示。影响面约 2 个文件、15 行 + 1 个配置项。
  风险：改动的是**上游部署/安全语义**，与 ADR-001"最小侵入"存在张力；需在 `UPSTREAM.md` 登记为本地补丁，
  且后续每次同步上游都要重新确认。收益：不依赖任何外部账号即可跑通 `Source→Engine→Executor→Report`。

**已撤销**：早期把"集成测试当作 Gate 0 证据"列为选项 3 —— 与蓝图 §3.4 冲突，作废。

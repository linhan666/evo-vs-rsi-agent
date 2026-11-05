## Phase 0 Implementation Report

> 格式严格遵循蓝图 §21。凡未运行/未通过项均显式标注，不写"应该可以"。

### Upstream and environment

- Upstream commit: `dsh-superagent-prototype` = `8c32a9dc5d72c033816c6a8110b37f40cf94fba4`（2026-10-31T20:06:31+08:00，MIT）
- Reference commit: `pzs19/HarnessPro` = `6fd2d4dbc3b73881b2b48833764fcd803aacb7b8`（`--depth 1`，只读，gitignored）
- DSH version: `@deepseek-ai/dsh@0.2.1-rc.5`（`npx` 调用，未全局安装；满足 `engines.dsh: ^0.2.1-alpha.2`）
- Python/Node versions: Python 3.12.3（系统，无 `pip3`）/ Node v22.23.4（用户态）/ pnpm 11.7.0 / npm 10.9.9 / git 2.43.0 / **gh 2.103.3（用户态）**
- GitHub 账号: `linhan666`（沿用操作者本人账号，见 `docs/BLOCKERS.md` B-006 的风险记录），细粒度 PAT 仅授权 `linhan666/evo-vs-rsi-agent`
- Environment / container lock: **无容器**。仅用户态工具链 `~/software/node-v22.23.4-linux-x64`；系统包、`~/.bashrc`、全局 npm prefix 均未改动。`pnpm-lock.yaml` 原样保留（172,084 B）。

### Files changed

| 文件 | 为什么 |
|---|---|
| `PROJECT.md` | 项目元信息早期草稿；内容已被 `README.md` 覆盖，保留以记录演进 |
| `README.md` | 蓝图 §15 要求 `README.md` 为 project overview；原上游 README 移至 `docs/upstream-README.md` |
| `UPSTREAM.md` | 基线 SHA、版本锁定、参考仓、合并策略 |
| `AGENTS.md` | 本项目开发规则（执行位置、禁区、科研诚信） |
| `env.sh` | 项目环境入口：Node PATH + 仓库外凭据 + 单卡策略 |
| `docs/UPSTREAM_AUDIT.md` | P0 Gate 表：版本、构建/测试证据、真实签名、隔离审计 |
| `docs/ARCHITECTURE.md` | 分层、三类修改面隔离、`[PLANNED]` 模块 |
| `docs/IMPLEMENTATION_LOG.md` | 真实命令与输出时间线 |
| `docs/BLOCKERS.md` | B-001…B-005，含处置与需决策项 |
| `docs/PHASE0_REPORT.md` | 本文件（§21 格式） |
| `docs/evidence/phase0/*.log` | 安装/检查原始日志（从 `logs/phase0/` 复制，纳入版本库以便复现） |
| `scientific/pyproject.toml`、`src/evovs_science/{__init__,schemas,cli}.py`、`tests/test_schemas.py`、`examples/job_spec.example.json`、`README.md` | 蓝图 §20 第 7 条：最小 `scientific/` 包与 schema 占位（**仅契约，无科研实现**） |
| `ops/bootstrap_node.sh`、`ops/phase0_run.sh`、`ops/rctl.py` | 用户态 Node 引导、基线检查、远程控制（凭据走 gitignored `ops/local.env`） |
| `.gitignore` | 追加 `logs/ reference/ runs/ workspaces/ artifacts/ benchmarks/heldout/ ops/local.env` |
| `src/sources/local.ts`、`tests/local.spec.ts`、`docs/LOCAL_SOURCE.md`、`ops/register_local_source.py` | 本地任务文件 Source（蓝图 §7.2 可选扩展）：把 JSON 任务文件映射为 Trigger/Thread/Actor/Channel，7 个单测覆盖翻译、入库与归档、坏文件、scope、幂等回复、setup 与开关状态 |
| `tsdown.config.ts`、`package.json`、`cordis.patch.yml`、`docs/007-architecture.md`、`tests/bundle-patch.spec.ts` | 按 cookbook 第 10 步注册新 Source（构建入口、导出、bundle 插入、模块/测试索引、patch 列表断言同步） |
| `src/`（除新增文件）、`prompts/`、`skills/`、`tests/`（除新增 spec） | 既有文件**语义未改**（Engine / Store / Policy / Executor 未动） |

### Executed commands (real, not assumed)

| 命令 | 结果 | 输出位置 |
|---|---|---|
| `bash ops/bootstrap_node.sh` | PASS — node v22.23.4 / pnpm 11.7.0 | `docs/evidence/phase0/`、服务器 `logs/phase0/` |
| `git clone …dsh-superagent-prototype` | PASS — HEAD `8c32a9d` | `docs/UPSTREAM_AUDIT.md` §2 |
| `git clone --depth 1 …HarnessPro` | PASS — 58 MB，HEAD `6fd2d4d` | 同上 |
| `git clone --depth 1 …deepseek-harness` | **FAIL/中止** — >12 min 未完成，已终止清理 | B-003 |
| `pnpm install --frozen-lockfile` | PASS — exit 0，8.7 s | `docs/evidence/phase0/pnpm_install.log` |
| `pnpm typecheck`（`tsc --noEmit`） | PASS | `docs/evidence/phase0/pnpm_check.log` |
| `pnpm test`（`vitest run`） | **PARTIAL** — 58/59 文件通过，1 例失败 | 同上 |
| `npx vitest run tests/sources.spec.ts` | **FAIL（稳定复现）** — 71 例中 1 例失败 | 同上 |
| `pnpm build`（`tsdown`） | PASS — 11 文件 / 693.50 kB / 2516 ms | 同上 |
| `npx @deepseek-ai/dsh --version` | PASS — `0.2.1-rc.5` | `docs/IMPLEMENTATION_LOG.md` §4 |
| `npx @deepseek-ai/dsh headless "Reply with exactly: SMOKE_OK"` | PASS — `SMOKE_OK`，`api.deepseek.com` 返回 2 个模型 | 同上 |
| `PYTHONPATH=scientific/src python3 -m unittest discover -s scientific/tests` | 见下（本轮新增） | `docs/evidence/phase0/scientific_tests.log` |
| `PYTHONPATH=scientific/src python3 -m evovs_science.cli validate-spec …` | 见下（本轮新增） | 同上 |
| `npx tsc --noEmit`（加入本地 Source 后） | PASS | `docs/evidence/phase0/` |
| `npx vitest run tests/local.spec.ts` | **PASS — 7/7** | 同上 |
| `npx vitest run tests/local.spec.ts tests/docs.spec.ts tests/bundle-patch.spec.ts` | **PASS — 15/15** | 同上 |
| `pnpm check`（含本地 Source） | 59/60 文件通过；唯一失败为 B-002 | `docs/evidence/phase0/pnpm_check_local_source.log` |
| `pnpm build` | PASS，产出 `lib/local-watch.js` 9,411 B | 同上 |
| `dsh superagent --from-default-profile web` + `dsh plugin add link:$PWD` + `scripts/dsh-superagent start` | 服务启动成功，但 setup 报 `github/repositoryUnset`；健康中 `local: paused` | `docs/LOCAL_SOURCE.md` §5 |

### Acceptance tests

- **Test IDs completed**：无完整通过的 T-ID。
- **T-001（不破坏上游 `pnpm check`）**：**PARTIAL**。`typecheck` 与 `build` 通过；上游自身 `tests/sources.spec.ts` 有 1 例 Feishu 用例可复现失败。加入本项目新增文件后重跑结果一致（58/59），可证明**未引入新破坏**，但不能宣称 `pnpm check` 全绿。
- **T-002（Ticket 启动→Worker→报告）**：**PASS**。真实链路：`smoke_001.json` → Trigger → Ticket `2fa505775dd03e69a222cc2babfdf2fe` → DSH Worker → `acknowledgement`（08:15:12）→ `reply: SMOKE_OK`（08:15:22），产物 `.artifacts/state/work/smoke-write-file-2fa505775dd0/smoke_output.txt` = `hello-from-worker`。证据见 `docs/evidence/phase0/smoke/`。
- **T-003（重启恢复）**：**PASS（限 Source/Engine 层）**。`scripts/dsh-superagent restart` 后 outbox 仍为 2 个文件（旧任务未重放、未重复创建 Ticket）；随后 `smoke_002` 正常完成（`RESTART_OK`，产物 `restart_proof.txt` = `after-restart`）。**未测试**：运行中作业被强杀后的 Assignment 断点续跑。
- **Known failures**：`tests/sources.spec.ts > feishu event consumer > …reports a malformed line without stopping`，断言 `health.feishu` 应为 `error` 实为 `ready`（B-002，上游缺陷，不修不回退）。
- **未进入范围**：T-004…T-020 属 Phase 2+ 科学/进化/Benchmark 测试，Phase 0 不得声称通过。

### Scientific / security integrity

- Data split changes: **no**（Phase 0 未接触任何真实活性数据；`benchmarks/heldout/` 尚未创建）
- Protected test access: **none**（无 heldout 标签存在，无评测器调用）
- Permission changes: **none**（未改系统包、未改 `~/.bashrc`、未改全局 npm/pip 配置；仅在 `~/software` 与 `~/.npm` 写入）
- 凭据处理：DeepSeek API key 存于 `~/.config/evo_vs_rsi/secrets.env`（`600`，仓库外）；已用 `git grep` 校验仓库内**无** API key、代理口令、SSH 口令。
- 隔离风险（**未解决**）：上游 worker 以操作者 OS 用户 + `danger-full-access` 运行，可读整个 `$HOME`（该账号 home 下有 220 个既有项目）。Phase 5 自修改闭环前必须补物理隔离（B-005）。

### Artifact links and reproducibility

- Dataset manifests: **无**（尚未进入 Phase 2 数据阶段）
- Job/trace logs: 服务器 `/home/linhan_cluster/evo_vs_rsi/logs/phase0/`；关键日志已复制到 `docs/evidence/phase0/`
- Code commit: `1e2771c`（Phase 0 审计文档与骨架）+ 本次补充提交（README / scientific 契约 / 本报告）
- Result artifacts: `docs/evidence/phase0/smoke/`（4 条 outbox 消息、2 个 worker 产物、`state_after.json`）；无科研工件，`scientific/examples/job_spec.example.json` 仅用于契约校验

### RSI classification (only for Evolution phases)

不适用：Phase 0 无任何 Harness 候选、无 Shadow 评估、无版本晋升。
**本阶段不存在任何可称为 `validated_harness_evolution` 的事件。**

### Next phase

- **Recommended tasks**（蓝图 §17 Phase 1，P1-01…P1-06）：
  1. `scientific/` 固定 Python 版本与依赖 pin（uv/venv），补齐 `schemas.py` 之外的 chemistry/data/modeling/evaluation/screening 骨架；
  2. 实现 TS 侧 `JobSpec/JobResult` schema + 沙箱 `subprocess` 运行 + 资源限制 + 工件返回 + 取消；
  3. 科学 tool registry（能力查询、版本、licence、失败码）；
  4. 统一日志、`sha256` 工件清单、job ID、资源用量；
  5. 合法 SMILES 小样本跑 RDKit ECFP / 2D descriptors + 小模型；
  6. 失败/超时/中断恢复集成测试。
- **Blocking decisions requiring operator authorization**：
  - ~~**B-001**~~：**已解决**。两条路径同时落地：实现本地 Source，并用操作者本人账号的细粒度 PAT 解锁上游 setup 门禁；T-002/T-003 均有真实日志。
  - **B-005**：进入 Phase 5 前必须提供隔离环境（专用 OS 账号/容器/受保护资产不可读）。

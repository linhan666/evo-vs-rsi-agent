# IMPLEMENTATION_LOG

> 只记录**真实执行过的命令**与真实结果。所有命令在 `172.25.18.26` 上运行，本机仅做编辑与 SSH 控制。

## 2026-11-05 · Phase 0

### 0. 前置：只读探测（未做任何改动）

| 探测 | 结果 |
|---|---|
| 6 台服务器工具链横向比对 | 仅 `172.25.18.26 / 18.25 / 16.33` 有 node（均 v18.19.1）；`16.33` 磁盘仅剩 1.5 G |
| 选定执行机 | `172.25.18.26`：GPU2/3 全空（0 MiB），`/home` 649 G 可用 |
| 外网可达 | github.com / registry.npmjs.org / npmmirror / 清华 PyPI / huggingface 均 200 |
| 目录冲突 | 无 `evo*/rsi*/harness*/dsh*` 目录；home 下另有 220 个既有项目目录，**未触碰** |
| GPU 占用 | GPU0/1 被他人进程占用（约 3.3 G），**全程不使用** |

### 1. 用户态运行时

```sh
bash ops/bootstrap_node.sh          # NV=v22.23.4, PNPM_VER=11.7.0
```
输出：`node: v22.23.4` / `npm: 10.9.9` / `pnpm: 11.7.0` / `prefix: ~/software/node-v22.23.4-linux-x64`
写入范围：仅 `~/software/` 与 `~/.npm/`。**未**改系统包、**未**写 `~/.bashrc`。

### 2. 仓库与基线

```sh
git clone https://github.com/deepseek-ai/dsh-superagent-prototype.git
# HEAD = 8c32a9dc5d72c033816c6a8110b37f40cf94fba4
git clone --depth 1 https://github.com/pzs19/HarnessPro.git reference/HarnessPro
# HEAD = 6fd2d4dbc3b73881b2b48833764fcd803aacb7b8  (58 MB)
```

`deepseek-harness` 克隆超过 12 分钟未完成 → 终止并清理，记 B-003；运行时改用 npm 包。

### 3. 基线检查

```sh
pnpm install --frozen-lockfile     # exit=0, Done in 8.7s
pnpm typecheck                     # PASS
pnpm test                          # Test Files 1 failed | 58 passed (59)
pnpm build                         # PASS, 11 files, 693.50 kB, 2516ms
```

失败用例复跑：`npx vitest run tests/sources.spec.ts` → `71 tests | 1 failed`（稳定复现，Feishu 专属，记 B-002）。

### 4. LLM 端到端冒烟

```sh
set -a; . ~/.config/evo_vs_rsi/secrets.env; set +a
npx --yes @deepseek-ai/dsh headless "Reply with exactly: SMOKE_OK"
```
输出：
```
[llm-deepseek-api-key] model listing from https://api.deepseek.com/models loaded 2 model(s), skipped 0 row(s)
SMOKE_OK
```
- 密钥存放：`~/.config/evo_vs_rsi/secrets.env`，`-rw-------`（600），94 字节，**不在仓库内、不入 Git、不回显**。
- 默认 profile 配置已内置 `provider: deepseek-official` / `model: deepseek-flash`，与需求一致。

### 5. 本轮产生/修改的文件

| 路径 | 性质 |
|---|---|
| `PROJECT.md` / `UPSTREAM.md` / `AGENTS.md` / `env.sh` | 新增（本项目元信息） |
| `docs/UPSTREAM_AUDIT.md` / `docs/ARCHITECTURE.md` / `docs/BLOCKERS.md` / `docs/IMPLEMENTATION_LOG.md` | 新增 |
| `ops/bootstrap_node.sh` / `ops/phase0_run.sh` / `ops/rctl.py` | 新增（运维脚本，凭据外置） |
| `.gitignore` | 追加 `logs/ reference/ ops/local.env` 等 |
| `src/` `prompts/` `skills/` `tests/` `package.json` | **未修改**（上游原样） |

### 6. 与蓝图的偏差（显式记录）

| 项 | 蓝图要求 | 实际 | 原因 |
|---|---|---|---|
| P0-04 真实 Ticket | Source→Engine→Executor→Report | 未完成，仅做 LLM + 集成测试级验证 | 缺 `gh` 与 Agent 账号（B-001） |
| P0-03 `pnpm check` | 全绿 | typecheck/build 绿，测试 1 例红 | 上游缺陷（B-002） |
| §3.2 运行时源码审计 | 读 `deepseek-harness` 源码 | 仅用 npm 包行为验证 | 克隆过慢（B-003） |
| Phase 1 科研包 | `scientific/` | **未创建** | 本轮只做 Phase 0 门禁，不越阶段 |

### 7. 下一步建议

1. 你裁定 B-001 的三条路径后，补完真实 Ticket 冒烟；
2. Phase 1：`scientific/` Python 包 + JobSpec/JobResult 桥接（含 GPU 硬限与 job 状态机）；
3. Phase 2 前先解决 B-005 的隔离等级，否则自修改闭环不具备安全前提。

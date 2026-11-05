# EvoVS-RSI

面向跨靶点药物虚拟筛选的自主 Agent Harness 与递归自进化系统。

> **本项目的本体不是"自动选择最优 QSAR 模型"，而是"让通用科研 Agent Harness 在持续执行不同靶点任务时，对自身完成科研任务的运行机制进行证据驱动、可验证、可回滚的递归改进"。**
> —— 蓝图 §23 最终一句话

- 设计蓝图：`EvoVS_RSI_Harness_Codex_Blueprint.md`（v0.1.0，2026-11-05）
- 代码基底：`deepseek-ai/dsh-superagent-prototype`（MIT，研究原型）
- RSI 机制参考：`pzs19/HarnessPro`（仅参考，不替代基底）
- 当前阶段：**Phase 1 — 科研环境与可观测 job 执行**（Gate 1 已通过）
- 状态：**Phase 0 与 Phase 1 的 Gate 均已通过**。Agent 能在真实 Ticket 中自主发现并调用两个科研工具（`rdkit.featurize`、`sklearn.train`），产出带 sha256 的工件与指标。**尚未接触任何真实活性数据**；Phase 2 起。

## 关键事实（实测，非推测）

| 项 | 值 |
|---|---|
| 上游 commit | `8c32a9dc5d72c033816c6a8110b37f40cf94fba4` |
| DSH runtime | `@deepseek-ai/dsh@0.2.1-rc.5` |
| Node / pnpm | v22.23.4 / 11.7.0（用户态 `~/software`） |
| `pnpm typecheck` | PASS |
| `pnpm build` | PASS（11 文件，693.50 kB，2516 ms） |
| `pnpm test` | 58/59 文件通过；1 例 Feishu 用例可复现失败（上游缺陷） |
| LLM 端到端 | PASS（`deepseek-flash` → `SMOKE_OK`） |
| 科研环境 | `scientific/.venv`：rdkit 2024.09.5 / scikit-learn 1.5.2 / numpy 2.1.3 |
| Gate 1 | PASS — 真实 Ticket 自主调用 2 个科研工具，工件与指标可复核 |
| Gate 0 | **通过**：`T-002`（Ticket 生命周期）与 `T-003`（重启恢复）PASS，证据在 `docs/evidence/phase0/smoke/` |

## 快速开始

```sh
source env.sh                 # Node 22 + pnpm + 模型凭据（凭据在仓库外，600）
pnpm install --frozen-lockfile
pnpm check                    # typecheck + test + build

# 科研 Python 包（仅 schema 占位，标准库，无需 pip）
PYTHONPATH=scientific/src python3 -m unittest discover -s scientific/tests -v
```

## 目录

```
├── src/                 上游 TypeScript + 新增 src/sources/local.ts、src/research/（工具与沙箱 runner）
├── scientific/          【新增】Python 科研环境（featurize / train / manifest；契约见 schemas.py）
├── ops/                 运维脚本（Node 引导、基线检查、远程控制）
├── docs/                上游 001-008 + 本项目审计/架构/日志/阻塞/阶段报告
├── prompts/ skills/ scripts/ tests/ examples/ locale/   上游原样
├── reference/           【gitignored】HarnessPro 只读参考
├── logs/                【gitignored】运行日志
└── README.md / AGENTS.md / UPSTREAM.md / PROJECT.md
```

## 必读文档

| 文档 | 内容 |
|---|---|
| `docs/UPSTREAM_AUDIT.md` | 上游真实接口、版本、构建与测试证据、Gate 0 判定 |
| `docs/LOCAL_SOURCE.md` | 本地任务文件 Source：格式、配置、已验证行为、setup 门禁的成因与解除方式 |
| `docs/PHASE1_REPORT.md` | Phase 1 报告：Gate 1 证据、已知缺口、Phase 2 前置 |
| `docs/TRANSFER_DESIGN.md` | §12 迁移实验预注册口径（pooled vs per-target、负迁移判定、scaffold 聚类 bootstrap） |
| `docs/EVALUATOR_TRIGGER_DESIGN.md` | 锁定评测的触发方式设计（手动/垫片/orchestrator pass 三案比较） |
| 运行主机 | **172.25.16.37**（8×H100；`rctl --host 172.25.16.37`）。`.26` 为迁移前存档 |
| `docs/ARCHITECTURE.md` | 分层、三类修改面隔离、计划新增模块 |
| `docs/BLOCKERS.md` | 5 项阻塞与处置 |
| `docs/PHASE0_REPORT.md` | 按蓝图 §21 格式的阶段报告 |
| `AGENTS.md` | 开发规则（执行位置、禁区、科研诚信） |
| `UPSTREAM.md` | 基线 SHA、版本锁定与合并策略 |

## 边界

1. 本机只编辑，所有执行在内网 GPU 服务器；
2. 单卡，只用空闲卡，不碰他人进程与项目；
3. 任务工作区 / 可进化 Harness / 受保护信任根三者物理隔离；
4. 不训练 Meta-Policy，不改基础 LLM 权重；下游 QSAR/DTI/DTA 训练属科研任务，允许。

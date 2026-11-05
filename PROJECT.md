# EvoVS-RSI（历史快照）

> **⚠️ 本文件已冻结为 Phase 0 时期的历史草稿，不再维护。**
> 当前状态请看 `README.md`（阶段映射 + 关键事实）与 `docs/PHASE5_REPORT.md`（最新阶段报告）。
> 保留本文件是为了记录项目骨架的演进起点；其中的"当前阶段/状态"字段均为 2026-11-05 的值。

面向跨靶点药物虚拟筛选的自主 Agent Harness 与递归自进化（RSI）系统。

- **设计蓝图**：`EvoVS_RSI_Harness_Codex_Blueprint.md`（v0.1.0，2026-11-05）
- **当前阶段（历史，2026-11-05）**：Phase 0 — 上游审计与最小运行验证（已完成，含 4 项阻塞记录）
- **状态（历史，2026-11-05）**：不是可运行的完整系统。目前只有上游基线的可复现构建证据与项目骨架。

## 关键事实（Phase 0 实测值，历史）

| 项 | 值 | 证据 |
|---|---|---|
| 上游基线 commit | `8c32a9dc5d72c033816c6a8110b37f40cf94fba4` | `git rev-parse HEAD` |
| 运行时 | `@deepseek-ai/dsh@0.2.1-rc.5`（`engines.dsh: ^0.2.1-alpha.2` 满足） | `npx @deepseek-ai/dsh --version` |
| Node / pnpm | v22.23.4 / 11.7.0（用户态，`~/software`） | 见 `docs/IMPLEMENTATION_LOG.md` |
| typecheck | PASS | `tsc --noEmit` |
| tests | 58/59 文件通过，1 个 Feishu 用例可复现失败 | `docs/BLOCKERS.md` B-002 |
| build | PASS（11 文件，693.5 kB，2516 ms） | `pnpm build` |
| LLM 冒烟 | PASS（`deepseek-flash` → `SMOKE_OK`） | `docs/IMPLEMENTATION_LOG.md` |

## 目录

```
evo_vs_rsi/
├── src/                     # 保留的上游 dsh-superagent TS 源码（未改语义）
├── docs/                    # 上游文档 + 本项目审计/架构/日志/阻塞
├── prompts/ skills/ scripts/ tests/ examples/ locale/
├── reference/               # 【gitignored】HarnessPro 等只读参考仓
├── ops/                     # 本项目运维脚本（Node 引导、安装检查、远程控制）
├── logs/                    # 【gitignored】运行日志
├── env.sh                   # 项目环境入口（Node PATH + 密钥）
└── package.json             # 上游原样，未改动
```

**当时计划新增、现已创建**（Phase 1+，见 `docs/ARCHITECTURE.md`）：`src/research/`、`scientific/`、`evolution/`、`protected/` 均已落地；`configs/`、`benchmarks/` 仍未创建（benchmark 设计见蓝图 §13）。

## 环境

```sh
source env.sh                       # 注入 node22 / pnpm / DEEPSEEK_API_KEY
pnpm install --frozen-lockfile
pnpm check                          # typecheck + test + build
```

## 边界（不可违反）

1. **本机不做任何实验**：本仓库在本机只编辑，所有执行都在内网 GPU 服务器。
2. **单卡**：至多占用一张 GPU，且不碰他人已占用的卡。
3. **不修改其它既有项目**：本项目只写自己的目录。
4. **任务工作区 / 可进化 Harness / 受保护信任根**三者物理隔离（见 `docs/ARCHITECTURE.md`）。

详见 `AGENTS.md`。

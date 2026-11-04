# UPSTREAM — 上游基线与锁定策略

## 主基线

| 项 | 值 |
|---|---|
| 仓库 | https://github.com/deepseek-ai/dsh-superagent-prototype |
| 许可 | MIT（`LICENSE` 原样保留） |
| 基线 commit | `8c32a9dc5d72c033816c6a8110b37f40cf94fba4` |
| 提交时间 | 2026-10-31T20:06:31+08:00 |
| remote `origin` | 指向上游（本仓库为其 fork 工作副本） |
| 锁定文件 | `pnpm-lock.yaml` 原样保留（172 KB） |

## 运行环境

| 项 | 锁定值 | 来源 |
|---|---|---|
| Node.js | v22.23.4（用户态 `~/software/node-v22.23.4-linux-x64`） | 官方 linux-x64 tarball |
| pnpm | 11.7.0 | `npm i -g` 到 user prefix |
| DSH runtime | `@deepseek-ai/dsh@0.2.1-rc.5` | `npx`；满足 `engines.dsh: ^0.2.1-alpha.2` |
| 模型 | `deepseek-flash`（provider `deepseek-official`） | DSH 默认 profile 配置 |

**不自动升级 alpha/rc 版本**。任何 runtime 升级必须：重跑 `pnpm check` → 更新本文件与 `docs/UPSTREAM_AUDIT.md` → 记录旧版本以便回滚。

## 参考仓（只读，不进本仓库 Git）

| 仓库 | commit | 用途 |
|---|---|---|
| https://github.com/pzs19/HarnessPro | `6fd2d4dbc3b73881b2b48833764fcd803aacb7b8` | RSI 机制参考：轨迹诊断、候选编辑、合成测试、Pareto 选择 |
| https://github.com/deepseek-ai/deepseek-harness | `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159`（仅 ls-remote） | 运行时上游；本轮未克隆（见 BLOCKERS B-003） |

两者位于 `reference/`（gitignored），**不得**作为代码基底替换主基线。

## 合并策略

1. 上游改动手工 cherry-pick 或 rebase，不整包替换；
2. 与 `src/core/`、`src/app/store.ts` 冲突时，**保留上游语义**，把我们的能力放到 Ports 之外的独立模块；
3. 每次同步上游后必须重跑 `pnpm check`，并把新 SHA 与测试结果写入 `docs/IMPLEMENTATION_LOG.md`。

## 已知上游问题

- `tests/sources.spec.ts` 的 Feishu 事件消费用例可复现失败（`health.feishu` 未进入 `error`）。见 `docs/BLOCKERS.md` B-002。**不修上游、不回退**。

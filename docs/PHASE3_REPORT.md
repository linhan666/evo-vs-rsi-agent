# PHASE3_REPORT（部分：P3-01/03/04/05；P3-02 部分完成）

> 本阶段无新外部依赖；venv 不变。所有脚本为 operator/CLI 级执行，服务保持停止。

## 数据（P3-03，靶点 ID 经 API 核实，非凭记忆）

| 靶点 | ChEMBL ID | UniProt | 快照（拉取/保留/丢弃） | Ki 行 | 归一化→分子→标签 | 划分 train/val/test |
|---|---|---|---|---|---|---|
| MOR | CHEMBL233 | P35372 | 16,240/16,131/109 | 8,763 | 6,339→4,472→3,281 | 2,297/493/491 |
| **KOR** | **CHEMBL237** | P41145 | 13,456/13,330/126 | 6,261 | 4,174→3,100→2,233 | 1,564/335/334 |
| **DRD2** | **CHEMBL217** | P14416 | 19,662/19,564/98 | 14,783 | 10,753→6,606→3,873 | 2,712/581/580 |

三靶点 `no_molecule_in_two_splits` / `no_scaffold_crosses_splits` 全部为 true。
**本阶段修复的缺陷**：split manifest 写在 outdir mkdir 之前（首跑必现 FileNotFoundError，KOR/DRD2 首跑暴露）。

## 模型与锁定测试（xgboost，scaffold-manifest 训练；测试仅评测器可读）

| 靶点 | train/val | val AUROC | **test AUROC** | test AUPRC | test EF@1% | test n |
|---|---|---|---|---|---|---|
| MOR | 2,297/493 | 0.9021 | **0.9339** | 0.9722 | 1.379 | 491 |
| KOR | 1,564/335 | 0.8765 | **0.8685** | 0.9263 | 1.459 | 334 |
| DRD2 | 2,712/581 | 0.9214 | **0.9015** | 0.9260 | 1.824 | 580 |

## 100k 库复用筛选（P3-04）与三靶点矩阵（P3-05）

- 同一 `library_100k.smi`（sha256 记录在 `library_manifest.json`）筛 MOR/KOR/DRD2 三次：耗时 83.6 / 65.7 / 69.8 s。
- `screening/matrix.py`：按分子 id **inner join** → **100,000 行 × 三靶点 score+rank**（`.artifacts/matrix/three_targets.csv`；样例入 `docs/evidence/phase3/`）。
- 明确边界：跨靶点分数**不可直接比较**，矩阵不衍生 selectivity 列（§9.6 要求校准后输出才可比较）。

## 经验库（P3-01）

`experience/store.py`：`record`（dataset/model/screening 三类，payload 摘要 + sha256 + **applicability 一句话**）与 `retrieve`（按 target/kind 过滤）。当前 9 条记录（3 靶点 × 3 类），每条明确"跨靶点迁移不成立"等边界。

## P3-02 完成（2026-11-05 21:45，science_008）

**核查结论（为什么之前没做）**：检索 CLI 早已可用，缺的是**注入路径的设计决策**。写入系统提示的方案被否——静态事实会成为无出处的权威、且撑爆 worker 字符预算。选定**按需检索**：新增只读工具 `experience.retrieve`（4 号工具），检索行为本身落一个可审计工件（`runs/experience/*.json`），provenance（experience_id + payload sha256）保留在轨迹里。

**实测（Ticket `science_008` → `b6d4f508…`，无 shell）**：Agent 先检索 KOR dataset 与 MOR model 两条经验，然后完成 KOR 全链路，回复引用**逐字的适用性限制**（"scores are predictions on an unlabeled library, so no hit rate or EF is defined"）。Agent 模型锁定测试 **AUROC 0.8685 / AUPRC 0.9263**——与 operator 模型完全一致。

**契约测试当场抓到两处真实契约缺陷并修复**：
1. `--store` 定义在顶层 parser，而工具 argv 把它放在子命令后——argparse 会拒绝；已让 `record`/`retrieve` 子命令都接受 `--store`（SUPPRESS 默认防覆盖顶层值）。
2. 契约测试最初只查顶层 `--help`，子命令式 CLI 的 flag 检查不到——测试已支持子命令式 argv。

**Agent 三次自纠暴露的工具层毛刺（已修，无需重建 lib）**：
1. `screening.rank --model` 传目录 → 现在给出明确报错（"must be the fitted pipeline FILE …"）；
2. `experience.retrieve --out` 父目录不存在 → 现在 `os.makedirs` 自动创建（实测验证）；
3. Agent 靠重试绕过的错误，不该靠重试——这两处修完，重试路径消失。

## 防再发机制（承接 Gate 2 两缺陷）

1. **缺陷 1（改源码未重建 lib）**：`ops/check_build_freshness.py` 启动门禁——`src/**.ts` 任一比 `lib/index.js` 新即拒绝启动（实测通过）。
2. **缺陷 2（TS schema 与 Python CLI 漂移）**：`tests/research.spec.ts` 新增契约测试——三个工具 argv 的**每一个 flag** 必须出现在对应模块 `--help` 中（13/13 通过）。
3. **新缺陷（本阶段发现并修）**：normalize 首跑目录创建顺序（见上）。

## Known failures / not done

- B-002 上游 Feishu 用例（与本阶段无关）；
- P3-02 的 Agent 侧接入；
- P3-05 的 selectivity 列与 OOD/不确定性列（§9.6 全量字段）——待校准模块；
- 经验库当前为文件存储，并发写未加锁（单人 operator 场景可接受）。

## 边界测绘与收紧（science_009/010，B-005 无账号替代方案）

**测绘（science_009，裁剪前，Ticket `fa6b99e6…`）**：泛用 fs 工具的可写根**远宽于 ticket 目录**——
ticket 外写文件 succeeded（探针文件已清理）、**protected 测试标签可读**；科学工具的路径 schema 正确拒绝数据根外路径。
**收紧**：worker 与主 Session 的泛用文件/网络工具全部移除（write/edit/read/glob/grep/read_image/web_search/web_fetch），
仅保留 job 工具——依据：science_007/008 全链路只用了 scientific_* + orchestrator_*。
**复测（science_010，裁剪后，Ticket `395d0521…`）**：A/B 探针报 "no file-write/read tool is available"、逃逸文件未创建、featurize 正常（2,790）。

**附加加固**：scientific 作业的 `HOME` 指向 ticket 工作区（~ 访问落在工作区）；`ops/canary_check.py` 金丝雀
监控 API key 文件、gh-agent hosts.yml、home 金丝雀、protected 目录权限（基线已记录，Ticket 前后各跑一次）。

**残余风险（诚实声明）**：同用户上限仍在——以上都是应用层约束；若上游 DSH 或我们工具层出现可执行任意代码的
漏洞，逃逸进程仍拥有 `linhan_cluster` 的全部权限，金丝雀只能**检测**不能**阻止**。Phase 4 前必须三选一：
专用账号 / 另一台机器跑 Harness / 书面接受残余风险并限制 Phase 4 能力面。

## §12 迁移实验实跑（预注册口径，2026-11-05 23:05）

pooled 模型（三靶点 train 合并 + 预注册 target one-hot，6,573 行 / 2,058 维）vs per-target 基线，**锁定测试**：

| 靶点 | pooled AUROC | per-target AUROC | Δ | CI95（scaffold 聚类 bootstrap） | 判定 |
|---|---|---|---|---|---|
| MOR | 0.8872 | 0.9339 | **−0.0468** | [−0.0770, −0.0195] | **负迁移 = True**（幅度与方向均过阈值） |
| KOR | 0.8522 | 0.8685 | −0.0163 | [−0.0457, +0.0119] | False（CI 含 0：未观察到差异） |
| DRD2 | 0.8842 | 0.9015 | −0.0173 | [−0.0312, −0.0034] | False（CI 全负但幅度未达 −0.02 阈值——如实标注"统计可检的下降"） |

三条 CI 已作为 `transfer` 类经验写入经验库（applicability：pooled 训练未经重校准不得用于该靶点）。
**结论的表述规则已执行**：CI 含 0 只说"未观察到差异"；DRD2 不写成"无影响"。

## KOR/DRD2 经真实 Ticket 复用经验库（P3-02 收尾）

| Ticket | 靶点 | 经验检索 | 链路作业 | 回复要点 | Agent 模型锁定测试 |
|---|---|---|---|---|---|
| science_008 | KOR | 2 次（KOR dataset + MOR model） | 全 SUCCEEDED | val AUROC 0.8765 / 100k / top-1 0.999433 + 逐字限制 | **0.8685**（与 operator 一致） |
| science_011 | DRD2 | 3 次（含 DRD2 transfer 警告） | **6 作业一次全成（零重试）** | val AUROC 0.9214 / 100k / top-1 0.996710 + 引用 dataset_DRD2_007 | **0.9015**（与 operator 一致） |

**新缺陷（经验库分裂脑，已修）**：`store` 默认路径依赖 cwd，三条 transfer 记录写进了 `scientific/experience/`（旧位置），agent 如实报告 "0 DRD2 transfer records" 暴露了分裂。已合并（12 条）并删除游离文件；规则改为**始终显式传 `--store`**（数据根内路径）。

## Next phase

- Phase 3 后半：Memory 注入机制设计 → 经真实 Ticket 的 KOR/DRD2 执行（复用经验库）；
- §12 的跨靶点迁移实验设计（负迁移检测）；
- B-005 专用账号（建议在 Phase 4 前落实）。

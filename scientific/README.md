# scientific/ — 科研执行环境（Phase 0 占位）

**当前只实现了一个东西：TypeScript ↔ Python 的 job 契约（蓝图 §8.1）。**
没有化学计算、没有模型训练、没有子进程执行。任何"已实现科研工具链"的说法都是不成立的。

## 为什么先做这个

蓝图 §20 第 7 条要求 Phase 0 "创建最小 `scientific/` Python 包及 schema 占位，仅当不破坏上游时；先不要假装已实现完整科研工具链"。
先固化契约，Phase 1 的 runner / registry / artifact 才不会各写一套。

## 内容

| 文件 | 作用 |
|---|---|
| `src/evovs_science/schemas.py` | `JobSpec` / `JobResult` / `Resources` / `Usage` + 校验 |
| `src/evovs_science/cli.py` | `version` / `validate-spec` / `run-job`（故意未实现） |
| `tests/test_schemas.py` | 契约测试，标准库 `unittest` |
| `examples/job_spec.example.json` | 合法样例，供 CLI 校验 |

## 已强制的结构约束

- `schema_version` 必须为 `"1"`；
- `argv` 必须是**字符串列表**，不接受整条 shell 字符串（蓝图 §8.1 明确禁止 shell 插值）；
- `max_cpu_cores / max_wall_seconds / max_memory_gb ≥ 1`，`max_gpu_count ≥ 0`；
- 布尔值不得冒充整数资源（Python 中 `True == 1`，显式拒绝）；
- 作业状态只能是 6 个声明状态之一。

## 运行

服务器系统 Python **没有 pip**（见 `docs/BLOCKERS.md` B-004），因此不安装包，直接用 `PYTHONPATH`：

```sh
PYTHONPATH=scientific/src python3 -m unittest discover -s scientific/tests -v
PYTHONPATH=scientific/src python3 -m evovs_science.cli validate-spec scientific/examples/job_spec.example.json
```

## 明确未实现（Phase 1 P1-02..P1-06）

沙箱执行、资源硬限、工件注册表、幂等命中、取消/超时/恢复、RDKit 与模型适配器。
`run-job` 会以退出码 3 明确报"未实现"，不返回假成功。

#!/usr/bin/env python3
"""List the new research modules and test in docs/007 (idempotent).

`tests/docs.spec.ts` fails if any file under `src/` or any `tests/*.spec.ts` is
missing from those two tables, so this is part of adding a module, not a nicety.
"""
import pathlib

root = pathlib.Path.home() / "evo_vs_rsi"
path = root / "docs/007-architecture.md"
source = path.read_text(encoding="utf-8")
changed = False

MODULE_ROWS = [
    ("| `src/research/registry.ts` | The whitelisted scientific tools: `tool_id`, capability and failure-code metadata, "
     "a zod input schema, and the fixed argv a job runs — the Agent names a tool and arguments, never a command |"),
    ("| `src/research/job-runner.ts` | The sandboxed runner: `shell: false`, one process group per job, a wall-clock kill, "
     "stdout/stderr files, a sha256 artifact manifest, and `INTERRUPTED` for a job whose host stopped |"),
    ("| `src/research/tools.ts` | The worker tools `scientific_tools`, `scientific_run_job`, `scientific_job_status`, "
     "`scientific_read_artifact` and `scientific_cancel_job`, registered on every Executor Session |"),
]

anchor = [line for line in source.split("\n") if line.startswith("| `src/sources/local.ts`")]
assert anchor, "module anchor missing"
row_block = "\n".join(row for row in MODULE_ROWS if row.split("|")[1].strip() not in source)
if row_block:
    source = source.replace(anchor[0], anchor[0] + "\n" + row_block, 1)
    changed = True

TEST_ROW = ("| `tests/research.spec.ts` | The scientific tool registry and the sandboxed job runner: schema rejection, "
            "path containment, a sha256 manifest, non-zero exit, wall-clock kill, a missing declared output, and an "
            "abandoned job reported `INTERRUPTED` |")
test_anchor = [line for line in source.split("\n") if line.startswith("| `tests/local.spec.ts`")]
assert test_anchor, "test anchor missing"
if "tests/research.spec.ts" not in source:
    source = source.replace(test_anchor[0], test_anchor[0] + "\n" + TEST_ROW, 1)
    changed = True

if changed:
    path.write_text(source, encoding="utf-8")
print("changed" if changed else "already listed")

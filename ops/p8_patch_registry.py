#!/usr/bin/env python3
"""Expose the frozen search space to the agent, relax the job timeout, add two tools.

Three changes, all required by the experiment design:

1. `ml.train` accepts `config_id` / `workspace` / `budget_limit` so a draw from the
   frozen space is the unit of search and the budget is charged by the tool.
2. `search.space` lets an arm read the space it is allowed to explore (100 entries).
3. `harness.propose` lets the *agent* write a candidate spec, which is the missing
   P4-04 piece: without it only the operator can propose, so the self-evolving arm
   never differs from the memory arm.
4. Job wall time: default 600 s -> 7200 s, cap 3600 s -> 21600 s. A legitimate
   catboost fit was killed at 1200 s, which silently removed configurations from
   one arm's model table and made the wall-clock comparison meaningless.
"""
from pathlib import Path

ROOT = Path("/home/linhan_cluster/evo_vs_rsi")
REGISTRY = ROOT / "src/research/registry.ts"
TOOLS = ROOT / "src/research/tools.ts"
RUNNER = ROOT / "src/research/job-runner.ts"

TRAIN_INPUT_OLD = '''  label_column: z.string().trim().min(1).max(60).optional(),
}).strict()'''
TRAIN_INPUT_NEW = '''  label_column: z.string().trim().min(1).max(60).optional(),
  config_id: z.string().trim().min(1).max(80).optional()
    .describe('One configuration id from `search.space`; charges this ticket\\'s search budget'),
  workspace: DataPath.optional().describe('Ticket directory holding .search_budget.json (default: the cwd)'),
  budget_limit: z.number().int().min(1).max(1000).optional()
    .describe('How many configurations this ticket may draw (default: the whole space)'),
}).strict()'''

TRAIN_ARGV_OLD = '''      '--label-id-column', args.label_id_column ?? 'id', '--label-column', args.label_column ?? 'label',
      ...(args.split_manifest ? ['--split-manifest', args.split_manifest] : []),
    ],'''
TRAIN_ARGV_NEW = '''      '--label-id-column', args.label_id_column ?? 'id', '--label-column', args.label_column ?? 'label',
      ...(args.split_manifest ? ['--split-manifest', args.split_manifest] : []),
      ...(args.config_id ? ['--config-id', args.config_id] : []),
      ...(args.workspace ? ['--workspace', args.workspace] : []),
      ...(args.budget_limit ? ['--budget-limit', String(args.budget_limit)] : []),
    ],'''

REGISTRY_END_OLD = '''      `${args.output_dir}/artifact_manifest.json`,
    ],
  },
]'''
REGISTRY_END_NEW = '''      `${args.output_dir}/artifact_manifest.json`,
    ],
  },
  {
    id: 'search.space',
    version: '0.1.0',
    description: 'List the frozen 100-configuration search space every arm must search. Read it before drawing configurations.',
    capabilities: ['search', 'read'],
    resources: [],
    sideEffects: [],
    failureCodes: [],
    input: z.object({}).strict(),
    argv: (_args, context) => [context.python, '-m', 'evovs_science.search.space', '--list'],
    outputs: () => [],
  },
  {
    id: 'harness.propose',
    version: '0.1.0',
    description: 'Propose a change to the harness itself, as a candidate spec for the shadow/gate pipeline. Use it when the traces show the harness wasting work; the operator still adjudicates promotion.',
    capabilities: ['self-modification', 'write_artifacts'],
    resources: [],
    sideEffects: ['write_artifacts'],
    failureCodes: ['INVALID_SPEC'],
    input: z.object({
      candidate_id: z.string().trim().min(3).max(80)
        .describe('Stable id, e.g. preflight-ml-train-columns'),
      hypothesis: z.string().trim().min(10).max(2000)
        .describe('What waste this removes, and the evidence you saw in the traces'),
      risk: z.string().trim().min(5).max(1000),
      change_key: z.string().trim().min(3).max(120).describe('e.g. preflight:ml.train'),
      change_value: z.string().trim().min(5).max(2000),
      acceptance_json: z.string().trim().min(2).max(400)
        .describe('JSON object, e.g. {"equivalence":1.0,"early_rejection":true}'),
      output_dir: RelativePath.default('harness_candidates'),
    }).strict(),
    argv: (args, context) => [
      context.python, '-m', 'evovs_science.harness.propose',
      '--candidate-id', args.candidate_id, '--hypothesis', args.hypothesis, '--risk', args.risk,
      '--change-key', args.change_key, '--change-value', args.change_value,
      '--acceptance-json', args.acceptance_json, '--output-dir', args.output_dir,
    ],
    outputs: (args) => [`${args.output_dir}/${args.candidate_id}.json`],
  },
]'''

TOOLS_CAP_OLD = "max_wall_seconds: z.number().int().min(1).max(3600).optional().describe('Seconds')"
TOOLS_CAP_NEW = "max_wall_seconds: z.number().int().min(1).max(21600).optional().describe('Seconds; up to 6 h, so a slow fit is measured rather than killed')"

RUNNER_OLD = "const DEFAULT_RESOURCES: JobResources = { max_cpu_cores: 2, max_gpu_count: 0, max_wall_seconds: 600, max_memory_gb: 32 }"
RUNNER_NEW = "const DEFAULT_RESOURCES: JobResources = { max_cpu_cores: 2, max_gpu_count: 0, max_wall_seconds: 7200, max_memory_gb: 32 }"


def patch(path: Path, pairs: list[tuple[str, str]]) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in pairs:
        if old not in text:
            print(f"{path.name}: ANCHOR MISSING -> {old.splitlines()[0][:60]}")
            return False
        text = text.replace(old, new, 1)
    if text == original:
        print(f"{path.name}: unchanged")
        return False
    path.write_text(text, encoding="utf-8")
    print(f"{path.name}: patched")
    return True


def main() -> int:
    ok = patch(REGISTRY, [(TRAIN_INPUT_OLD, TRAIN_INPUT_NEW),
                          (TRAIN_ARGV_OLD, TRAIN_ARGV_NEW),
                          (REGISTRY_END_OLD, REGISTRY_END_NEW)])
    ok = patch(TOOLS, [(TOOLS_CAP_OLD, TOOLS_CAP_NEW)]) and ok
    ok = patch(RUNNER, [(RUNNER_OLD, RUNNER_NEW)]) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

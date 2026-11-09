#!/usr/bin/env python3
"""Second pass: give `harness.propose` a named schema so its callbacks are typed.

The first pass inlined the proposal schema, so `z.infer` resolved the argv/outputs
parameters to `never` and `pnpm typecheck` failed. This hoists the schema into a
`ProposalInput` const and points the tool at it.
"""
from pathlib import Path

REGISTRY = Path("/home/linhan_cluster/evo_vs_rsi/src/research/registry.ts")

INLINE = '''    input: z.object({
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
    argv: (args, context) => ['''

NAMED = '''    input: ProposalInput,
    argv: (args: z.infer<typeof ProposalInput>, context) => ['''

HEAD_OLD = "const SCIENTIFIC_TOOLS_BASE: readonly ScientificToolDefinition[] = ["
HEAD_NEW = '''// Hoisted so z.infer can type the argv/outputs callbacks; an inline schema makes
// those parameters resolve to `never` and fails typecheck.
const ProposalInput = z.object({
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
}).strict()

''' + HEAD_OLD


def main() -> int:
    text = REGISTRY.read_text(encoding="utf-8")
    if "const ProposalInput" in text:
        print("registry.ts: already hoisted")
        return 0
    if INLINE not in text:
        print("registry.ts: inline schema anchor missing")
        return 1
    text = text.replace(INLINE, NAMED, 1)
    if HEAD_OLD not in text:
        print("registry.ts: array anchor missing")
        return 1
    text = text.replace(HEAD_OLD, HEAD_NEW, 1)
    text = text.replace("    outputs: (args) => [`${args.output_dir}/${args.candidate_id}.json`],",
                        "    outputs: (args: z.infer<typeof ProposalInput>) => "
                        "[`${args.output_dir}/${args.candidate_id}.json`],", 1)
    REGISTRY.write_text(text, encoding="utf-8")
    print("registry.ts: ProposalInput hoisted and callbacks typed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

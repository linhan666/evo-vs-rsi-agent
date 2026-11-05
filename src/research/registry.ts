/**
 * Whitelisted scientific tools (Blueprint §8.1, §16.1).
 *
 * The Agent never supplies an argv. It names a `tool_id` and validated arguments;
 * this module turns that into a fixed argv with no shell interpretation. Paths are
 * resolved inside the ticket workspace and may not escape it.
 */
import { isAbsolute, normalize, resolve, sep } from 'node:path'
import { z } from 'zod'

export interface ToolContext {
  /** Absolute interpreter path, from `EVOVS_PYTHON`; never guessed. */
  python: string
}

export interface ScientificToolDefinition {
  id: string
  version: string
  description: string
  capabilities: string[]
  resources: ('cpu' | 'gpu')[]
  sideEffects: string[]
  failureCodes: string[]
  input: z.ZodType
  /** Fixed argv; the runner executes it without a shell. */
  argv(args: never, context: ToolContext): string[]
  /** Files the run must produce, relative to the workspace. */
  outputs(args: never): string[]
}

/** Resolve a caller-supplied relative path, refusing anything outside the workspace. */
export function withinWorkspace(workspace: string, relative: string): string {
  if (isAbsolute(relative)) throw new Error(`path must be relative to the workspace: ${relative}`)
  const target = resolve(workspace, normalize(relative))
  const root = resolve(workspace) + sep
  if (target !== resolve(workspace) && !target.startsWith(root)) throw new Error(`path escapes the workspace: ${relative}`)
  return target
}

const RelativePath = z.string().trim().min(1).max(300)
  .refine(value => !isAbsolute(value) && !value.split(/[\\/]/).includes('..'), 'Use a relative path inside the workspace')

const FeaturizeInput = z.object({
  input: RelativePath.describe('CSV with id,smiles (or a .smi file), relative to the workspace'),
  output: RelativePath.describe('Output .npz path'),
  report: RelativePath.describe('Output feature report .json path'),
  radius: z.number().int().min(1).max(4).default(2),
  n_bits: z.number().int().min(256).max(4096).default(2048),
  limit: z.number().int().min(0).max(200000).default(0),
}).strict()

const TrainInput = z.object({
  features: RelativePath.describe('npz produced by rdkit.featurize'),
  labels: RelativePath.describe('CSV with id,label'),
  output_dir: RelativePath.describe('Directory for metrics, predictions and the fitted model'),
  model: z.enum(['logreg', 'rf']).default('logreg'),
  seed: z.number().int().min(0).max(1_000_000).default(17),
  test_fraction: z.number().min(0.1).max(0.5).default(0.3),
  label_source: z.string().trim().min(1).max(60).default('fixture')
    .describe('Where the labels come from; "fixture" keeps a synthetic set from being reported as measured activity'),
}).strict()

export const SCIENTIFIC_TOOLS: readonly ScientificToolDefinition[] = [
  {
    id: 'rdkit.featurize',
    version: '0.1.0',
    description: 'Compute Morgan fingerprints and 2D descriptors from SMILES. Invalid SMILES are skipped and reported, never replaced.',
    capabilities: ['smiles', 'fingerprints', 'descriptors'],
    resources: ['cpu'],
    sideEffects: ['write_artifacts'],
    failureCodes: ['INPUT_NOT_FOUND', 'NO_VALID_MOLECULES'],
    input: FeaturizeInput,
    argv: (args: z.infer<typeof FeaturizeInput>, context) => [
      context.python, '-m', 'evovs_science.chemistry.featurize',
      '--input', args.input, '--output', args.output, '--report', args.report,
      '--radius', String(args.radius), '--n-bits', String(args.n_bits), '--limit', String(args.limit),
    ],
    outputs: (args: z.infer<typeof FeaturizeInput>) => [args.output, args.report],
  },
  {
    id: 'sklearn.train',
    version: '0.1.0',
    description: 'Train a small classifier on featurized molecules and report AUROC, AUPRC, EF@1% and counts. Refuses to invent negatives.',
    capabilities: ['classification', 'metrics', 'enrichment'],
    resources: ['cpu'],
    sideEffects: ['write_artifacts'],
    failureCodes: ['NOT_ENOUGH_RELIABLE_DATA', 'FEATURE_SHAPE_MISMATCH'],
    input: TrainInput,
    argv: (args: z.infer<typeof TrainInput>, context) => [
      context.python, '-m', 'evovs_science.modeling.train',
      '--features', args.features, '--labels', args.labels, '--output-dir', args.output_dir,
      '--model', args.model, '--seed', String(args.seed), '--test-fraction', String(args.test_fraction),
      '--label-source', args.label_source,
    ],
    outputs: (args: z.infer<typeof TrainInput>) => [
      `${args.output_dir}/metrics.json`, `${args.output_dir}/predictions.csv`, `${args.output_dir}/model.joblib`,
      `${args.output_dir}/artifact_manifest.json`,
    ],
  },
]

export function findTool(id: string): ScientificToolDefinition {
  const found = SCIENTIFIC_TOOLS.find(item => item.id === id)
  if (!found) throw new Error(`unknown scientific tool: ${id}; call scientific_tools for the list`)
  return found
}

/** Metadata for discovery; the JSON Schema comes from the same zod object the runner validates with. */
export function describeTools() {
  return SCIENTIFIC_TOOLS.map(item => ({
    tool_id: item.id,
    version: item.version,
    description: item.description,
    capabilities: item.capabilities,
    resources: item.resources,
    side_effects: item.sideEffects,
    failure_codes: item.failureCodes,
    input_schema: z.toJSONSchema(item.input),
  }))
}

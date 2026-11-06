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

/** Read-only roots outside the ticket, from `EVOVS_DATA_ROOT` (colon-separated). */
const DATA_ROOTS = (process.env.EVOVS_DATA_ROOT ?? '').split(':').filter(Boolean)
  .map(root => resolve(root) + sep)

/**
 * Inputs may live in a read-only data root so a ticket can read a snapshot without
 * copying it (the worker has no shell to copy with). Outputs stay inside the ticket.
 */
const DataPath = z.string().trim().min(1).max(400)
  .refine(value => {
    if (value.split(/[\\/]/).includes('..')) return false
    if (!isAbsolute(value)) return true
    return DATA_ROOTS.some(root => resolve(value).startsWith(root))
  }, 'Use a relative path inside the workspace, or an absolute path under EVOVS_DATA_ROOT')

const FeaturizeInput = z.object({
  input: DataPath.describe('CSV with id,smiles (or a .smi file); relative, or absolute under the data root'),
  output: RelativePath.describe('Output .npz path'),
  report: RelativePath.describe('Output feature report .json path'),
  radius: z.number().int().min(1).max(4).default(2),
  n_bits: z.number().int().min(256).max(4096).default(2048),
  limit: z.number().int().min(0).max(200000).default(0),
  id_column: z.string().trim().min(1).max(60).default('id'),
  smiles_column: z.string().trim().min(1).max(60).default('smiles'),
  desc_set: z.enum(['v1', 'v2']).default('v1'),
}).strict()

const TrainInput = z.object({
  features: DataPath.describe('npz produced by rdkit.featurize, or one under the data root'),
  labels: DataPath.describe('CSV with id,label, or one under the data root'),
  output_dir: RelativePath.describe('Directory for metrics, predictions and the fitted model'),
  model: z.enum(['logreg', 'rf', 'xgboost', 'catboost']).default('logreg'),
  seed: z.number().int().min(0).max(1_000_000).default(17),
  test_fraction: z.number().min(0.1).max(0.5).default(0.3),
  label_source: z.string().trim().min(1).max(60).default('fixture')
    .describe('Where the labels come from; "fixture" keeps a synthetic set from being reported as measured activity'),
  split_manifest: DataPath.optional().describe('split_manifest.json: train on scaffold-train, report on scaffold-validation'),
  label_id_column: z.string().trim().min(1).max(60).optional(),
  label_column: z.string().trim().min(1).max(60).optional(),
}).strict()

const RankInput = z.object({
  model: RelativePath.describe('Fitted pipeline from ml.train, relative to the workspace'),
  library: DataPath.describe('SMILES library (.smi/.csv); relative, or absolute under the data root'),
  output: RelativePath.describe('Ranked CSV, best first'),
  top_output: RelativePath.describe('Top-K CSV'),
  report: RelativePath.describe('Screening report json'),
  top_k: z.number().int().min(1).max(100000).default(100),
  radius: z.number().int().min(1).max(4).default(2),
  n_bits: z.number().int().min(256).max(4096).default(2048),
}).strict()

const SCIENTIFIC_TOOLS_APPEND = {
  id: 'screening.rank',
  version: '0.1.0',
  description: 'Score an unlabeled library with a fitted model and rank it best-first; writes full ranking, top-K and a report. Predictions only: no hit rate is defined for an unlabeled library.',
  capabilities: ['virtual_screening', 'ranking'],
  resources: ['cpu'],
  sideEffects: ['write_artifacts'],
  failureCodes: ['MODEL_NOT_FOUND', 'LIBRARY_UNREADABLE', 'NO_VALID_MOLECULES'],
  input: RankInput,
  argv: (args: z.infer<typeof RankInput>, context) => [
    context.python, '-m', 'evovs_science.screening.predict',
    '--model', args.model, '--library', args.library, '--output', args.output,
    '--top-output', args.top_output, '--report', args.report,
    '--top-k', String(args.top_k), '--radius', String(args.radius), '--n-bits', String(args.n_bits),
  ],
  outputs: (args: z.infer<typeof RankInput>) => [args.output, args.top_output, args.report],
} as ScientificToolDefinition

const SplitInput = z.object({
  input: DataPath.describe('CSV with id and smiles columns'),
  output: RelativePath.describe('split manifest json consumed by ml.train via --split-manifest'),
  strategy: z.enum(['random', 'scaffold']).describe('scaffold = Bemis-Murcko, the main generalisation check; random = optimistic diagnostic baseline'),
  test_fraction: z.coerce.number().min(0.05).max(0.6).default(0.3),
  val_fraction: z.coerce.number().min(0.0).max(0.4).default(0.1),
  seed: z.coerce.number().int().default(17),
  id_column: z.string().trim().min(1).default('id'),
  smiles_column: z.string().trim().min(1).default('smiles'),
}).strict()

const SPLIT_TOOL = {
  id: 'data.split',
  version: '0.1.0',
  description: 'Make a train/val/test split manifest with a declared strategy. Scaffold split (Bemis-Murcko) is the generalisation check; random split is optimistic and must not be the only result. The strategy is recorded in the manifest.',
  capabilities: ['split', 'scaffold', 'validation'],
  resources: ['cpu'],
  sideEffects: ['write_artifacts'],
  failureCodes: ['INPUT_NOT_FOUND', 'NOT_ENOUGH_RELIABLE_DATA'],
  input: SplitInput,
  argv: (args: z.infer<typeof SplitInput>, context) => [
    context.python, '-m', 'evovs_science.data.split',
    '--input', args.input, '--output', args.output, '--strategy', args.strategy,
    '--test-fraction', String(args.test_fraction), '--val-fraction', String(args.val_fraction),
    '--seed', String(args.seed), '--id-column', args.id_column, '--smiles-column', args.smiles_column,
  ],
  outputs: (args: z.infer<typeof SplitInput>) => [args.output],
} as ScientificToolDefinition

const SCIENTIFIC_TOOLS_BASE: readonly ScientificToolDefinition[] = [
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
      '--id-column', args.id_column, '--smiles-column', args.smiles_column,
      '--desc-set', args.desc_set,
    ],
    outputs: (args: z.infer<typeof FeaturizeInput>) => [args.output, args.report],
  },
  SPLIT_TOOL as ScientificToolDefinition,
  {
    id: 'ml.train',
    version: '0.1.0',
    description: 'Train a small classifier (logreg, rf, xgboost, catboost) on featurized molecules; reports AUROC, AUPRC, EF@1% and counts. Refuses to invent negatives.',
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
      '--label-id-column', args.label_id_column ?? 'id', '--label-column', args.label_column ?? 'label',
      ...(args.split_manifest ? ['--split-manifest', args.split_manifest] : []),
    ],
    outputs: (args: z.infer<typeof TrainInput>) => [
      `${args.output_dir}/metrics.json`, `${args.output_dir}/predictions.csv`, `${args.output_dir}/model.joblib`,
      `${args.output_dir}/artifact_manifest.json`,
    ],
  },
]

const ExperienceInput = z.object({
  target: z.string().trim().min(1).max(60).optional(),
  kind: z.enum(['dataset', 'model', 'screening', 'transfer', 'harness']).optional(),
  store: DataPath.describe('Experience store json; absolute under the data root or relative'),
  out: RelativePath.describe('Where the retrieval result is written'),
}).strict()

const EXPERIENCE_TOOL = {
  id: 'experience.retrieve',
  version: '0.1.0',
  description: 'Read past experiences (dataset/model/screening facts with provenance and applicability limits). Facts are context only: check each applicability note before relying on one.',
  capabilities: ['experience', 'provenance'],
  resources: ['cpu'],
  sideEffects: ['write_artifacts'],
  failureCodes: ['STORE_UNREADABLE'],
  input: ExperienceInput,
  argv: (args: z.infer<typeof ExperienceInput>, context) => [
    context.python, '-m', 'evovs_science.experience.store', 'retrieve',
    '--store', args.store, '--out', args.out,
    ...(args.target ? ['--target', args.target] : []),
    ...(args.kind ? ['--kind', args.kind] : []),
  ],
  outputs: (args: z.infer<typeof ExperienceInput>) => [args.out],
} as ScientificToolDefinition

const LockedInput = z.object({
  target: z.enum(['MOR', 'KOR', 'DRD2']),
  endpoint: z.enum(['Ki', 'IC50']).default('Ki').describe('Locked channel; must match the labels the model was trained on'),
  model: RelativePath.describe('Fitted pipeline FILE from ml.train in this workspace'),
  receipt: RelativePath.describe('Where the summary receipt is written'),
  desc_set: z.enum(['v1', 'v2']).default('v1'),
}).strict()

const LOCKED_TOOL = {
  id: 'evaluation.locked',
  version: '0.2.0',
  description: 'Trigger a locked final-test evaluation for a model in this workspace. Test set and output location are fixed per target and endpoint (Ki or IC50); the raw result stays in the protected tree — you get a receipt with summary metrics. One evaluation per target per endpoint per ticket.',
  capabilities: ['evaluation', 'locked_test'],
  resources: ['cpu'],
  sideEffects: ['write_artifacts'],
  failureCodes: ['RATE_LIMITED', 'MODEL_NOT_FOUND'],
  input: LockedInput,
  argv: (args: z.infer<typeof LockedInput>, context) => [
    context.python, '-m', 'evovs_science.evaluation.locked',
    '--target', args.target, '--endpoint', args.endpoint, '--model', args.model,
    '--workspace', '.', '--receipt', args.receipt,
    '--desc-set', args.desc_set,
  ],
  outputs: (args: z.infer<typeof LockedInput>) => [args.receipt],
} as ScientificToolDefinition

/**
 * Phase 6 experimental group (`EVOVS_GROUP`): `fixed` (group A) hides cross-task
 * experience retrieval, so the comparison separates "memory" from "self-modification";
 * `memory` (M) and `rsi` (R) both see it. Group W has no agent and never reaches
 * this registry at all.
 */
export function experimentGroup(): string {
  return (process.env.EVOVS_GROUP || 'rsi').toLowerCase()
}

const HIDDEN_BY_GROUP: Record<string, readonly string[]> = {
  fixed: ['experience.retrieve'],
  workflow: ['experience.retrieve'],
  memory: [],
  rsi: [],
}

export function toolsForGroup(group: string): readonly ScientificToolDefinition[] {
  return [...SCIENTIFIC_TOOLS_BASE, SCIENTIFIC_TOOLS_APPEND, EXPERIENCE_TOOL, LOCKED_TOOL]
    .filter(tool => !(HIDDEN_BY_GROUP[group] ?? []).includes(tool.id))
}

export const SCIENTIFIC_TOOLS: readonly ScientificToolDefinition[] = toolsForGroup(experimentGroup())


export function findTool(id: string): ScientificToolDefinition {
  const found = SCIENTIFIC_TOOLS.find(item => item.id === id)
  if (!found) throw new Error(`unknown scientific tool: ${id}; call scientific_tools for the list`)
  return found
}

/**
 * Metadata for discovery; the JSON Schema comes from the same zod object the runner
 * validates with. The result is normalised through JSON because `z.toJSONSchema`
 * may return non-plain objects, and DSH rejects a tool result that is not lossless
 * JSON (`isJsonValue` checks the prototype, not just `JSON.stringify`).
 */
export function describeTools() {
  const described = SCIENTIFIC_TOOLS.map(item => ({
    tool_id: item.id,
    version: item.version,
    description: item.description,
    capabilities: item.capabilities,
    resources: item.resources,
    side_effects: item.sideEffects,
    failure_codes: item.failureCodes,
    input_schema: z.toJSONSchema(item.input),
  }))
  return JSON.parse(JSON.stringify(described)) as typeof described
}

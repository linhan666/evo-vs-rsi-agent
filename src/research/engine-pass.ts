/**
 * Engine pass (docs/EVALUATOR_TRIGGER_DESIGN.md §方案 3, P5 item): the Harness, not
 * the Agent, triggers the locked evaluation once a ticket reports `ready`.
 *
 * Properties that keep this safe:
 *  - the plan is derived from the ticket's own job records (labels path + label
 *    source + model artifact), never from the worker's prose;
 *  - it reuses `evaluation.locked`, so the test set, the protected output path
 *    and the rate-limit marker are identical to the Agent-triggered path — at
 *    most one evaluation per (target, endpoint) per ticket, whichever fires first;
 *  - every failure is swallowed by the caller: an evaluation problem must never
 *    block or fail a ticket that has already finished its work.
 */
import { execFile } from 'node:child_process'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

export type Target = 'MOR' | 'KOR' | 'DRD2'
export type Endpoint = 'Ki' | 'IC50'

export interface EnginePassPlan {
  target: Target
  endpoint: Endpoint
  descSet: 'v1' | 'v2'
  model: string
}

/** ChEMBL snapshot directories as they appear under `scientific/.artifacts/chembl/`. */
const TARGET_BY_DIRECTORY: Record<string, Target> = { oprm1: 'MOR', oprk1: 'KOR', drd2: 'DRD2' }

function flag(argv: readonly string[], name: string): string | undefined {
  const at = argv.indexOf(name)
  return at >= 0 && at + 1 < argv.length ? argv[at + 1] : undefined
}

function jobs(ticketDir: string): { id: string, record: Record<string, unknown> }[] {
  const root = join(ticketDir, '.jobs')
  if (!existsSync(root)) return []
  const records: { id: string, record: Record<string, unknown> }[] = []
  for (const id of readdirSync(root).filter(name => /^[0-9a-f]{12}$/.test(name)).sort()) {
    const path = join(root, id, 'result.json')
    if (!existsSync(path)) continue
    try {
      records.push({ id, record: JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown> })
    } catch { /* a half-written result.json is not a plan */ }
  }
  return records
}

/**
 * Derive what should be evaluated, or explain why nothing should.
 * `descSet` comes from the label source, which `ml.train` records verbatim.
 */
export function planEnginePass(ticketDir: string): EnginePassPlan | { reason: string } {
  const trained = jobs(ticketDir)
    .filter(item => item.record.tool_id === 'ml.train' && item.record.state === 'SUCCEEDED')
    .sort((a, b) => String(a.record.started_at ?? '').localeCompare(String(b.record.started_at ?? '')))
  if (trained.length === 0) return { reason: 'no successful ml.train job in this ticket' }

  const latest = trained[trained.length - 1]!.record
  const argv = (latest.argv as string[] | undefined) ?? []
  const labelSource = flag(argv, '--label-source')
  const labelsPath = flag(argv, '--labels')
  if (!labelSource || !labelsPath) return { reason: 'ml.train argv lacks --label-source or --labels' }

  const directory = labelsPath.split('/').find(part => part in TARGET_BY_DIRECTORY)
  const target = directory ? TARGET_BY_DIRECTORY[directory] : undefined
  if (!target) return { reason: `cannot tell the target from ${labelsPath}` }

  const endpoint: Endpoint = /ic50/i.test(labelSource) || /\/ic50\//.test(labelsPath) ? 'IC50' : 'Ki'
  if (endpoint === 'Ki' && !/ki/i.test(labelSource)) return { reason: `label source ${labelSource} names no endpoint` }

  const descSet = /_descv2\b/i.test(labelSource) ? 'v2' : 'v1'
  const model = ((latest.artifacts as { path?: string }[] | undefined) ?? [])
    .map(item => item.path)
    .find(path => typeof path === 'string' && path.endsWith('model.joblib'))
  if (!model) return { reason: 'the ml.train record lists no model.joblib artifact' }

  return { target, endpoint, descSet, model: join(ticketDir, model) }
}

/** Same marker the Agent-triggered tool uses, so the two paths cannot both evaluate. */
export function markerPath(ticketDir: string, plan: EnginePassPlan): string {
  return join(ticketDir, '.evaluation', `${plan.target}_${plan.endpoint}.done`)
}

export interface EnginePassResult {
  ran: boolean
  reason?: string
  receipt?: string
}

/**
 * Run the locked evaluation for a finished ticket. Never throws: the caller is a
 * tool handler that has already recorded the report, and an evaluation problem
 * must not turn a finished ticket into a failed one.
 */
export async function runEnginePass(ticketDir: string, python: string | undefined): Promise<EnginePassResult> {
  if (!python) return { ran: false, reason: 'EVOVS_PYTHON is not set' }
  const plan = planEnginePass(ticketDir)
  if ('reason' in plan) return { ran: false, reason: plan.reason }
  if (existsSync(markerPath(ticketDir, plan))) return { ran: false, reason: 'already evaluated in this ticket' }

  const receipt = join(ticketDir, 'runs', 'evaluation', 'engine_receipt.json')
  const argv = ['-m', 'evovs_science.evaluation.locked',
    '--target', plan.target, '--endpoint', plan.endpoint, '--desc-set', plan.descSet,
    '--model', plan.model, '--workspace', ticketDir, '--receipt', receipt]
  return new Promise<EnginePassResult>(resolve => {
    execFile(python, argv, { cwd: ticketDir, timeout: 600_000, env: { ...process.env, HOME: ticketDir } },
      error => resolve(error ? { ran: false, reason: String(error).slice(0, 200) } : { ran: true, receipt }))
  })
}

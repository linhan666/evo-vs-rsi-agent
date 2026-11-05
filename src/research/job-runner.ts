/**
 * Sandboxed job runner for scientific tools (Blueprint §8.1, P1-02/P1-04).
 *
 * Properties the rest of the system relies on:
 *  - `shell: false`: the argv comes from the registry, never from the model;
 *  - the child runs in its own process group, so a timeout kills the whole tree;
 *  - `prlimit` caps address space and disables core dumps when it is available;
 *  - stdout/stderr go to files, and every declared output gets a sha256;
 *  - a job that disappears with the host is reported `INTERRUPTED` on the next read;
 *  - the same tool + arguments + input digests reuse a finished job instead of
 *    recomputing it. Different seeds are different arguments, so they never collide.
 */
import { spawn, type ChildProcess } from 'node:child_process'
import { createHash } from 'node:crypto'
import { createReadStream, existsSync, mkdirSync, openSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { isAbsolute, join, relative } from 'node:path'
import { randomBytes } from 'node:crypto'

import type { ScientificToolDefinition } from './registry.ts'

export type JobState = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED' | 'TIMED_OUT' | 'INTERRUPTED'

export interface JobResources {
  max_cpu_cores: number
  max_gpu_count: number
  max_wall_seconds: number
  max_memory_gb: number
}

export interface JobArtifact {
  path: string
  sha256: string
  size: number
}

export interface JobRecord {
  job_id: string
  tool_id: string
  tool_version: string
  state: JobState
  started_at: string
  ended_at?: string
  exit_code?: number | null
  signal?: string | null
  argv: string[]
  artifacts: JobArtifact[]
  usage: { wall_seconds: number; cpu_seconds: number | null; gpu_seconds: null; max_rss_mb: number | null }
  idempotency_key?: string
  reused?: boolean
  error?: string
}

export interface RunOptions {
  workspace: string
  python: string
  resources?: Partial<JobResources>
  signal?: AbortSignal
  /** Defaults to a digest of tool id, version, arguments and the digests of input files that exist. */
  idempotencyKey?: string
}

interface IndexEntry { job_id: string; state: JobState; tool_id: string; created_at: string }

/** Live children, so `cancel` and status reads can tell a running job from an abandoned one. */
const running = new Map<string, ChildProcess>()

const DEFAULT_RESOURCES: JobResources = { max_cpu_cores: 2, max_gpu_count: 0, max_wall_seconds: 600, max_memory_gb: 8 }
const PRLIMIT = '/usr/bin/prlimit'
const CLOCK_TICKS = 100

function sha256File(path: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const hash = createHash('sha256')
    createReadStream(path)
      .on('data', chunk => hash.update(chunk))
      .on('error', reject)
      .on('end', () => resolve(hash.digest('hex')))
  })
}

const sha256Text = (text: string): string => createHash('sha256').update(text).digest('hex')

/** Digests of the input files the arguments name, so editing a dataset changes the key. */
function inputDigest(workspace: string, args: unknown): string {
  const parts: string[] = []
  const visit = (value: unknown): void => {
    if (typeof value === 'string') {
      if (value.split(/[\\/]/).includes('..')) return
      // An absolute input is a read-only data-root path the schema already checked.
      const path = isAbsolute(value) ? value : join(workspace, value)
      try {
        if (!statSync(path).isFile()) return
        const size = statSync(path).size
        // Hashing a huge file on every submission would be wasteful; size marks it instead.
        parts.push(`${value}:${size <= 64 * 1024 * 1024 ? sha256FileSync(path) : `size:${size}`}`)
      } catch { /* not a file: not an input */ }
    } else if (Array.isArray(value)) value.forEach(visit)
    else if (value && typeof value === 'object') Object.values(value as Record<string, unknown>).forEach(visit)
  }
  visit(args)
  return parts.sort().join('|')
}

function sha256FileSync(path: string): string {
  return createHash('sha256').update(readFileSync(path)).digest('hex')
}

export function idempotencyKeyFor(definition: ScientificToolDefinition, argv: string[], args: unknown, workspace: string): string {
  // The argv is part of the key: two definitions that share an id but build
  // different commands must not reuse each other's result.
  return sha256Text(JSON.stringify({ tool: definition.id, version: definition.version, argv, inputs: inputDigest(workspace, args) }))
}

function childEnvironment(resources: JobResources, workspace: string): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {
    PYTHONHASHSEED: '0',
    OMP_NUM_THREADS: String(resources.max_cpu_cores),
    MKL_NUM_THREADS: String(resources.max_cpu_cores),
    // Single-GPU policy: GPU0/1 belong to other people's jobs.
    CUDA_VISIBLE_DEVICES: resources.max_gpu_count > 0 ? (process.env.EVOVS_GPU ?? '2') : '',
  }
  for (const key of ['PATH', 'LANG', 'LC_ALL', 'TMPDIR', 'TZ']) {
    const value = process.env[key]
    if (value !== undefined) env[key] = value
  }
  // HOME is the workspace: a job that touches ~ lands in the ticket directory, not in
  // the operator's home (same-user limitation, B-005). Library caches follow.
  env.HOME = workspace
  return env
}

const jobDirectory = (workspace: string, jobId: string): string => join(workspace, '.jobs', jobId)
const indexPath = (workspace: string): string => join(workspace, '.jobs', 'index.json')

function readIndex(workspace: string): Record<string, IndexEntry> {
  try { return JSON.parse(readFileSync(indexPath(workspace), 'utf8')) as Record<string, IndexEntry> } catch { return {} }
}

function writeIndex(workspace: string, index: Record<string, IndexEntry>): void {
  mkdirSync(join(workspace, '.jobs'), { recursive: true })
  writeFileSync(indexPath(workspace), `${JSON.stringify(index, null, 2)}\n`, 'utf8')
}

async function collectArtifacts(workspace: string, paths: string[]): Promise<JobArtifact[]> {
  const artifacts: JobArtifact[] = []
  for (const path of paths) {
    if (!existsSync(path) || !statSync(path).isFile()) continue
    artifacts.push({ path: relative(workspace, path), sha256: await sha256File(path), size: statSync(path).size })
  }
  return artifacts
}

function writeRecord(directory: string, name: string, record: unknown): void {
  writeFileSync(join(directory, name), `${JSON.stringify(record, null, 2)}\n`, 'utf8')
}

/** `prlimit` caps address space and core dumps; without it the process is started as-is. */
function commandFor(argv: string[], resources: JobResources): { file: string; args: string[] } {
  if (!existsSync(PRLIMIT)) return { file: argv[0]!, args: argv.slice(1) }
  const bytes = Math.max(1, resources.max_memory_gb) * 1024 ** 3
  return { file: PRLIMIT, args: [`--as=${bytes}`, `--core=0`, '--', ...argv] }
}

/** Run one whitelisted tool and resolve when the child exits, times out, or fails to start. */
export async function runScientificJob(
  definition: ScientificToolDefinition,
  rawArgs: unknown,
  options: RunOptions,
): Promise<JobRecord> {
  const args = definition.input.parse(rawArgs) as never
  const resources: JobResources = { ...DEFAULT_RESOURCES, ...options.resources }
  const argv = definition.argv(args, { python: options.python })
  const key = options.idempotencyKey ?? idempotencyKeyFor(definition, argv, args, options.workspace)

  const hit = readIndex(options.workspace)[key]
  if (hit) {
    const prior = jobStatus(options.workspace, hit.job_id)
    if (prior?.state === 'SUCCEEDED') return { ...prior, reused: true, idempotency_key: key }
  }

  const jobId = randomBytes(6).toString('hex')
  const directory = jobDirectory(options.workspace, jobId)
  mkdirSync(directory, { recursive: true })

  const record: JobRecord = {
    job_id: jobId, tool_id: definition.id, tool_version: definition.version, state: 'PENDING',
    started_at: new Date().toISOString(), argv, artifacts: [], idempotency_key: key,
    usage: { wall_seconds: 0, cpu_seconds: null, gpu_seconds: null, max_rss_mb: null },
  }
  writeRecord(directory, 'job.json', { ...record, state: 'RUNNING', arguments: rawArgs, resources, cwd: options.workspace })

  const stdout = openSync(join(directory, 'stdout.log'), 'a')
  const stderr = openSync(join(directory, 'stderr.log'), 'a')

  return await new Promise<JobRecord>(resolve => {
    let timedOut = false
    let cpuSeconds = 0
    let child: ChildProcess
    const started = Date.now()
    const command = commandFor(argv, resources)
    try {
      child = spawn(command.file, command.args, {
        cwd: options.workspace, env: childEnvironment(resources, options.workspace), shell: false, detached: true,
        stdio: ['ignore', stdout, stderr],
      })
    } catch (error) {
      resolve({ ...record, state: 'FAILED', ended_at: new Date().toISOString(), error: String(error) })
      return
    }
    running.set(jobId, child)
    record.state = 'RUNNING'

    // CPU time is sampled from /proc because Node does not expose a child's rusage.
    const sampler = setInterval(() => {
      if (!child.pid) return
      try {
        const stat = readFileSync(`/proc/${child.pid}/stat`, 'utf8')
        const fields = stat.slice(stat.lastIndexOf(')') + 2).split(' ')
        const ticks = Number(fields[11]) + Number(fields[12])
        if (Number.isFinite(ticks)) cpuSeconds = Math.max(cpuSeconds, Math.round((ticks / CLOCK_TICKS) * 100) / 100)
      } catch { /* the child exited between the read and the sample */ }
    }, 100)
    sampler.unref()

    const timer = setTimeout(() => {
      timedOut = true
      try { if (child.pid) process.kill(-child.pid, 'SIGKILL') } catch { /* already gone */ }
    }, Math.max(1, resources.max_wall_seconds) * 1000)

    const onAbort = () => { try { if (child.pid) process.kill(-child.pid, 'SIGKILL') } catch { /* already gone */ } }
    options.signal?.addEventListener('abort', onAbort, { once: true })

    const finish = async (code: number | null, signal: string | null, error?: string) => {
      clearTimeout(timer)
      clearInterval(sampler)
      options.signal?.removeEventListener('abort', onAbort)
      running.delete(jobId)
      const artifacts = await collectArtifacts(options.workspace, definition.outputs(args).map(path => join(options.workspace, path)))
      const state: JobState = timedOut ? 'TIMED_OUT'
        : options.signal?.aborted ? 'CANCELLED'
          : error ? 'FAILED' : code === 0 ? 'SUCCEEDED' : 'FAILED'
      const finished: JobRecord = {
        ...record, state, ended_at: new Date().toISOString(), exit_code: code, signal,
        artifacts,
        usage: { ...record.usage, wall_seconds: Math.round((Date.now() - started) / 10) / 100, cpu_seconds: cpuSeconds },
        ...(error ? { error } : {}),
      }
      if (state === 'SUCCEEDED' && artifacts.length === 0) {
        finished.state = 'FAILED'
        finished.error = 'the tool exited 0 but produced none of its declared outputs'
      }
      writeRecord(directory, 'result.json', finished)
      writeRecord(directory, 'artifact_manifest.json', {
        schema_version: '1', job_id: jobId, tool_id: definition.id, created_at: finished.ended_at, artifacts,
      })
      const index = readIndex(options.workspace)
      index[key] = { job_id: jobId, state: finished.state, tool_id: definition.id,
        created_at: finished.ended_at ?? finished.started_at }
      writeIndex(options.workspace, index)
      resolve(finished)
    }

    child.on('error', error => { void finish(null, null, String(error)) })
    child.on('close', (code, signal) => { void finish(code, signal) })
  })
}

/** Read a job's result; a job with no result and no live process is reported INTERRUPTED once. */
export function jobStatus(workspace: string, jobId: string): JobRecord | undefined {
  const directory = jobDirectory(workspace, jobId)
  if (!existsSync(join(directory, 'job.json'))) return undefined
  if (existsSync(join(directory, 'result.json'))) {
    return JSON.parse(readFileSync(join(directory, 'result.json'), 'utf8')) as JobRecord
  }
  if (running.has(jobId)) {
    return { ...JSON.parse(readFileSync(join(directory, 'job.json'), 'utf8')), state: 'RUNNING' } as JobRecord
  }
  const job = JSON.parse(readFileSync(join(directory, 'job.json'), 'utf8')) as JobRecord
  const interrupted: JobRecord = { ...job, state: 'INTERRUPTED', ended_at: new Date().toISOString(),
    error: 'the host stopped before the job reported; no result.json was written' }
  writeRecord(directory, 'result.json', interrupted)
  return interrupted
}

/** Kill a running job's process group; returns false when it is not running here. */
export function cancelJob(jobId: string): boolean {
  const child = running.get(jobId)
  if (!child?.pid) return false
  try { process.kill(-child.pid, 'SIGKILL'); return true } catch { return false }
}

export const jobDirectoryOf = (workspace: string, jobId: string): string => jobDirectory(workspace, jobId)

/** Every artifact this ticket has produced, newest job first. */
export function listArtifacts(workspace: string): { job_id: string; path: string; sha256: string; size: number }[] {
  const root = join(workspace, '.jobs')
  if (!existsSync(root)) return []
  const rows: { job_id: string; path: string; sha256: string; size: number }[] = []
  for (const name of readdirSync(root)) {
    if (!/^[0-9a-f]{12}$/.test(name)) continue
    for (const artifact of jobStatus(workspace, name)?.artifacts ?? []) rows.push({ job_id: name, ...artifact })
  }
  return rows.sort((a, b) => b.job_id.localeCompare(a.job_id))
}

/**
 * Sandboxed job runner for scientific tools (Blueprint §8.1, P1-02/P1-04).
 *
 * Properties the rest of the system relies on:
 *  - `shell: false`: the argv comes from the registry, never from the model;
 *  - the child runs in its own process group, so a timeout kills the whole tree;
 *  - stdout/stderr go to files, and every declared output gets a sha256 in a
 *    per-job manifest;
 *  - a job that disappears with the host is reported `INTERRUPTED` on the next
 *    read rather than silently staying `RUNNING`.
 */
import { spawn, type ChildProcess } from 'node:child_process'
import { createHash } from 'node:crypto'
import { createReadStream } from 'node:fs'
import { existsSync, mkdirSync, openSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
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
  usage: { wall_seconds: number; cpu_seconds: null; gpu_seconds: null; max_rss_mb: null }
  error?: string
}

export interface RunOptions {
  workspace: string
  python: string
  resources?: Partial<JobResources>
  signal?: AbortSignal
}

/** Live children, so `cancel` and status reads can tell a running job from an abandoned one. */
const running = new Map<string, ChildProcess>()

const DEFAULT_RESOURCES: JobResources = { max_cpu_cores: 2, max_gpu_count: 0, max_wall_seconds: 600, max_memory_gb: 8 }

function sha256File(path: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const hash = createHash('sha256')
    createReadStream(path)
      .on('data', chunk => hash.update(chunk))
      .on('error', reject)
      .on('end', () => resolve(hash.digest('hex')))
  })
}

function childEnvironment(resources: JobResources): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = {
    PYTHONHASHSEED: '0',
    OMP_NUM_THREADS: String(resources.max_cpu_cores),
    MKL_NUM_THREADS: String(resources.max_cpu_cores),
    // Single-GPU policy: GPU0/1 belong to other people's jobs.
    CUDA_VISIBLE_DEVICES: resources.max_gpu_count > 0 ? (process.env.EVOVS_GPU ?? '2') : '',
  }
  for (const key of ['PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR', 'TZ']) {
    const value = process.env[key]
    if (value !== undefined) env[key] = value
  }
  return env
}

function jobDirectory(workspace: string, jobId: string): string {
  return join(workspace, '.jobs', jobId)
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

/** Run one whitelisted tool and resolve when the child exits, times out, or fails to start. */
export async function runScientificJob(
  definition: ScientificToolDefinition,
  rawArgs: unknown,
  options: RunOptions,
): Promise<JobRecord> {
  const args = definition.input.parse(rawArgs) as never
  const resources: JobResources = { ...DEFAULT_RESOURCES, ...options.resources }
  const argv = definition.argv(args, { python: options.python })
  const jobId = randomBytes(6).toString('hex')
  const directory = jobDirectory(options.workspace, jobId)
  mkdirSync(directory, { recursive: true })

  const startedAt = new Date().toISOString()
  const record: JobRecord = {
    job_id: jobId, tool_id: definition.id, tool_version: definition.version, state: 'PENDING',
    started_at: startedAt, argv, artifacts: [],
    usage: { wall_seconds: 0, cpu_seconds: null, gpu_seconds: null, max_rss_mb: null },
  }
  writeRecord(directory, 'job.json', { ...record, state: 'RUNNING', arguments: rawArgs, resources, cwd: options.workspace })

  const stdout = openSync(join(directory, 'stdout.log'), 'a')
  const stderr = openSync(join(directory, 'stderr.log'), 'a')

  return await new Promise<JobRecord>(resolve => {
    let timedOut = false
    let child: ChildProcess
    const started = Date.now()
    try {
      child = spawn(argv[0]!, argv.slice(1), {
        cwd: options.workspace, env: childEnvironment(resources), shell: false, detached: true,
        stdio: ['ignore', stdout, stderr],
      })
    } catch (error) {
      resolve({ ...record, state: 'FAILED', ended_at: new Date().toISOString(), error: String(error) })
      return
    }
    running.set(jobId, child)
    record.state = 'RUNNING'

    const timer = setTimeout(() => {
      timedOut = true
      try { if (child.pid) process.kill(-child.pid, 'SIGKILL') } catch { /* already gone */ }
    }, Math.max(1, resources.max_wall_seconds) * 1000)

    const onAbort = () => { try { if (child.pid) process.kill(-child.pid, 'SIGKILL') } catch { /* already gone */ } }
    options.signal?.addEventListener('abort', onAbort, { once: true })

    const finish = async (code: number | null, signal: string | null, error?: string) => {
      clearTimeout(timer)
      options.signal?.removeEventListener('abort', onAbort)
      running.delete(jobId)
      const artifacts = await collectArtifacts(options.workspace, definition.outputs(args).map(path => join(options.workspace, path)))
      const state: JobState = timedOut ? 'TIMED_OUT'
        : options.signal?.aborted ? 'CANCELLED'
          : error ? 'FAILED' : code === 0 ? 'SUCCEEDED' : 'FAILED'
      const record2: JobRecord = {
        ...record, state, ended_at: new Date().toISOString(), exit_code: code, signal,
        artifacts, usage: { ...record.usage, wall_seconds: Math.round((Date.now() - started) / 10) / 100 },
        ...(error ? { error } : {}),
      }
      if (state === 'SUCCEEDED' && artifacts.length === 0) {
        record2.state = 'FAILED'
        record2.error = 'the tool exited 0 but produced none of its declared outputs'
      }
      writeRecord(directory, 'result.json', record2)
      writeRecord(directory, 'artifact_manifest.json', {
        schema_version: '1', job_id: jobId, tool_id: definition.id, created_at: record2.ended_at, artifacts,
      })
      resolve(record2)
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

export function jobDirectoryOf(workspace: string, jobId: string): string {
  return jobDirectory(workspace, jobId)
}

import { existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { z } from 'zod'
import { SCIENTIFIC_TOOLS, describeTools, findTool, withinWorkspace, type ScientificToolDefinition } from '../src/research/registry.ts'
import { jobStatus, listArtifacts, runScientificJob } from '../src/research/job-runner.ts'

const roots: string[] = []
afterEach(() => { for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true }) })

function workspace(): string {
  const root = mkdtempSync(join(tmpdir(), 'evovs-job-'))
  roots.push(root)
  return root
}

/** A stub tool that writes argv[1] to out.txt; no shell, no interpolation. */
function writeTool(text: string): ScientificToolDefinition {
  return {
    id: 'test.write', version: '0.0.1', description: 'stub', capabilities: ['test'], resources: ['cpu'],
    sideEffects: ['write_artifacts'], failureCodes: [],
    input: z.object({}).strict(),
    argv: (_args, context) => [context.python, '-c', 'import sys,pathlib;pathlib.Path("out.txt").write_text(sys.argv[1])', text],
    outputs: () => ['out.txt'],
  }
}

function exitTool(code: number): ScientificToolDefinition {
  return {
    id: 'test.exit', version: '0.0.1', description: 'stub', capabilities: ['test'], resources: ['cpu'],
    sideEffects: [], failureCodes: [],
    input: z.object({}).strict(),
    argv: (_args, context) => [context.python, '-c', `import sys; sys.exit(${code})`],
    outputs: () => [],
  }
}

function sleepTool(): ScientificToolDefinition {
  return {
    id: 'test.sleep', version: '0.0.1', description: 'stub', capabilities: ['test'], resources: ['cpu'],
    sideEffects: [], failureCodes: [],
    input: z.object({}).strict(),
    argv: (_args, context) => [context.python, '-c', 'import time; time.sleep(10)'],
    outputs: () => [],
  }
}

const python = 'python3'

describe('scientific registry', () => {
  it('publishes both shipped tools with a JSON Schema the Agent can read', () => {
    const described = describeTools()
    expect(described.map(item => item.tool_id)).toEqual(['rdkit.featurize', 'sklearn.train'])
    for (const item of described) {
      expect(item.input_schema).toBeTruthy()
      expect(item.failure_codes.length).toBeGreaterThan(0)
    }
    expect(SCIENTIFIC_TOOLS.every(item => item.argv.length > 0)).toBe(true)
  })

  it('produces discovery output that survives a JSON round trip', () => {
    const payload = { tools: describeTools(), interpreter_configured: true }
    expect(JSON.parse(JSON.stringify(payload))).toEqual(payload)
  })

  it('refuses unknown tools and paths that leave the workspace', () => {
    expect(() => findTool('nope.nope')).toThrow(/unknown scientific tool/)
    const root = workspace()
    expect(() => withinWorkspace(root, '../etc/passwd')).toThrow(/escapes the workspace/)
    expect(() => withinWorkspace(root, '/etc/passwd')).toThrow(/must be relative/)
    expect(withinWorkspace(root, 'runs/a.json')).toBe(join(root, 'runs/a.json'))
  })

  it('rejects arguments that do not match the tool schema', async () => {
    const root = workspace()
    await expect(runScientificJob(findTool('rdkit.featurize'), { input: 'a.csv' }, { workspace: root, python }))
      .rejects.toThrow()
  })
})

describe('scientific job runner', () => {
  it('records a successful job with a sha256 manifest', async () => {
    const root = workspace()
    const record = await runScientificJob(writeTool('hello-artifact'), {}, { workspace: root, python })
    expect(record.state).toBe('SUCCEEDED')
    expect(record.exit_code).toBe(0)
    expect(record.artifacts).toHaveLength(1)
    expect(record.artifacts[0]).toMatchObject({ path: 'out.txt', size: 14 })
    expect(record.artifacts[0]!.sha256).toMatch(/^[0-9a-f]{64}$/)
    expect(jobStatus(root, record.job_id)?.state).toBe('SUCCEEDED')
  })

  it('reports a non-zero exit as FAILED without pretending it produced output', async () => {
    const root = workspace()
    const record = await runScientificJob(exitTool(3), {}, { workspace: root, python })
    expect(record.state).toBe('FAILED')
    expect(record.exit_code).toBe(3)
  })

  it('kills the process group when the wall limit expires', async () => {
    const root = workspace()
    const started = Date.now()
    const record = await runScientificJob(sleepTool(), {}, { workspace: root, python, resources: { max_wall_seconds: 1 } })
    expect(record.state).toBe('TIMED_OUT')
    expect(Date.now() - started).toBeLessThan(6000)
  })

  it('fails a job that exits 0 but writes none of its declared outputs', async () => {
    const root = workspace()
    const record = await runScientificJob(exitTool(0), {}, { workspace: root, python })
    expect(record.state).toBe('FAILED')
    expect(record.error).toMatch(/none of its declared outputs/)
  })

  it('reuses a finished job for the same tool, arguments and inputs', async () => {
    const root = workspace()
    const first = await runScientificJob(writeTool('same'), {}, { workspace: root, python })
    const second = await runScientificJob(writeTool('same'), {}, { workspace: root, python })
    expect(first.reused).toBeUndefined()
    expect(second.reused).toBe(true)
    expect(second.job_id).toBe(first.job_id)
    expect(listArtifacts(root).map(row => row.path)).toContain('out.txt')
  })

  it('records the CPU time the child actually burned', async () => {
    const root = workspace()
    const busy: ScientificToolDefinition = {
      id: 'test.busy', version: '0.0.1', description: 'stub', capabilities: ['test'], resources: ['cpu'],
      sideEffects: [], failureCodes: [], input: z.object({}).strict(),
      argv: (_args, context) => [context.python, '-c',
        's = 0\nfor i in range(20000000): s += i\nopen("busy.txt", "w").write(str(s))'],
      outputs: () => ['busy.txt'],
    }
    const record = await runScientificJob(busy, {}, { workspace: root, python })
    expect(record.state).toBe('SUCCEEDED')
    expect(record.usage.cpu_seconds).toBeGreaterThan(0)
  })

  it.skipIf(!existsSync('/usr/bin/prlimit'))('enforces the address-space limit', async () => {
    const root = workspace()
    const hog: ScientificToolDefinition = {
      id: 'test.hog', version: '0.0.1', description: 'stub', capabilities: ['test'], resources: ['cpu'],
      sideEffects: [], failureCodes: [], input: z.object({}).strict(),
      argv: (_args, context) => [context.python, '-c', 'x = bytearray(2 * 1024 ** 3)'],
      outputs: () => [],
    }
    const record = await runScientificJob(hog, {}, { workspace: root, python, resources: { max_memory_gb: 1 } })
    expect(record.state).toBe('FAILED')
    expect(record.exit_code).not.toBe(0)
  })

  it('reports an abandoned job as INTERRUPTED instead of leaving it RUNNING', () => {
    const root = workspace()
    const jobId = 'abcdef123456'
    const directory = join(root, '.jobs', jobId)
    mkdirSync(directory, { recursive: true })
    writeFileSync(join(directory, 'job.json'), JSON.stringify({ job_id: jobId, tool_id: 'rdkit.featurize', state: 'RUNNING',
      started_at: new Date().toISOString(), argv: [], artifacts: [], usage: {} }), 'utf8')
    const record = jobStatus(root, jobId)
    expect(record?.state).toBe('INTERRUPTED')
    expect(jobStatus(root, jobId)?.state).toBe('INTERRUPTED')
  })
})

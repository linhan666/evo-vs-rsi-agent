/**
 * Worker-facing scientific tools (Blueprint §8.1 "tool discovery" and §16.1).
 *
 * Three tools keep the worker's context small while covering the four operations
 * the blueprint names: discovery, run, and one `scientific_job` action tool for
 * status / read / cancel / list. The Agent never composes a shell command: it
 * names a tool id and validated arguments, and the registry builds the argv.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { z } from 'zod'
import { tool, type Tool } from '../app/tools/tool.ts'
import type { Ticket } from '../core/index.ts'
import { cancelJob, jobDirectoryOf, jobStatus, runScientificJob } from './job-runner.ts'
import { describeTools, findTool, withinWorkspace } from './registry.ts'

const JobId = z.string().regex(/^[0-9a-f]{12}$/, 'a job id from scientific_run_job')

function interpreter(): string {
  const value = process.env.EVOVS_PYTHON
  if (!value) throw new Error('EVOVS_PYTHON is not set; point it at scientific/.venv/bin/python before starting the runtime')
  return value
}

function workspaceOf(ticket: Ticket): string {
  const directory = ticket.execution?.directory
  if (!directory) throw new Error('this ticket has no execution directory yet')
  return directory
}

export function scientificTools(ticket: Ticket): Tool[] {
  return [
    tool({
      name: 'scientific_tools',
      description: 'List scientific tools: capabilities, resources, failure codes, schema.',
      schema: z.object({}).strict(),
      execute: async () => ({ tools: describeTools(), interpreter_configured: Boolean(process.env.EVOVS_PYTHON) }),
    }),
    tool({
      name: 'scientific_run_job',
      description: 'Run one scientific tool by id here; records outputs with sha256.',
      schema: z.object({
        tool_id: z.string().min(1).describe('From scientific_tools'),
        arguments: z.record(z.string(), z.unknown()).describe('Match its input_schema'),
        max_wall_seconds: z.number().int().min(1).max(3600).optional().describe('Seconds'),
      }).strict(),
      execute: async (args, signal) => {
        const definition = findTool(args.tool_id)
        const workspace = workspaceOf(ticket)
        const record = await runScientificJob(definition, args.arguments, {
          workspace,
          python: interpreter(),
          signal,
          ...(args.max_wall_seconds ? { resources: { max_wall_seconds: args.max_wall_seconds } } : {}),
        })
        const metrics = record.artifacts.find(item => item.path.endsWith('metrics.json'))
        return { ...record, ...(metrics ? { metrics: JSON.parse(readFileSync(join(workspace, metrics.path), 'utf8')) } : {}) }
      },
    }),
    tool({
      name: 'scientific_job',
      description: 'Job status, artifact text, cancel, or list jobs.',
      schema: z.object({
        operation: z.enum(['status', 'read', 'cancel', 'list']),
        job_id: JobId.optional(),
        path: z.string().min(1).optional().describe('read: its path'),
        limit: z.number().int().min(1).max(8000).default(4000),
      }).strict(),
      execute: async args => {
        const workspace = workspaceOf(ticket)
        if (args.operation === 'list') {
          const root = join(workspace, '.jobs')
          let ids: string[] = []
          try { ids = readdirSync(root).filter(name => /^[0-9a-f]{12}$/.test(name)).sort().slice(-20) } catch { ids = [] }
          return { jobs: ids.map(id => ({ job_id: id, state: jobStatus(workspace, id)?.state ?? 'UNKNOWN' })) }
        }
        if (!args.job_id) throw new Error(`${args.operation} needs job_id`)
        if (args.operation === 'cancel') {
          return { job_id: args.job_id, cancelled: cancelJob(args.job_id), directory: jobDirectoryOf(workspace, args.job_id) }
        }
        const record = jobStatus(workspace, args.job_id)
        if (!record) throw new Error(`no such job: ${args.job_id}`)
        if (args.operation === 'status') return record
        if (!args.path) throw new Error('read needs path')
        const target = withinWorkspace(workspace, args.path)
        const artifact = record.artifacts.find(item => item.path === args.path)
        if (!artifact) throw new Error(`the job did not produce ${args.path}; it produced ${record.artifacts.map(item => item.path).join(', ') || 'nothing'}`)
        const text = readFileSync(target, 'utf8')
        return { path: artifact.path, sha256: artifact.sha256, size: statSync(target).size,
          truncated: text.length > args.limit, text: text.slice(0, args.limit) }
      },
    }),
  ]
}

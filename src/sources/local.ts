/**
 * Local Source: one JSON task file per request, dropped into an inbox directory.
 *
 * Why it exists (Blueprint §7.2, §19.1): the MVP needs a real `Source → Engine → Executor → Report`
 * path that does not depend on a GitHub account. This kind maps a file onto the same domain objects
 * as the shipped Sources — a `Trigger`, a `Thread`, an `Actor` and a `Channel` — so nothing in the
 * Engine, the Store or the trace pipeline is special-cased for it.
 *
 * Trust boundary: the filesystem permission on `inboxDir` is what authorizes a request. A file is a
 * `direct` request from its `sender`, exactly as a direct message would be. The Source's Policy
 * `allowed` list still applies for identity bookkeeping and for `unlistedAddressed` decisions.
 */
import type { Context } from '@deepseek-ai/cordis'
import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, writeFileSync } from 'node:fs'
import { basename, join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { z } from 'zod'
import { key, type OutboundMessage, type Trigger } from '../core/index.ts'
import { health, sourceContext, type SourceContext } from './host.ts'
import type { SourceKind } from './kind.ts'

const ConfigSchema = z.object({
  /** Absolute path of the directory scanned for `*.json` task files. Empty receives nothing. */
  inboxDir: z.string().trim().default(''),
  /** Absolute path where replies are written, one `<message id>.json` per message. Empty drops replies. */
  outboxDir: z.string().trim().default(''),
  pollSeconds: z.number().int().min(5).max(3600).default(10),
  /** Move a task file into `<inboxDir>/.processed` once its Trigger is stored. */
  archive: z.boolean().default(true),
}).strict()
export type LocalConfig = z.infer<typeof ConfigSchema>

/** One task file. `task_id` is stable: the same id is the same Trigger, so replay is safe. */
const TaskSchema = z.object({
  task_id: z.string().min(1).regex(/^[A-Za-z0-9._-]+$/, 'Use letters, digits, dot, dash or underscore'),
  sender: z.string().min(1).default('operator'),
  at: z.string().optional(),
  title: z.string().optional(),
  text: z.string().min(1),
}).strict()
export type LocalTask = z.infer<typeof TaskSchema>

/** The Trigger of one task file, or `undefined` when the file cannot be a request. */
export function localTrigger(task: LocalTask, file: string, at: string, outboxDir: string): Trigger {
  return {
    id: key('local', task.task_id),
    source: 'local',
    threads: [{ source: 'local', id: task.task_id }],
    actor: { source: 'local', id: task.sender },
    human: true,
    addressed: 'direct',
    at: task.at ?? at,
    text: task.text,
    channel: { source: 'local', thread: `local:${task.task_id}`, address: { task: task.task_id, file, outbox: outboxDir } },
    url: `file://${file}`,
    meta: { taskId: task.task_id, file, sender: task.sender, ...(task.title ? { title: task.title } : {}) },
  }
}

/**
 * Write one reply under the task's outbox directory. The message id names the file, so a retried
 * send rewrites the same file instead of duplicating the reply (the idempotency rule of step 5).
 */
export async function sendLocal(_host: Pick<SourceContext, 'commands'>, message: OutboundMessage): Promise<'sent' | 'gone'> {
  const { outbox, task } = message.channel.address
  if (!outbox) return 'gone'
  const file = join(outbox, `${message.id}.json`)
  if (existsSync(file)) return 'sent'
  mkdirSync(outbox, { recursive: true })
  const payload = {
    id: message.id,
    kind: message.kind,
    task_id: task ?? '',
    ...(message.ticketId ? { ticket_id: message.ticketId } : {}),
    text: message.text,
    at: new Date().toISOString(),
  }
  writeFileSync(file, `${JSON.stringify(payload, null, 2)}\n`, 'utf8')
  return 'sent'
}

export const localKind: SourceKind<LocalConfig> = {
  kind: 'local',
  title: { zh: '本地任务文件', en: 'Local task files' },
  description: {
    zh: '读取收件目录中的 JSON 任务文件，把每个文件变成一次请求；回复写入发件目录。',
    en: 'Reads JSON task files from an inbox directory, one request per file; replies go to an outbox directory.',
  },
  schema: ConfigSchema,
  fields: [
    { key: 'inboxDir', type: 'text', label: { zh: '收件目录（绝对路径）', en: 'Inbox directory (absolute)' } },
    { key: 'outboxDir', type: 'text', label: { zh: '回信目录（绝对路径）', en: 'Outbox directory (absolute)' } },
    { key: 'archive', type: 'switch', advanced: true, label: { zh: '处理后归档任务文件', en: 'Archive task files once handled' } },
    { key: 'pollSeconds', type: 'number', advanced: true, min: 5, max: 3600,
      label: { zh: '轮询间隔 / 秒', en: 'Polling interval / seconds' } },
  ],
  health: ['local'],

  // Step 4: what this Source receives. Files are always addressed to the agent, so it never observes
  // unaddressed traffic; `row` names the single admission row below.
  scope: (_input, config) => config.inboxDir
    ? { listened: true, observed: false, row: 'inbox' }
    : { listened: false, reason: 'inbox_not_set' },

  // Step 5: replies.
  channel: {
    allowed: address => typeof address.outbox === 'string' && address.outbox.length > 0,
    send: sendLocal,
    link: address => ({ url: address.file ?? '', label: { zh: '本地任务文件', en: 'Local task file' } }),
  },

  // Step 6: a task file is a thread of one message.
  threadContext: {
    messageId: trigger => String(trigger.meta.taskId ?? ''),
    read: async (_commands, trigger, part) => {
      if (part === 'parent') return { messages: [], body: { messages: [] } }
      const message = { id: String(trigger.meta.taskId ?? ''), from: trigger.actor.id, at: trigger.at, text: trigger.text }
      return { messages: [message], body: { messages: [message], file: String(trigger.meta.file ?? '') } }
    },
  },

  find: query => ({ threads: [], terms: [...new Set(query.match(/\b[A-Za-z0-9._-]{3,}\b/g) ?? [])] }),

  // Step 7: the Source's part of the Policy.
  policy: {
    schema: z.object({
      allowed: z.array(z.object({ id: z.string().min(1), name: z.string().trim().max(100).optional() }).strict()).default([]),
    }).strict(),
    fields: [{
      key: 'allowed', type: 'rows', label: { zh: '能发起工作的发送者', en: 'Senders who may originate work' },
      columns: [
        { key: 'id', label: { zh: '发送者', en: 'Sender' }, type: 'text' },
        { key: 'name', label: { zh: '名字', en: 'Name' }, type: 'text', optional: true },
      ],
    }],
    explicit: { zh: '放在收件目录里的任务文件被视为直接请求。', en: 'A task file in the inbox counts as a direct request.' },
    rows: config => ConfigSchema.parse(config).inboxDir
      ? [{
        id: 'inbox',
        label: { zh: '收件目录', en: 'Inbox' },
        note: { zh: '文件写入权限即授权', en: 'Filesystem write access is the grant' },
        cells: { listedUnaddressed: false, unlistedAddressed: true, unlistedUnaddressed: false },
      }]
      : [],
  },

  // Step 8: variables for the Executor.
  environment: {
    variables: [
      { key: 'DSH_SUPERAGENT_LOCAL_TASK_ID', description: {
        zh: '接下工单的本地任务 id；工单不是从本地 Source 来的时为空',
        en: 'The local task id that started the ticket; empty when the ticket did not start here' } },
      { key: 'DSH_SUPERAGENT_LOCAL_SENDER', description: {
        zh: '提交该本地任务的发送者；工单不是从本地 Source 来的时为空',
        en: 'The sender of that local task; empty when the ticket did not start here' } },
    ],
    values: ({ trigger }) => ({
      DSH_SUPERAGENT_LOCAL_TASK_ID: trigger?.source === 'local' ? String(trigger.meta.taskId ?? '') : '',
      DSH_SUPERAGENT_LOCAL_SENDER: trigger?.source === 'local' ? String(trigger.meta.sender ?? '') : '',
    }),
  },
}

/**
 * Scan the inbox once: store each valid task's Trigger, then archive the file.
 * A malformed file is counted and left in place, so a person can fix it (per-item errors, step 9).
 */
export async function scanInbox(ctx: SourceContext, config: LocalConfig, signal?: AbortSignal): Promise<{ read: number; unreadable: number }> {
  if (!config.inboxDir) return { read: 0, unreadable: 0 }
  let names: string[]
  try {
    names = readdirSync(config.inboxDir).filter(name => name.endsWith('.json')).sort()
  } catch (error) {
    throw new Error(`cannot read the local inbox ${config.inboxDir}: ${String(error)}`)
  }
  let read = 0
  let unreadable = 0
  for (const name of names) {
    if (signal?.aborted) break
    const file = join(config.inboxDir, name)
    let task: LocalTask
    try {
      const parsed = TaskSchema.safeParse(JSON.parse(readFileSync(file, 'utf8')))
      if (!parsed.success) { unreadable += 1; continue }
      task = parsed.data
    } catch { unreadable += 1; continue }
    await ctx.receive(localTrigger(task, file, new Date().toISOString(), config.outboxDir))
    if (config.archive) {
      const done = join(config.inboxDir, '.processed')
      mkdirSync(done, { recursive: true })
      renameSync(file, join(done, basename(file)))
    }
    read += 1
  }
  return { read, unreadable }
}

/** Step 9: the polling loop, waiting for setup, following the Source switch and reporting health. */
export async function watch(ctx: SourceContext, signal: AbortSignal): Promise<void> {
  await ctx.ready
  if (!ctx.configured()) { ctx.report('local', health('paused', 'setupPending')); return }
  let failures = 0
  while (!signal.aborted) {
    const config = ctx.config<LocalConfig>('local')
    if (!config) ctx.report('local', health('paused', 'sourceOff'))
    else {
      const at = new Date().toISOString()
      try {
        const { read, unreadable } = await scanInbox(ctx, config, signal)
        failures = 0
        ctx.report('local', { state: 'ready', detail: `${read} tasks, ${unreadable} unreadable`, at })
      } catch (error) {
        failures += 1
        if (!signal.aborted && failures >= 3) {
          ctx.report('local', health('error', 'pollFailures', { count: String(failures), error: String(error) }))
        }
      }
    }
    await delay((config?.pollSeconds ?? 10) * 1000, undefined, { signal }).catch(() => {})
  }
}

export const name = 'dsh-superagent-local'
export const inject = ['orchestrator']
export function apply(ctx: Context): void {
  ctx.effect(() => ctx.orchestrator.sources.register(localKind), 'local: source kind')
  ctx.effect(() => {
    const source = sourceContext(ctx.orchestrator, localKind)
    const controller = new AbortController()
    // DSH ends its process on an unhandled rejection, so a failure that escapes the loop becomes health.
    const running = watch(source, controller.signal)
      .catch((error: unknown) => { source.report('local', { state: 'error', detail: String(error) }) })
    return async () => { controller.abort(); await running }
  })
}

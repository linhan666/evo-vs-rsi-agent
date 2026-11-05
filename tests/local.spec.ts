import { afterEach, describe, expect, it, vi } from 'vitest'
import { Engine, key, type Assessor, type Executor, type OutboundMessage, type Trigger } from '../src/core/index.ts'
import { localKind, localTrigger, scanInbox, sendLocal, watch, type LocalConfig } from '../src/sources/local.ts'
import { SourceRegistry } from '../src/sources/registry.ts'
import { Store } from '../src/app/store.ts'
import { Commands } from '../src/infra/commands.ts'
import { HealthBoard } from '../src/infra/health.ts'
import { testDeployment } from './fixtures/deployment.ts'
import { SettingsSchema, settingsPolicy } from '../src/policy.ts'
import { sourceContextOf, type SourceContextDeps } from '../src/app/source-context.ts'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const roots: string[] = []
afterEach(() => { for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true }) })

function sandbox() {
  const root = mkdtempSync(join(tmpdir(), 'local-source-'))
  roots.push(root)
  const inbox = join(root, 'inbox')
  mkdirSync(inbox, { recursive: true })
  return { root, inbox, outbox: join(root, 'outbox') }
}

function host(options: { enabled?: boolean; configured?: boolean; pollSeconds?: number } = {}) {
  const { root, inbox, outbox } = sandbox()
  const store = new Store(join(root, 'db.sqlite'))
  store.saveSettings(SettingsSchema.parse({
    sources: { local: { enabled: options.enabled ?? true, config: { inboxDir: inbox, outboxDir: outbox, pollSeconds: options.pollSeconds ?? 5 } } },
    policy: { sources: { local: { allowed: [{ id: 'operator' }] } } },
    eval: { mode: 'auto' },
  }))
  const board = new HealthBoard()
  const sources = new SourceRegistry(() => store.settings(), board)
  sources.register(localKind)
  const deployment = testDeployment()
  const assessor: Assessor = { request: vi.fn(async () => {}) }
  const executor: Executor = { start: vi.fn(async () => {}), deliver: vi.fn(async () => {}), stop: vi.fn(async () => {}) }
  const outboxPort = { send: (message: OutboundMessage) => { store.receipts.add(message) }, status: () => undefined, withdraw: () => {} }
  const engine = new Engine({ repo: store, scope: sources, policy: () => settingsPolicy(store.settings(), sources), assessor, executor, outbox: outboxPort })
  const commands = new Commands(() => deployment, {}, new AbortController().signal)
  const receive = vi.fn(async (trigger: Trigger) => { const result = engine.receive(trigger); engine.evaluateDue(); return result })
  const parts: SourceContextDeps = { store, engine, outbox: outboxPort, commands, sources, deployment,
    ready: Promise.resolve(), configured: () => options.configured ?? true, receive }
  return { ctx: sourceContextOf(parts, localKind), store, engine, receive, health: board.all, inbox, outbox, root }
}

const task = (inbox: string, name: string, value: unknown) => writeFileSync(join(inbox, name), JSON.stringify(value), 'utf8')
const config = (h: ReturnType<typeof host>) => h.ctx.config<LocalConfig>('local')!

describe('local source', () => {
  it('maps a task file onto stable Trigger, Thread, Actor and Channel ids', () => {
    const trigger = localTrigger({ task_id: 'mor_bind_001', sender: 'operator', text: 'Build the MOR model' },
      '/tmp/inbox/a.json', '2026-11-05T00:00:00Z', '/tmp/outbox')
    expect(trigger.id).toBe(key('local', 'mor_bind_001'))
    expect(trigger.source).toBe('local')
    expect(trigger.threads[0]).toEqual({ source: 'local', id: 'mor_bind_001' })
    expect(trigger.actor).toEqual({ source: 'local', id: 'operator' })
    expect(trigger.human).toBe(true)
    expect(trigger.addressed).toBe('direct')
    expect(trigger.channel?.address).toEqual({ task: 'mor_bind_001', file: '/tmp/inbox/a.json', outbox: '/tmp/outbox' })
  })

  it('stores one Trigger per file, archives the file, and does not re-store it', async () => {
    const h = host()
    task(h.inbox, 'a.json', { task_id: 'mor_bind_001', sender: 'operator', text: 'Build the MOR model' })
    expect(await scanInbox(h.ctx, config(h))).toEqual({ read: 1, unreadable: 0 })
    expect(await h.receive.mock.results[0]!.value).toBe('stored')
    expect(h.engine.candidate(key('local', 'mor_bind_001'))?.strength).toBe('explicit')
    expect(existsSync(join(h.inbox, 'a.json'))).toBe(false)
    expect(existsSync(join(h.inbox, '.processed', 'a.json'))).toBe(true)
    expect(await scanInbox(h.ctx, config(h))).toEqual({ read: 0, unreadable: 0 })
    h.store.close()
  })

  it('counts malformed files and leaves them for a person to fix', async () => {
    const h = host()
    writeFileSync(join(h.inbox, 'broken.json'), 'not json', 'utf8')
    task(h.inbox, 'incomplete.json', { task_id: 'no_text' })
    expect(await scanInbox(h.ctx, config(h))).toEqual({ read: 0, unreadable: 2 })
    expect(existsSync(join(h.inbox, 'broken.json'))).toBe(true)
    expect(h.receive).not.toHaveBeenCalled()
    h.store.close()
  })

  it('listens only with an inbox configured, and never observes unaddressed traffic', () => {
    expect(localKind.scope!({ meta: {} }, localKind.schema.parse({}) as LocalConfig))
      .toEqual({ listened: false, reason: 'inbox_not_set' })
    expect(localKind.scope!({ meta: {} }, localKind.schema.parse({ inboxDir: '/tmp/in' }) as LocalConfig))
      .toEqual({ listened: true, observed: false, row: 'inbox' })
    expect(localKind.policy!.rows!(localKind.schema.parse({}) as Record<string, unknown>)).toEqual([])
  })

  it('sends each reply once, keyed by message id, and answers gone without an outbox', async () => {
    const h = host()
    const message: OutboundMessage = { id: 'msg_1', kind: 'reply', text: 'done',
      channel: { source: 'local', thread: 'local:mor_bind_001', address: { task: 'mor_bind_001', outbox: h.outbox } } }
    const sender = { commands: h.ctx.commands }
    expect(await sendLocal(sender, message)).toBe('sent')
    expect(await sendLocal(sender, message)).toBe('sent')
    expect(readdirSync(h.outbox)).toEqual(['msg_1.json'])
    expect(JSON.parse(readFileSync(join(h.outbox, 'msg_1.json'), 'utf8'))).toMatchObject({ id: 'msg_1', task_id: 'mor_bind_001', text: 'done' })
    const gone: OutboundMessage = { ...message, channel: { ...message.channel, address: { task: 'mor_bind_001' } } }
    expect(await sendLocal(sender, gone)).toBe('gone')
    h.store.close()
  })

  it('reports setupPending instead of reading while setup waits', async () => {
    const h = host({ configured: false })
    task(h.inbox, 'a.json', { task_id: 't1', text: 'x' })
    await watch(h.ctx, new AbortController().signal)
    expect(h.health.local).toMatchObject({ state: 'paused', code: 'setupPending' })
    expect(h.receive).not.toHaveBeenCalled()
    h.store.close()
  })

  it('reports sourceOff while the Source is switched off', async () => {
    const h = host({ enabled: false })
    const controller = new AbortController()
    const running = watch(h.ctx, controller.signal)
    await vi.waitFor(() => expect(h.health.local?.code).toBe('sourceOff'))
    controller.abort()
    await running
    h.store.close()
  })
})

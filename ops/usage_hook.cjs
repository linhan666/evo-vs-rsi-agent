/**
 * Cost instrumentation: sniff `usage` out of every model response and append it
 * to a JSONL ledger.
 *
 * The upstream `@deepseek-ai/dsh-llm` client is not ours to patch and its provider
 * route gives us no hook, so this module rides along with the process via
 * `NODE_OPTIONS=--require` and watches every way a Node client can send the
 * request: `globalThis.fetch` (undici), `http`/`https`, `http2`, and `undici`
 * itself. Nothing else about the call is touched — same request, same response,
 * only the `usage` block is copied out.
 *
 * Ledger lines:
 *   {event: 'hook-installed', pid}                     once per process
 *   {event: 'call', via, url}                          every intercepted request
 *   {ts, model, prompt_tokens, completion_tokens, ...} every response that had usage
 */
'use strict'

const fs = require('fs')
const path = require('path')

const OUT = process.env.EVOVS_USAGE_LOG
  || path.join(process.cwd(), 'scientific', '.artifacts', 'usage.jsonl')
const DEBUG = process.env.EVOVS_USAGE_DEBUG === '1'

function record (entry) {
  try {
    fs.mkdirSync(path.dirname(OUT), { recursive: true })
    fs.appendFileSync(OUT, JSON.stringify(entry) + '\n')
  } catch { /* never let accounting break the call */ }
}

function sniff (text, via) {
  if (DEBUG) record({ event: 'sniff', via, length: text ? text.length : -1,
                      hasToken: typeof text === 'string' && text.indexOf('token') !== -1,
                      head: String(text).slice(0, 120), ts: new Date().toISOString() })
  if (typeof text !== 'string' || text.length === 0) return
  if (text.indexOf('token') === -1) return
  const payloads = []
  // SSE (streaming) first: the body is `event:`/`data:` lines, not one JSON document,
  // and Anthropic splits usage across message_start (input) and message_delta (output),
  // so the parts have to be merged before they mean anything.
  if (text.indexOf('data:') !== -1) {
    for (const line of text.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      try { payloads.push(JSON.parse(trimmed.slice(5).trim())) } catch { /* not JSON */ }
    }
  } else {
    try { payloads.push(JSON.parse(text)) } catch { return }
  }
  const merged = { model: null, prompt_tokens: 0, completion_tokens: 0, cached_tokens: 0 }
  let seen = false
  for (const data of payloads) {
    // Anthropic nests the first usage inside `message` (message_start) and sends the
    // rest at top level (message_delta); OpenAI puts it at top level.
    const usage = (data && data.usage) || (data && data.message && data.message.usage)
    if (!usage) continue
    const prompt = usage.prompt_tokens !== undefined ? usage.prompt_tokens : usage.input_tokens
    const completion = usage.completion_tokens !== undefined ? usage.completion_tokens : usage.output_tokens
    if (prompt === undefined && completion === undefined) continue
    seen = true
    const model = data.model || (data.message && data.message.model)
    if (model) merged.model = model
    // Anthropic reports input_tokens as the *uncached* part and cache_read_input_tokens
    // separately; OpenAI's prompt_tokens already includes the cache. Store the total in
    // prompt_tokens so pricing can treat cached as a subset, not an addition.
    const cached = (usage.prompt_tokens_details && usage.prompt_tokens_details.cached_tokens)
      || usage.cache_read_input_tokens || 0
    if (prompt !== undefined) merged.prompt_tokens = prompt + cached
    if (completion !== undefined) merged.completion_tokens = completion
    merged.cached_tokens = cached || merged.cached_tokens
  }
  if (!seen) return
  record({ ts: new Date().toISOString(), ...merged,
           total_tokens: merged.prompt_tokens + merged.completion_tokens, via })
}

function noteCall (via, target) {
  if (!DEBUG) return
  record({ event: 'call', via, url: String(target).slice(0, 160), ts: new Date().toISOString() })
}

// --- global fetch (undici-backed in Node 18+) ---------------------------------
if (typeof globalThis.fetch === 'function') {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async function instrumentedFetch (input, init) {
    noteCall('fetch', (init && init.url) || (input && input.url) || input)
    const response = await originalFetch.apply(this, arguments)
    try {
      // `clone().text()` never settles on a streaming response while the caller is
      // reading the original body, so tee the stream instead: one branch goes to the
      // caller unchanged, the other is drained here for accounting.
      if (response.body && typeof response.body.tee === 'function') {
        const [mine, theirs] = response.body.tee()
        if (DEBUG) record({ event: 'tee', ts: new Date().toISOString() })
        ;(async () => {
          const chunks = []
          try {
            const reader = mine.getReader()
            for (;;) {
              const { done, value } = await reader.read()
              if (done) break
              chunks.push(Buffer.from(value))
            }
            if (DEBUG) record({ event: 'tee-drained', bytes: chunks.reduce((n, c) => n + c.length, 0) })
          } catch (error) {
            // The client cancels the stream once it has the final message_delta, so
            // an AbortError here is normal: the usage is in what was already read.
            if (DEBUG) record({ event: 'tee-error', message: String(error).slice(0, 120),
                                bytes: chunks.reduce((n, c) => n + c.length, 0) })
          }
          if (chunks.length) sniff(Buffer.concat(chunks).toString('utf8'), 'fetch')
        })()
        return new Response(theirs, {
          status: response.status, statusText: response.statusText, headers: response.headers,
        })
      }
      const clone = response.clone()
      clone.text().then(text => sniff(text, 'fetch')).catch(() => {})
    } catch { /* response bodies are best-effort */ }
    return response
  }
}

// --- http / https -------------------------------------------------------------
for (const name of ['http', 'https']) {
  const module = require(name)
  const originalRequest = module.request
  module.request = function instrumentedRequest (...args) {
    const request = originalRequest.apply(this, args)
    noteCall(name, (args[0] && (args[0].href || args[0].host)) || args[0])
    request.on('response', response => {
      const chunks = []
      response.on('data', chunk => chunks.push(chunk))
      response.on('end', () => sniff(Buffer.concat(chunks).toString('utf8'), name))
    })
    return request
  }
  const originalGet = module.get
  if (originalGet) {
    module.get = function instrumentedGet (...args) {
      const request = module.request(...args)
      request.end()
      return request
    }
  }
}

// --- http2 --------------------------------------------------------------------
try {
  const http2 = require('http2')
  const originalConnect = http2.connect
  http2.connect = function instrumentedConnect (...args) {
    const session = originalConnect.apply(this, args)
    const originalRequest = session.request.bind(session)
    session.request = function instrumentedStream (headers, options) {
      noteCall('http2', headers && (headers[':path'] || headers.host))
      const stream = originalRequest(headers, options)
      const chunks = []
      stream.on('data', chunk => chunks.push(chunk))
      stream.on('end', () => sniff(Buffer.concat(chunks).toString('utf8'), 'http2'))
      return stream
    }
    return session
  }
} catch { /* http2 unavailable */ }

// --- undici (if the client imports it directly rather than using global fetch) --
try {
  const undici = require('undici')
  if (typeof undici.request === 'function') {
    const originalRequest = undici.request
    undici.request = async function instrumentedUndiciRequest (url, options) {
      noteCall('undici', url)
      const result = await originalRequest.apply(this, arguments)
      try {
        const chunks = []
        for await (const chunk of result.body) chunks.push(chunk)
        const text = Buffer.concat(chunks).toString('utf8')
        sniff(text, 'undici')
        const stream = require('stream').Readable.from(Buffer.concat(chunks))
        return { ...result, body: stream }
      } catch { return result }
    }
  }
} catch { /* undici not loadable as CJS */ }

record({ ts: new Date().toISOString(), event: 'hook-installed', pid: process.pid, debug: DEBUG })

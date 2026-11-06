/**
 * Cost instrumentation: sniff `usage` out of every model response and append it
 * to a JSONL ledger.
 *
 * The upstream `@deepseek-ai/dsh-llm` client is not ours to patch and its provider
 * route gives us no hook, so this module rides along with the process via
 * `NODE_OPTIONS=--require` and watches the two ways a Node client can send the
 * request: `globalThis.fetch` (undici) and `http(s).request`. Nothing else about
 * the call is touched — same request, same response, only the `usage` block is
 * copied out.
 *
 * Ledger line: {ts, model, prompt_tokens, completion_tokens, total_tokens, cached_tokens, via}
 */
'use strict'

const fs = require('fs')
const path = require('path')

const OUT = process.env.EVOVS_USAGE_LOG
  || path.join(process.cwd(), 'scientific', '.artifacts', 'usage.jsonl')

function record (entry) {
  try {
    fs.mkdirSync(path.dirname(OUT), { recursive: true })
    fs.appendFileSync(OUT, JSON.stringify(entry) + '\n')
  } catch { /* never let accounting break the call */ }
}

function sniff (text, via) {
  if (typeof text !== 'string' || text.length === 0 || text.indexOf('"usage"') === -1) return
  let data
  try { data = JSON.parse(text) } catch { return }
  const usage = data && data.usage
  if (!usage || usage.prompt_tokens === undefined) return
  record({
    ts: new Date().toISOString(),
    model: data.model || null,
    prompt_tokens: usage.prompt_tokens,
    completion_tokens: usage.completion_tokens,
    total_tokens: usage.total_tokens,
    cached_tokens: (usage.prompt_tokens_details && usage.prompt_tokens_details.cached_tokens) || 0,
    via,
  })
}

if (typeof globalThis.fetch === 'function') {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async function instrumentedFetch (...args) {
    const response = await originalFetch.apply(this, args)
    try {
      const clone = response.clone()
      clone.text().then(text => sniff(text, 'fetch')).catch(() => {})
    } catch { /* response bodies are best-effort */ }
    return response
  }
}

for (const name of ['http', 'https']) {
  const module = require(name)
  const originalRequest = module.request
  module.request = function instrumentedRequest (...args) {
    const request = originalRequest.apply(this, args)
    request.on('response', response => {
      const chunks = []
      response.on('data', chunk => chunks.push(chunk))
      response.on('end', () => sniff(Buffer.concat(chunks).toString('utf8'), name))
    })
    return request
  }
}

record({ ts: new Date().toISOString(), event: 'hook-installed', pid: process.pid })

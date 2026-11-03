import assert from 'node:assert/strict'
import { test } from 'node:test'
import Module from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
async function bundled(relativePath, apiBase = 'http://localhost:8000/api/v1') {
  const result = await build({ entryPoints: [path.join(root, relativePath)], bundle: true, platform: 'node', format: 'cjs', packages: 'external', write: false, jsx: 'automatic', define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify(apiBase) } })
  const module = new Module(path.join(root, 'tests', 'phase11-compiled.cjs'))
  module.filename = path.join(root, 'tests', 'phase11-compiled.cjs')
  module.paths = Module._nodeModulePaths(path.join(root, 'tests'))
  module._compile(result.outputFiles[0].text, module.filename)
  return module.exports
}

const storage = new Map()
globalThis.localStorage = { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) }
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { onLine: false } })

function analysis(id) {
  return {
    analysis_id: id, image_url: '/private-image', extraction: { claim: 'সব বিশ্ববিদ্যালয় বন্ধ' },
    retrieval: { retrieved_at: '2026-11-02T10:00:00Z' }, limitations: ['Only titles were checked'],
    verification: { label: 'unverified', evidence_coverage: 'low', summary: 'Unknown', reasons: [], comparison_method: 'none', fallbacks_used: [], limitations: [], flags: [], layers: { claim: { status: 'unverified', summary: 'Unknown' }, source: { status: 'inconclusive', summary: 'Unknown' }, context: { status: 'inconclusive', summary: 'Unknown' }, media: { status: 'inconclusive', summary: 'Unknown' } } },
    evidence: [{ evidence_id: 'ev_1', title: 'একটি সূত্র', url: 'https://example.org/a', domain: 'example.org', source_type: 'other', stance: 'mentions_but_unclear', published_at: null, retrieved_at: '2026-11-02T10:00:00Z', snippet: 'private provider response', quote: 'private quote' }],
  }
}

test('bounded cache keeps derived report metadata and removes deleted reports', async () => {
  const cache = await bundled('src/pwa/reportCache.ts')
  for (let i = 0; i < 12; i++) cache.saveCachedReport(analysis(`an_${i}`))
  const reports = cache.listCachedReports()
  assert.equal(reports.length, 10)
  assert.equal(reports[0].analysis_id, 'an_11')
  assert.equal(reports[0].retrieved_at, '2026-11-02T10:00:00Z')
  assert.doesNotMatch(JSON.stringify(reports), /private-image|private provider response|private quote/)
  cache.removeCachedReport('an_11')
  assert.equal(cache.getCachedReport('an_11'), null)
})

test('graph and cached text list show the same evidence IDs', async () => {
  const Graph = (await bundled('src/components/EvidenceGraph.tsx')).default
  const Cached = (await bundled('src/components/CachedReportView.tsx')).default
  const cache = await bundled('src/pwa/reportCache.ts')
  cache.saveCachedReport(analysis('an_graph'))
  const report = cache.getCachedReport('an_graph')
  const graph = renderToStaticMarkup(React.createElement(Graph, { claim: report.claim, evidence: report.evidence }))
  const page = renderToStaticMarkup(React.createElement(Cached, { report, onRetry: () => {}, retrying: false }))
  assert.match(graph, /ev_1/)
  assert.match(page, /অফলাইনে সংরক্ষিত কপি/)
  assert.equal((page.match(/ev_1/g) || []).length, 2)
  assert.match(page, /সংরক্ষণ:/)
  assert.match(page, /সূত্র পাওয়া:/)
})

test('offline state stops verification before a network request', async () => {
  let calls = 0
  globalThis.fetch = () => { calls++; throw Error('network call') }
  const api = await bundled('src/api/truthlayer.ts')
  assert.throws(() => api.verifyAnalysis('an_test'), /ইন্টারনেট সংযোগ নেই/)
  assert.equal(calls, 0)
})

test('offline state stops uploads and new searches before a network request', async () => {
  let calls = 0
  globalThis.fetch = () => { calls++; throw Error('network call') }
  const api = await bundled('src/api/truthlayer.ts')
  await assert.rejects(api.uploadAnalysis(new Blob(['image'], { type: 'image/png' }), ''), /ইন্টারনেট সংযোগ নেই/)
  await assert.rejects(api.retrieveEvidence('an_test'), /ইন্টারনেট সংযোগ নেই/)
  assert.equal(calls, 0)
})

test('one-origin deployment resolves uploaded images from a relative API base', async () => {
  globalThis.window = { location: { origin: 'https://demo.example' } }
  const api = await bundled('src/api/truthlayer.ts', '/api/v1')
  assert.equal(api.imageUrl('/api/v1/analyses/an_test/image'), 'https://demo.example/api/v1/analyses/an_test/image')
})

test('service worker preloads the hashed app assets on install', async () => {
  const listeners = new Map()
  const added = []
  const context = {
    URL,
    self: { location: { origin: 'https://truthlayer.example' }, clients: { claim: async () => {} }, addEventListener: (name, handler) => listeners.set(name, handler) },
    caches: { open: async () => ({ put: async () => {}, addAll: async paths => added.push(...paths) }) },
    fetch: async () => ({ ok: true, clone() { return this }, text: async () => '<script src="/assets/index-abc.js"></script><link href="/assets/index-def.css">' }),
  }
  vm.runInNewContext(readFileSync(path.join(root, 'dist/sw.js'), 'utf8'), context)
  let installing
  listeners.get('install')({ waitUntil: promise => { installing = promise } })
  await installing
  assert.ok(added.includes('/assets/index-abc.js'))
  assert.ok(added.includes('/assets/index-def.css'))
  assert.ok(added.includes('/offline.html'))
})

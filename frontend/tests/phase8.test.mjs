import assert from 'node:assert/strict'
import { test } from 'node:test'
import Module from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

async function component(relativePath) {
  const result = await build({ entryPoints: [path.join(root, relativePath)], bundle: true, platform: 'node', format: 'cjs', packages: 'external', write: false, jsx: 'automatic' })
  const module = new Module(path.join(root, 'tests', 'phase8-compiled.cjs'))
  module.filename = path.join(root, 'tests', 'phase8-compiled.cjs')
  module.paths = Module._nodeModulePaths(path.join(root, 'tests'))
  module._compile(result.outputFiles[0].text, module.filename)
  return module.exports.default
}

const layers = {
  claim: { status: 'insufficient_evidence', summary: 'Available evidence is insufficient to assess the claim.' },
  source: { status: 'inconclusive', summary: 'Source identity was not independently authenticated.' },
  context: { status: 'inconclusive', summary: 'Image or event provenance was not independently established.' },
  media: { status: 'inconclusive', summary: 'Media authenticity was not tested.' },
}

test('insufficient report shows all four layers and no invented citation', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const html = renderToStaticMarkup(React.createElement(Summary, { report: { label: 'insufficient_evidence', flags: [], evidence_coverage: 'low', summary: 'Available evidence is insufficient to assess the claim.', reasons: [], comparison_method: 'none', fallbacks_used: [], limitations: [], layers } }))
  assert.match(html, /প্রমাণ অপর্যাপ্ত/)
  assert.match(html, /উৎস পরিচয়/)
  assert.match(html, /প্রসঙ্গ/)
  assert.match(html, /ছবির সত্যতা/)
  assert.match(html, /এখনো নিশ্চিত নয়/)
  assert.doesNotMatch(html, /সিদ্ধান্তের ভিত্তি/)
})

test('completed report exposes cited reason and source URL', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const report = { label: 'verified', flags: [], evidence_coverage: 'medium', summary: 'A direct official source supports the claim.', reasons: [{ evidence_id: 'ev_1', url: 'https://ugc.gov.bd/notice', stance: 'supports', summary: 'Official notice.' }], comparison_method: 'gemini', fallbacks_used: [], limitations: [], layers: { ...layers, claim: { status: 'verified', summary: 'A direct official source supports the claim.' } } }
  const html = renderToStaticMarkup(React.createElement(Summary, { report }))
  assert.match(html, /সরকারি সূত্রে সমর্থিত/)
  assert.match(html, /href="https:\/\/ugc.gov.bd\/notice"/)
  assert.match(html, /ev_1/)
})

test('partial state explains provider limitation in Bangla', async () => {
  const Banner = await component('src/components/LimitationsBanner.tsx')
  const html = renderToStaticMarkup(React.createElement(Banner, { limitations: ['Live web retrieval is unavailable because Tavily is not configured.'], fallbacks: [] }))
  assert.match(html, /Tavily কনফিগার করা নেই/)
  assert.match(html, /সীমাবদ্ধতা/)
})

test('evidence card renders safe external citation and timestamps', async () => {
  const Card = await component('src/components/EvidenceCard.tsx')
  const html = renderToStaticMarkup(React.createElement(Card, { item: { evidence_id: 'ev_1', url: 'https://ugc.gov.bd/notice', title: 'বিজ্ঞপ্তি', domain: 'ugc.gov.bd', source_type: 'official_authority', snippet: 'সরকারি সংবাদ', published_at: null, retrieved_at: '2026-11-02T00:00:00Z', query: 'দাবি', stance: 'supports', relevance: 1, reason: 'সমর্থন করে', quote: 'সরকারি সংবাদ' } }))
  assert.match(html, /rel="noopener noreferrer"/)
  assert.match(html, /প্রকাশ: তারিখ অজানা/)
  assert.match(html, /প্রমাণ ID: ev_1/)
})

test('history exposes reopen and delete controls', async () => {
  const List = await component('src/components/HistoryList.tsx')
  const props = { items: [{ analysis_id: 'an_123', created_at: '2026-11-02T00:00:00Z', status: 'partial', extraction: { claim: 'পরীক্ষার দাবি' }, ocr: null, verification: null }], deleting: null, confirming: null, onDelete: () => {}, onConfirm: () => {}, onCancel: () => {} }
  const html = renderToStaticMarkup(React.createElement(List, props))
  assert.match(html, /href="#\/analysis\/an_123"/)
  assert.match(html, /রিপোর্ট খুলুন/)
  assert.match(html, /মুছুন/)
  assert.match(html, /আংশিক/)
  const confirming = renderToStaticMarkup(React.createElement(List, { ...props, confirming: 'an_123' }))
  assert.match(confirming, /হ্যাঁ, মুছুন/)
  assert.match(confirming, /বাতিল/)
})

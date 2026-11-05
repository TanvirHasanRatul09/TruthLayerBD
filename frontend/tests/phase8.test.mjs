import assert from 'node:assert/strict'
import { test } from 'node:test'
import Module from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

async function component(relativePath, exportName = 'default') {
  const result = await build({ entryPoints: [path.join(root, relativePath)], bundle: true, platform: 'node', format: 'cjs', packages: 'external', write: false, jsx: 'automatic' })
  const module = new Module(path.join(root, 'tests', 'phase8-compiled.cjs'))
  module.filename = path.join(root, 'tests', 'phase8-compiled.cjs')
  module.paths = Module._nodeModulePaths(path.join(root, 'tests'))
  module._compile(result.outputFiles[0].text, module.filename)
  return module.exports[exportName]
}

const layers = {
  claim: { status: 'insufficient_evidence', summary: 'Available evidence is insufficient to assess the claim.' },
  source: { status: 'inconclusive', summary: 'Source identity was not independently authenticated.' },
  context: { status: 'inconclusive', summary: 'Image or event provenance was not independently established.' },
  media: { status: 'inconclusive', summary: 'Media authenticity was not tested.' },
}

test('insufficient quick report is clear and has no invented citation', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const html = renderToStaticMarkup(React.createElement(Summary, { report: { label: 'insufficient_evidence', flags: [], evidence_coverage: 'low', summary: 'Available evidence is insufficient to assess the claim.', reasons: [], comparison_method: 'none', fallbacks_used: [], limitations: [], layers } }))
  assert.match(html, /যাচাই করা যায়নি/)
  assert.match(html, /এক নজরে ফলাফল/)
  assert.match(html, /এই নির্দিষ্ট দাবি নিশ্চিত বা খণ্ডন করার জন্য যথেষ্ট নয়/)
  assert.doesNotMatch(html, /ছবির সত্যতা|প্রকাশকের পরিচয়/)
  assert.doesNotMatch(html, /href=/)
})

test('completed report exposes cited reason and source URL', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const report = { label: 'verified', flags: [], evidence_coverage: 'medium', summary: 'A direct official source supports the claim.', reasons: [{ evidence_id: 'ev_1', url: 'https://ugc.gov.bd/notice', stance: 'supports', summary: 'Official notice.' }], comparison_method: 'gemini', fallbacks_used: [], limitations: [], layers: { ...layers, claim: { status: 'verified', summary: 'A direct official source supports the claim.' } } }
  const evidence = [{ evidence_id: 'ev_1', url: 'https://ugc.gov.bd/notice', title: 'Official notice', domain: 'ugc.gov.bd', quote: 'The notice confirms the event.', stance: 'supports' }]
  const html = renderToStaticMarkup(React.createElement(Summary, { report, evidence }))
  assert.match(html, /<h2 id="report-title">সত্য<\/h2>/)
  assert.match(html, /href="https:\/\/ugc.gov.bd\/notice"/)
  assert.match(html, /The notice confirms the event/)
})

test('a stored verdict without its matching citation is shown as unverified', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const report = { label: 'contradicted', flags: [], evidence_coverage: 'low', summary: 'Contradicted.', reasons: [{ evidence_id: 'ev_1', url: 'https://official.example/one', stance: 'contradicts', summary: 'Wrong place.' }], comparison_method: 'gemini', fallbacks_used: [], limitations: [], layers }
  const unrelated = { evidence_id: 'ev_1', url: 'https://official.example/other', title: 'Unrelated', domain: 'official.example', quote: 'The building is in Paris.', stance: 'contradicts' }
  const html = renderToStaticMarkup(React.createElement(Summary, { report, evidence: [unrelated] }))
  assert.match(html, /<h2 id="report-title">যাচাই করা যায়নি<\/h2>/)
  assert.doesNotMatch(html, /href=|The building is in Paris/)
})

test('quick report quotes only cited evidence and supported event details', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const source = { evidence_id: 'ev_1', url: 'https://official.example/place', title: 'Official location', domain: 'official.example', quote: 'The monument is in Paris.', stance: 'contradicts' }
  const report = { label: 'contradicted', flags: [], evidence_coverage: 'high', summary: 'Contradicted.', reasons: [{ evidence_id: 'ev_1', url: source.url, stance: 'contradicts', summary: 'Location differs.' }], comparison_method: 'gemini', fallbacks_used: [], limitations: [], layers, related_event: { value: 'The monument is in Paris.', evidence_id: 'ev_1', url: source.url } }
  const html = renderToStaticMarkup(React.createElement(Summary, { report, evidence: [source] }))
  assert.match(html, /The monument is in Paris/)
  assert.match(html, /<h2 id="report-title">মিথ্যা<\/h2>/)
  assert.match(html, /সূত্রে পাওয়া সংশোধিত তথ্য/)
  assert.match(html, /Official location/)
  assert.match(html, /সূত্রে পাওয়া সংশোধিত তথ্য/)
  assert.match(html, /Paris/)
  assert.equal((html.match(/The monument is in Paris\./g) || []).length, 1)
  assert.doesNotMatch(html, /Berlin/)
  assert.doesNotMatch(html, /সূত্র প্রকাশের তারিখ/)
  assert.doesNotMatch(html, /ঘটনার তারিখ<\/dt>/)
})

test('official address conclusion names the established city without claiming image origin', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const source = { evidence_id: 'ev_address', url: 'https://example.org/access', title: 'Official access', domain: 'example.org', source_type: 'official_authority', quote: 'Address 75007 Paris', stance: 'contradicts', published_at: null }
  const report = { label: 'contradicted', flags: [], evidence_coverage: 'low', summary: 'Contradicted.', reasons: [{ evidence_id: source.evidence_id, url: source.url, stance: 'contradicts', summary: 'The official source gives an address in Paris, not the claimed place.' }], comparison_method: 'rule_fallback', fallbacks_used: [], limitations: [], layers }
  const html = renderToStaticMarkup(React.createElement(Summary, { report, evidence: [source], claim: 'The Eiffel Tower is in Berlin.' }))
  assert.match(html, /Paris/)
  assert.match(html, /Address 75007 Paris/)
  assert.match(html, /https:\/\/example.org\/access/)
  assert.doesNotMatch(html, /ছবিটির সত্যতা|image’s authenticity/)
})

test('event date and source publication date are distinct and cited', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const Details = await component('src/components/VerificationSummary.tsx', 'VerificationDetails')
  const url = 'https://official.example/opening'
  const source = { evidence_id: 'ev_date', url, title: 'Opening notice', domain: 'official.example', quote: 'The bridge opened in Dhaka on 12 May 2024.', published_at: '2024-05-15T00:00:00Z', stance: 'supports' }
  const report = { label: 'verified', flags: [], evidence_coverage: 'high', summary: 'Verified.', reasons: [{ evidence_id: 'ev_date', url, stance: 'supports', summary: 'Opening.' }], comparison_method: 'gemini', fallbacks_used: [], limitations: [], layers, event_details: { what: { value: source.quote, evidence_id: 'ev_date', url }, when: { value: '12 May 2024', evidence_id: 'ev_date', url }, where: { value: 'Dhaka', evidence_id: 'ev_date', url }, reported_by: null } }
  const html = renderToStaticMarkup(React.createElement(Summary, { report, evidence: [source] }))
  assert.match(html, /12 May 2024/)
  assert.match(html, /href="https:\/\/official.example\/opening"/)
  assert.doesNotMatch(html, /অনুসন্ধানে পাওয়া তারিখ/)
  const detailHtml = renderToStaticMarkup(React.createElement(Details, { report, evidence: [source] }))
  assert.match(detailHtml, /ঘটনার তারিখ/)
  assert.match(detailHtml, /12 May 2024/)
})

test('mixed evidence summary shows both cited sides without a false verdict', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const evidence = [
    { evidence_id: 'ev_support', url: 'https://a.example/report', title: 'First report', quote: 'The event happened.', stance: 'supports' },
    { evidence_id: 'ev_against', url: 'https://b.example/report', title: 'Second report', quote: 'The event did not happen.', stance: 'contradicts' },
  ]
  const report = { label: 'conflicting', flags: [], evidence_coverage: 'medium', summary: 'Conflicting evidence.', reasons: evidence.map(item => ({ evidence_id: item.evidence_id, url: item.url, stance: item.stance, summary: 'Cited excerpt.' })), comparison_method: 'gemini', fallbacks_used: [], limitations: [], layers }
  const html = renderToStaticMarkup(React.createElement(Summary, { report, evidence, claim: 'The event happened.' }))
  assert.match(html, /যাচাই করা যায়নি/)
  assert.match(html, /The event happened/)
  assert.match(html, /সূত্রগুলো একমত নয়/)
  assert.doesNotMatch(html, /The event did not happen|href=/)
})

test('publisher identity remains separate from claim verdict and cites direct evidence', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const Details = await component('src/components/VerificationSummary.tsx', 'VerificationDetails')
  const base = { label: 'insufficient_evidence', flags: [], evidence_coverage: 'low', summary: 'Insufficient.', reasons: [], comparison_method: 'none', fallbacks_used: [], limitations: [], layers }
  const unknown = renderToStaticMarkup(React.createElement(Summary, { report: { ...base, publisher: { status: 'unverified', claimed_name: 'Jamuna TV', evidence: null } } }))
  assert.match(unknown, /যাচাই করা যায়নি/)
  assert.doesNotMatch(unknown, /Jamuna TV/)
  const publisherReport = { ...base, publisher: { status: 'confirmed_published', claimed_name: 'Jamuna TV', scope: 'claim', evidence: { value: 'A bridge opened in Dhaka today', evidence_id: 'ev_1', url: 'https://jamuna.tv/article' } } }
  const evidence = [{ evidence_id: 'ev_1', url: 'https://jamuna.tv/article', quote: 'A bridge opened in Dhaka today' }]
  const published = renderToStaticMarkup(React.createElement(Details, { report: publisherReport, evidence }))
  assert.match(published, /নিজেদের সাইটে দাবিটি প্রকাশ করেছে/)
  assert.match(published, /এই ছবির উৎস যাচাই হয়নি/)
  assert.match(published, /href="https:\/\/jamuna.tv\/article"/)
})

test('partial state explains provider limitation in Bangla', async () => {
  const Banner = await component('src/components/LimitationsBanner.tsx')
  const html = renderToStaticMarkup(React.createElement(Banner, { limitations: ['Live web retrieval is unavailable because Tavily is not configured.'], fallbacks: [] }))
  assert.match(html, /Tavily কনফিগার করা নেই/)
  assert.match(html, /সীমাবদ্ধতা/)
})

test('failed search explains checked work and keeps unknown facts unknown', async () => {
  const Summary = await component('src/components/VerificationSummary.tsx')
  const Details = await component('src/components/VerificationSummary.tsx', 'VerificationDetails')
  const report = { label: 'insufficient_evidence', flags: [], evidence_coverage: 'low', summary: 'Insufficient.', reasons: [], comparison_method: 'rule_fallback', fallbacks_used: [], limitations: [], layers }
  const retrieval = { status: 'unavailable', query_count: 1, successful_queries: 0, retrieved_at: '2026-11-05T00:00:00Z', limitation: 'Search timed out.' }
  const html = renderToStaticMarkup(React.createElement(Summary, { report, retrieval, partial: true }))
  assert.match(html, /যাচাই করা যায়নি/)
  assert.match(html, /সূত্র অনুসন্ধান ব্যর্থ হয়েছে/)
  assert.doesNotMatch(html, /href=/)
  const detailHtml = renderToStaticMarkup(React.createElement(Details, { report, retrieval }))
  assert.match(detailHtml, /১টি অনুসন্ধান চেষ্টা করা হয়েছে/)
  assert.match(detailHtml, /লাইভ সূত্র অনুসন্ধান ব্যর্থ হয়েছে/)
})

test('evidence card renders safe external citation and timestamps', async () => {
  const Card = await component('src/components/EvidenceCard.tsx')
  const html = renderToStaticMarkup(React.createElement(Card, { item: { evidence_id: 'ev_1', url: 'https://ugc.gov.bd/notice', title: 'বিজ্ঞপ্তি', domain: 'ugc.gov.bd', source_type: 'official_authority', snippet: 'সরকারি সংবাদ', published_at: null, retrieved_at: '2026-11-02T00:00:00Z', query: 'দাবি', stance: 'supports', relevance: 1, reason: 'সমর্থন করে', quote: 'সরকারি সংবাদ' } }))
  assert.match(html, /rel="noopener noreferrer"/)
  assert.match(html, /অনুসন্ধানে পাওয়া তারিখ \(যাচাই হয়নি\): তারিখ অজানা/)
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

import { removeCachedReport, saveCachedReport } from '../pwa/reportCache'

export type UploadResult = {
  analysis_id: string
  status: 'awaiting_confirmation'
  image_url: string
  caption: string | null
  ocr: OcrResult
}

export type OcrResult = {
  text: string
  confidence: number | null
  needs_confirmation: boolean
  error_code: string | null
}

export type ClaimExtraction = {
  claim: string | null
  claimed_source: string | null
  people: string[]
  organizations: string[]
  places: string[]
  event_date_text: string | null
  event_date: string | null
  keywords: string[]
  search_queries_bn: string[]
  search_queries_en: string[]
  needs_user_confirmation: boolean
  ambiguities: string[]
}

export type AnalysisRead = {
  analysis_id: string
  created_at: string
  status: 'processing' | 'awaiting_confirmation' | 'completed' | 'partial' | 'failed'
  image_url: string
  caption: string | null
  ocr: OcrResult | null
  extraction: ClaimExtraction | null
  extraction_method: string | null
  retrieval: RetrievalResult | null
  evidence: EvidenceResult[]
  limitations: string[]
  verification: VerificationResult | null
  dataset_matches: DatasetMatchResult[]
}

export type DatasetMatchResult = {
  dataset_id: string
  record_id: string
  match_type: 'related_claim' | 'exact_image'
  similarity: number
  claim_text: string | null
  original_label: string | null
  source_url: string
  license: string
  attribution: string
  original_event_date: string | null
  original_location: string | null
  provenance_url: string | null
  matched_at: string
}

export type VerificationResult = {
  label: 'verified' | 'supported' | 'contradicted' | 'conflicting' | 'unverified' | 'insufficient_evidence'
  flags: string[]
  evidence_coverage: 'low' | 'medium' | 'high'
  summary: string
  reasons: { evidence_id: string; url: string; stance: string; summary: string }[]
  comparison_method: string
  fallbacks_used: string[]
  limitations: string[]
  layers: Record<string, { status: string; summary: string }>
  event_details?: Record<'what' | 'when' | 'where' | 'reported_by', { value: string; evidence_id: string; url: string } | null>
}

export type RetrievalResult = {
  status: 'completed' | 'partial' | 'no_results' | 'unavailable'
  query_count: number
  successful_queries: number
  retrieved_at: string
  limitation: string | null
}

export type EvidenceResult = {
  evidence_id: string
  url: string
  canonical_url: string
  title: string
  domain: string
  source_type: string
  snippet: string
  published_at: string | null
  retrieved_at: string
  query: string
  stance: string | null
  relevance: number | null
  reason: string | null
  quote: string | null
}

export type AnalysisList = { items: AnalysisRead[]; total: number; limit: number; offset: number }

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'
const requireOnline = () => { if (!navigator.onLine) throw new Error('ইন্টারনেট সংযোগ নেই। সংযোগ ফিরে এলে আবার চেষ্টা করুন।') }

export async function uploadAnalysis(file: File, caption: string): Promise<UploadResult> {
  requireOnline()
  const body = new FormData()
  body.append('file', file)
  if (caption.trim()) body.append('caption', caption.trim())
  let response: Response
  try { response = await fetch(`${apiBaseUrl}/analyses`, { method: 'POST', body }) }
  catch { throw new Error('ছবি পাঠানো যায়নি। সংযোগ পরীক্ষা করে আবার চেষ্টা করুন; বাছাই করা ছবিটি এখানেই আছে।') }
  if (!response.ok) {
    const messages: Record<number, string> = {
      400: 'ছবির ফাইলটি খালি। অন্য ছবি বেছে নিন।',
      413: 'ছবির আকার ৮ MB-এর মধ্যে রাখুন।',
      415: 'JPEG, PNG বা WebP ছবি বেছে নিন। ফাইলের ধরন ও ভেতরের তথ্য মিলতে হবে।',
      422: 'ছবিটি খোলা যাচ্ছে না। অন্য ছবি বেছে নিন।',
      429: 'অল্প সময়ে অনেক ছবি পাঠানো হয়েছে। কিছুক্ষণ পরে আবার চেষ্টা করুন; বাছাই করা ছবিটি এখানেই আছে।',
    }
    throw new Error(messages[response.status] || 'ছবি আপলোড করা যায়নি। আবার চেষ্টা করুন; বাছাই করা ছবিটি এখানেই আছে।')
  }
  return response.json() as Promise<UploadResult>
}

export function imageUrl(path: string): string {
  return new URL(path, new URL(apiBaseUrl, window.location.origin)).toString()
}

export async function saveOcrText(analysisId: string, text: string): Promise<OcrResult> {
  requireOnline()
  const response = await fetch(`${apiBaseUrl}/analyses/${analysisId}/ocr`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(typeof payload?.detail === 'string' ? payload.detail : `Save failed (${response.status}).`)
  }
  const analysis = await response.json() as AnalysisRead
  removeCachedReport(analysisId)
  if (!analysis.ocr) throw new Error('OCR result is missing.')
  return analysis.ocr
}

export function retryOcrWithVision(analysisId: string): Promise<AnalysisRead> {
  requireOnline()
  return fetch(`${apiBaseUrl}/analyses/${encodeURIComponent(analysisId)}/ocr/vision-retry`, { method: 'POST' }).then(readResponse<AnalysisRead>).then(value => { removeCachedReport(analysisId); return value })
}

export async function runExtraction(analysisId: string, claim?: string): Promise<AnalysisRead> {
  requireOnline()
  const response = await fetch(`${apiBaseUrl}/analyses/${analysisId}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(claim === undefined ? {} : { claim }),
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(typeof payload?.detail === 'string' ? payload.detail : `Extraction failed (${response.status}).`)
  }
  removeCachedReport(analysisId)
  return response.json() as Promise<AnalysisRead>
}

export async function retrieveEvidence(analysisId: string): Promise<AnalysisRead> {
  requireOnline()
  const response = await fetch(`${apiBaseUrl}/analyses/${analysisId}/retrieve`, { method: 'POST' })
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(typeof payload?.detail === 'string' ? payload.detail : `Search failed (${response.status}).`)
  }
  removeCachedReport(analysisId)
  return response.json() as Promise<AnalysisRead>
}

async function readResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new Error(typeof payload?.detail === 'string' ? payload.detail : `Request failed (${response.status}).`)
  }
  return response.json() as Promise<T>
}

export function getAnalysis(analysisId: string): Promise<AnalysisRead> {
  return fetch(`${apiBaseUrl}/analyses/${encodeURIComponent(analysisId)}`).then(readResponse<AnalysisRead>).then(value => { if (value.verification && value.status !== 'processing' && value.status !== 'failed') saveCachedReport(value); else if (!value.verification) removeCachedReport(analysisId); return value })
}

export function listAnalyses(limit = 20, offset = 0): Promise<AnalysisList> {
  return fetch(`${apiBaseUrl}/analyses?limit=${limit}&offset=${offset}`).then(readResponse<AnalysisList>).then(page => { page.items.forEach(item => { if (item.verification && item.status !== 'processing' && item.status !== 'failed') saveCachedReport(item) }); return page })
}

export function verifyAnalysis(analysisId: string): Promise<AnalysisRead> {
  requireOnline()
  return fetch(`${apiBaseUrl}/analyses/${encodeURIComponent(analysisId)}/verify`, { method: 'POST' }).then(readResponse<AnalysisRead>).then(value => { saveCachedReport(value); return value })
}

export function matchDataset(analysisId: string): Promise<AnalysisRead> {
  requireOnline()
  return fetch(`${apiBaseUrl}/analyses/${encodeURIComponent(analysisId)}/match`, { method: 'POST' }).then(readResponse<AnalysisRead>).then(value => { saveCachedReport(value); return value })
}

export async function deleteAnalysis(analysisId: string): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/analyses/${encodeURIComponent(analysisId)}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(`Delete failed (${response.status}).`)
  removeCachedReport(analysisId)
}


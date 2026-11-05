import type { AnalysisRead, VerificationResult } from '../api/truthlayer'

const KEY = 'truthlayer-reports-v1'
const MAX_REPORTS = 10
const MAX_BYTES = 500_000

export type CachedEvidence = {
  evidence_id: string
  title: string
  url: string
  domain: string
  source_type: string
  stance: string | null
  quote?: string | null
  published_at: string | null
  retrieved_at: string
}

export type CachedReport = {
  analysis_id: string
  saved_at: string
  retrieved_at: string | null
  claim: string
  verification: VerificationResult
  evidence: CachedEvidence[]
  limitations: string[]
}

function read(): CachedReport[] {
  try {
    const value = JSON.parse(localStorage.getItem(KEY) || '[]')
    return Array.isArray(value) ? value.filter(item => typeof item?.analysis_id === 'string' && typeof item?.saved_at === 'string' && item.verification && item.verification.decision_method === 'python_evidence_fusion_v9') : []
  } catch { return [] }
}

export function listCachedReports(): CachedReport[] { return read() }
export function getCachedReport(id: string): CachedReport | null { return read().find(item => item.analysis_id === id) || null }

export function saveCachedReport(analysis: AnalysisRead): void {
  if (!analysis.verification) return
  const snapshot: CachedReport = {
    analysis_id: analysis.analysis_id,
    saved_at: new Date().toISOString(),
    retrieved_at: analysis.retrieval?.retrieved_at || null,
    claim: (analysis.extraction?.claim || '').slice(0, 1000),
    verification: analysis.verification,
    evidence: analysis.evidence.slice(0, 30).map(item => ({
      evidence_id: item.evidence_id, title: item.title.slice(0, 300), url: item.url,
      domain: item.domain, source_type: item.source_type, stance: item.stance,
      quote: analysis.verification?.reasons.some(reason => reason.evidence_id === item.evidence_id) ? item.quote?.slice(0, 320) || null : null,
      published_at: item.published_at, retrieved_at: item.retrieved_at,
    })),
    limitations: analysis.limitations,
  }
  const reports = [snapshot, ...read().filter(item => item.analysis_id !== analysis.analysis_id)].slice(0, MAX_REPORTS)
  try {
    while (reports.length && new TextEncoder().encode(JSON.stringify(reports)).byteLength > MAX_BYTES) reports.pop()
    localStorage.setItem(KEY, JSON.stringify(reports))
  } catch { /* Storage may be disabled or full; online reports still work. */ }
}

export function removeCachedReport(id: string): void {
  try { localStorage.setItem(KEY, JSON.stringify(read().filter(item => item.analysis_id !== id))) } catch { /* Ignore unavailable storage. */ }
}

import { useEffect, useRef, useState } from 'react'
import { deleteAnalysis, getAnalysis, imageUrl, matchDataset, retrieveEvidence, runExtraction, saveOcrText, verifyAnalysis, type AnalysisRead } from '../api/truthlayer'
import GroupedEvidence from '../components/GroupedEvidence'
import LimitationsBanner from '../components/LimitationsBanner'
import VerificationSummary from '../components/VerificationSummary'
import CachedReportView from '../components/CachedReportView'
import { getCachedReport, type CachedReport } from '../pwa/reportCache'

const steps = ['ছবি পড়া', 'দাবি বোঝা', 'সূত্র খোঁজা', 'রিপোর্ট তৈরি']

export default function AnalysisPage({ analysisId }: { analysisId: string }) {
  const [analysis, setAnalysis] = useState<AnalysisRead | null>(null)
  const [claim, setClaim] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [correction, setCorrection] = useState('')
  const [editingClaim, setEditingClaim] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [cachedReport, setCachedReport] = useState<CachedReport | null>(null)
  const [usingCached, setUsingCached] = useState(false)
  const [allowResume, setAllowResume] = useState(false)
  const attempted = useRef(new Set<string>())

  useEffect(() => { attempted.current.clear() }, [analysisId])

  useEffect(() => {
    if (!analysis || busy || error || usingCached || !navigator.onLine || (analysis.status === 'processing' && !allowResume)) return
    let key = ''
    let action: (() => Promise<AnalysisRead>) | null = null
    if (analysis.ocr?.needs_confirmation && analysis.ocr.text.trim() && (analysis.ocr.confidence ?? 0) >= 0.55) {
      key = 'ocr'; action = async () => { await saveOcrText(analysisId, analysis.ocr!.text); return getAnalysis(analysisId) }
    } else if (analysis.ocr && !analysis.ocr.needs_confirmation && !analysis.extraction) {
      key = 'extract'; action = () => runExtraction(analysisId)
    } else if (analysis.extraction?.claim && !analysis.extraction.needs_user_confirmation && !analysis.retrieval) {
      key = 'search'; action = () => retrieveEvidence(analysisId)
    } else if (analysis.retrieval && !analysis.verification) {
      key = 'verify'; action = () => verifyAnalysis(analysisId)
    }
    if (!action || attempted.current.has(key)) return
    attempted.current.add(key)
    void act(key, action)
  }, [analysis, busy, error, usingCached, allowResume, analysisId])

  useEffect(() => {
    if (analysis?.status !== 'processing' || busy || allowResume || usingCached) return
    let active = true
    let checking = false
    const started = Date.now()
    const timer = window.setInterval(async () => {
      if (checking || !active) return
      if (Date.now() - started > 30000) {
        window.clearInterval(timer)
        setError('যাচাইয়ের অগ্রগতি পাওয়া যাচ্ছে না। আবার চেষ্টা করুন।')
        return
      }
      checking = true
      try {
        const value = await getAnalysis(analysisId)
        if (active && value.status !== 'processing') { setAnalysis(value); setClaim(value.extraction?.claim || ''); setCorrection(value.extraction?.claim || value.ocr?.text || '') }
      } catch { /* The next check may succeed after a temporary connection error. */ }
      checking = false
    }, 2000)
    return () => { active = false; window.clearInterval(timer) }
  }, [analysis?.status, busy, allowResume, usingCached, analysisId])

  useEffect(() => {
    let active = true
    setLoading(true)
    setAnalysis(null)
    setError(null)
    setAllowResume(false)
    if (!navigator.onLine) {
      setCachedReport(getCachedReport(analysisId))
      setUsingCached(true)
      setLoading(false)
    } else {
      getAnalysis(analysisId).then(value => { if (active) { setAnalysis(value); setCachedReport(null); setUsingCached(false); setClaim(value.extraction?.claim || ''); setCorrection(value.extraction?.claim || value.ocr?.text || '') } }).catch(cause => { if (active) { setCachedReport(getCachedReport(analysisId)); setUsingCached(true); setError(cause instanceof Error ? cause.message : 'বিশ্লেষণ পাওয়া যায়নি।') } }).finally(() => { if (active) setLoading(false) })
    }
    return () => { active = false }
  }, [analysisId])

  useEffect(() => {
    const update = () => {
      const isOffline = !navigator.onLine
      if (isOffline) { setCachedReport(getCachedReport(analysisId)); setUsingCached(true) }
      else void refresh().catch(() => { setCachedReport(getCachedReport(analysisId)); setUsingCached(true) })
    }
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update) }
  }, [analysisId])

  async function refresh() {
    const value = await getAnalysis(analysisId)
    setAnalysis(value)
    setCachedReport(null)
    setUsingCached(false)
    setClaim(value.extraction?.claim || '')
    setCorrection(value.extraction?.claim || value.ocr?.text || '')
  }

  async function act(name: string, action: () => Promise<AnalysisRead>) {
    setBusy(name)
    setError(null)
    try { const value = await action(); setAnalysis(value); setCachedReport(null); setUsingCached(false); setClaim(value.extraction?.claim || ''); setCorrection(value.extraction?.claim || value.ocr?.text || '') }
    catch (cause) {
      try { const latest = await getAnalysis(analysisId); setAnalysis(latest); setClaim(latest.extraction?.claim || ''); setCorrection(latest.extraction?.claim || latest.ocr?.text || '') } catch { /* Keep the last visible progress if the server is unavailable. */ }
      setError(cause instanceof Error ? cause.message : 'কাজটি সম্পন্ন হয়নি।')
    }
    finally { setBusy(null) }
  }

  async function submitCorrection() {
    const text = correction.trim()
    if (!text) return
    attempted.current.clear()
    await act('correction', async () => {
      if (analysis?.ocr?.needs_confirmation) await saveOcrText(analysisId, text)
      return runExtraction(analysisId, text)
    })
  }

  async function rerunClaim() {
    const text = claim.trim()
    if (!text) return
    attempted.current.clear()
    setEditingClaim(false)
    await act('claim', () => runExtraction(analysisId, text))
  }

  async function remove() {
    setBusy('delete')
    setError(null)
    try { await deleteAnalysis(analysisId); window.location.hash = '#/history' }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'বিশ্লেষণ মুছতে পারিনি।') }
    finally { setBusy(null) }
  }

  if (loading) return <main className="page"><p role="status" className="panel">বিশ্লেষণ আসছে…</p></main>
  if (cachedReport && usingCached) return <CachedReportView report={cachedReport} onRetry={() => { setBusy('retry'); void refresh().catch(cause => setError(cause instanceof Error ? cause.message : 'রিপোর্ট খোলা যায়নি।')).finally(() => setBusy(null)) }} retrying={busy === 'retry'} />
  if (!analysis) return <main className="page"><p role="alert" className="alert error">{error || 'বিশ্লেষণ পাওয়া যায়নি।'}</p><a href="#/history">ইতিহাসে ফিরুন</a></main>

  const ocrReady = !!analysis.ocr && !analysis.ocr.needs_confirmation
  const claimReady = !!analysis.extraction?.claim && !analysis.extraction.needs_user_confirmation
  const needsCorrection = (!!analysis.ocr?.needs_confirmation && (!analysis.ocr.text.trim() || (analysis.ocr.confidence ?? 0) < 0.55)) || (!!analysis.extraction && analysis.extraction.needs_user_confirmation)
  const reportReady = !!analysis.verification && analysis.status !== 'processing' && analysis.status !== 'failed' && !['claim', 'search', 'verify', 'correction'].includes(busy || '')
  const stage = reportReady ? 4 : analysis.retrieval ? 3 : claimReady ? 2 : ocrReady ? 1 : 0

  return <main className="page">
    <div className="page-heading"><p className="eyebrow">{reportReady ? 'রিপোর্ট প্রস্তুত' : 'যাচাই চলছে'} · {new Date(analysis.created_at).toLocaleString('bn-BD')}</p><h1>{reportReady ? 'যাচাইয়ের রিপোর্ট' : 'ছবিটি যাচাই করা হচ্ছে'}</h1><p className="muted">{reportReady ? 'নিচে সিদ্ধান্ত, সূত্র ও সীমাবদ্ধতা দেখুন।' : 'ছবির লেখা ও পাওয়া সূত্র মিলিয়ে দেখা হচ্ছে। প্রয়োজন হলে আপনার সাহায্য চাওয়া হবে।'}</p></div>
    {!reportReady && <ol className="progress" aria-label="যাচাইয়ের অগ্রগতি">{steps.map((step, index) => <li key={step} className={index < stage ? 'done' : ''}><span>{index + 1}</span>{step}</li>)}</ol>}
    {busy && <p className="notice compact" role="status">{busy === 'ocr' ? 'ছবির লেখা পড়া হচ্ছে…' : busy === 'extract' || busy === 'claim' ? 'মূল দাবি বোঝা হচ্ছে…' : busy === 'search' ? 'বিশ্বস্ত সূত্র খোঁজা হচ্ছে…' : 'রিপোর্ট তৈরি হচ্ছে…'}</p>}
    {analysis.status === 'partial' && reportReady && !busy && <p className="notice compact" role="status">এই রিপোর্ট আংশিক। নিচের সীমাবদ্ধতা দেখুন।</p>}
    {analysis.status === 'failed' && <p className="alert error" role="alert">বিশ্লেষণ সম্পন্ন হয়নি। আবার চেষ্টা করুন।</p>}
    {error && <div role="alert" className="alert error"><p>{error}</p><button className="button secondary" onClick={() => { attempted.current.clear(); setAllowResume(true); setError(null) }}>আবার চেষ্টা করুন</button></div>}
    <div className={reportReady ? 'analysis-grid report-layout' : 'analysis-grid'}>
      <div className="analysis-main">
        {claimReady && reportReady && <VerificationSummary report={analysis.verification!} />}
        {claimReady && reportReady && <GroupedEvidence claim={analysis.extraction?.claim || ''} evidence={analysis.evidence} />}
        <div className={reportReady ? 'report-inputs' : ''}><section className="panel"><p className="eyebrow">আপলোড করা ছবি</p><img className="source-image" src={imageUrl(analysis.image_url)} alt="যাচাইয়ের জন্য আপলোড করা পোস্ট" />{analysis.caption && <p className="muted">ক্যাপশন: {analysis.caption}</p>}</section>
        {needsCorrection && !reportReady && analysis.status !== 'processing' && <section className="panel correction-panel"><p className="eyebrow">একটি তথ্য নিশ্চিত করুন</p><h2>ছবির মূল দাবিটি কী?</h2><p className="muted">ছবিতে যা লেখা আছে তা দেখে এক বাক্যে মূল দাবিটি লিখুন। এরপর যাচাই নিজে থেকেই চলবে।</p><label className="field-label" htmlFor="correction-text">মূল দাবি</label><textarea id="correction-text" rows={4} maxLength={1000} value={correction} onChange={event => setCorrection(event.target.value)} /><button className="button primary full" disabled={!correction.trim() || !!busy} onClick={submitCorrection}>{busy === 'correction' ? 'সংরক্ষণ হচ্ছে…' : 'দাবি দিয়ে যাচাই চালিয়ে যান'}</button></section>}
        {reportReady && <section className="panel"><p className="eyebrow">যাচাই করা দাবি</p><p>{analysis.extraction?.claim}</p>{editingClaim ? <><label className="field-label" htmlFor="edit-claim">দাবি ঠিক করুন</label><textarea id="edit-claim" rows={3} maxLength={1000} value={claim} onChange={event => setClaim(event.target.value)} /><div className="button-row"><button className="button primary" disabled={!claim.trim() || !!busy} onClick={rerunClaim}>দাবি ঠিক করে আবার যাচাই করুন</button><button className="button secondary" onClick={() => { setClaim(analysis.extraction?.claim || ''); setEditingClaim(false) }}>বাতিল</button></div></> : <button className="button secondary" onClick={() => setEditingClaim(true)}>দাবি ঠিক করে আবার যাচাই করুন</button>}</section>}
        </div>
        {reportReady && <details className="panel optional-detail"><summary>পুরোনো রেকর্ডের সঙ্গে মিল দেখুন</summary><div id="dataset-title"><p className="muted small">আগের কোনো রেকর্ডের মিল বর্তমান দাবির রায় নয়। একই ছবির নথিবদ্ধ উৎস থাকলে মূল ঘটনার তথ্য দেখানো হয়।</p>
          <button className="button secondary full" disabled={!!busy} onClick={() => act('match', () => matchDataset(analysisId))}>{busy === 'match' ? 'মিল খোঁজা হচ্ছে…' : 'ডেটাসেটে মিল খুঁজুন'}</button>
          {analysis.dataset_matches?.length > 0 && <div className="dataset-matches">{analysis.dataset_matches.map(item => <article className="evidence-card" key={`${item.dataset_id}:${item.record_id}`}><h3>{item.match_type === 'exact_image' ? 'একই ছবির ফাইল পাওয়া গেছে' : 'সম্পর্কিত পুরোনো দাবি'}</h3><p className="small muted">{item.dataset_id} · রেকর্ড {item.record_id} · মিল {Math.round(item.similarity * 100).toLocaleString('bn-BD')}%</p>{item.claim_text && <p>{item.claim_text}</p>}{item.original_label && <p>ডেটাসেটের মূল রায়: {item.original_label} (বর্তমান রায় নয়)</p>}<p><a href={item.source_url} target="_blank" rel="noopener noreferrer">মূল রেকর্ড দেখুন</a> · {item.attribution} · {item.license}</p>{item.provenance_url && <div className="notice compact"><strong>নথিবদ্ধ মূল ঘটনা</strong><p>{item.original_event_date && `তারিখ: ${item.original_event_date} · `}{item.original_location && `স্থান: ${item.original_location}`}</p><a href={item.provenance_url} target="_blank" rel="noopener noreferrer">উৎসের প্রমাণ দেখুন</a></div>}</article>)}</div>}
        </div></details>}
        {reportReady && <LimitationsBanner limitations={analysis.limitations} fallbacks={analysis.verification?.fallbacks_used} />}
        <div className="button-row bottom-actions"><a className="button secondary" href="#/history">ইতিহাসে ফিরুন</a>{confirmDelete ? <span className="delete-confirm"><span>এই বিশ্লেষণ ও ছবিটি মুছবেন?</span><button className="button danger" disabled={!!busy} onClick={remove}>{busy === 'delete' ? 'মুছছে…' : 'হ্যাঁ, মুছুন'}</button><button className="button secondary" disabled={!!busy} onClick={() => setConfirmDelete(false)}>বাতিল</button></span> : <button className="button danger" disabled={!!busy} onClick={() => setConfirmDelete(true)}>এই বিশ্লেষণ মুছুন</button>}</div>
      </div>
      {reportReady && <aside className="sidebar-note"><h2>রিপোর্ট বুঝবেন যেভাবে</h2><p>দাবির সিদ্ধান্ত পাওয়া সূত্রের ওপর নির্ভর করে। উৎস পরিচয়, প্রসঙ্গ ও ছবির সত্যতা আলাদা করে দেখানো হয়। যথেষ্ট প্রমাণ না থাকলে সেগুলো “এখনো নিশ্চিত নয়” থাকবে।</p></aside>}
    </div>
  </main>
}

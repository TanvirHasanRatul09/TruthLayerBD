import { useEffect, useRef, useState } from 'react'
import { deleteAnalysis, getAnalysis, imageUrl, matchDataset, retrieveEvidence, runExtraction, saveOcrText, verifyAnalysis, type AnalysisRead } from '../api/truthlayer'
import GroupedEvidence from '../components/GroupedEvidence'
import LimitationsBanner from '../components/LimitationsBanner'
import VerificationSummary, { VerificationDetails } from '../components/VerificationSummary'
import CachedReportView from '../components/CachedReportView'
import { getCachedReport, type CachedReport } from '../pwa/reportCache'
import { displayError, useI18n } from '../i18n'

const steps = [['ছবি পড়া', 'Read image'], ['দাবি বোঝা', 'Identify claim'], ['সূত্র খোঁজা', 'Search sources'], ['রিপোর্ট তৈরি', 'Create report']] as const

export default function AnalysisPage({ analysisId }: { analysisId: string }) {
  const { language, tr, date, number } = useI18n()
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
        setError(tr('যাচাইয়ের অগ্রগতি পাওয়া যাচ্ছে না। আবার চেষ্টা করুন।', 'Analysis progress is unavailable. Try again.'))
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
      getAnalysis(analysisId).then(value => { if (active) { setAnalysis(value); setCachedReport(null); setUsingCached(false); setClaim(value.extraction?.claim || ''); setCorrection(value.extraction?.claim || value.ocr?.text || '') } }).catch(cause => { if (active) { setCachedReport(getCachedReport(analysisId)); setUsingCached(true); setError(cause instanceof Error ? cause.message : tr('বিশ্লেষণ পাওয়া যায়নি।', 'Analysis not found.')) } }).finally(() => { if (active) setLoading(false) })
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
      setError(cause instanceof Error ? cause.message : tr('কাজটি সম্পন্ন হয়নি।', 'The action could not be completed.'))
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

  async function retrySources() {
    attempted.current.delete('search')
    attempted.current.delete('verify')
    await act('search', () => retrieveEvidence(analysisId))
  }

  async function remove() {
    setBusy('delete')
    setError(null)
    try { await deleteAnalysis(analysisId); window.location.hash = '#/history' }
    catch (cause) { setError(cause instanceof Error ? cause.message : tr('বিশ্লেষণ মুছতে পারিনি।', 'Could not delete the analysis.')) }
    finally { setBusy(null) }
  }

  if (loading) return <main className="page"><p role="status" className="panel">{tr('বিশ্লেষণ আসছে…', 'Loading analysis…')}</p></main>
  if (cachedReport && usingCached) return <CachedReportView report={cachedReport} onRetry={() => { setBusy('retry'); void refresh().catch(cause => setError(cause instanceof Error ? cause.message : tr('রিপোর্ট খোলা যায়নি।', 'Could not open the report.'))).finally(() => setBusy(null)) }} retrying={busy === 'retry'} />
  if (!analysis) return <main className="page"><p role="alert" className="alert error">{error ? displayError(error, language) : tr('বিশ্লেষণ পাওয়া যায়নি।', 'Analysis not found.')}</p><a href="#/history">{tr('ইতিহাসে ফিরুন', 'Back to History')}</a></main>

  const ocrReady = !!analysis.ocr && !analysis.ocr.needs_confirmation
  const claimReady = !!analysis.extraction?.claim && !analysis.extraction.needs_user_confirmation
  const needsCorrection = (!!analysis.ocr?.needs_confirmation && (!analysis.ocr.text.trim() || (analysis.ocr.confidence ?? 0) < 0.55)) || (!!analysis.extraction && analysis.extraction.needs_user_confirmation)
  const reportReady = !!analysis.verification && analysis.status !== 'processing' && analysis.status !== 'failed' && !['claim', 'search', 'verify', 'correction'].includes(busy || '')
  const stage = reportReady ? 4 : analysis.retrieval ? 3 : claimReady ? 2 : ocrReady ? 1 : 0

  return <main className="page">
    {reportReady ? <div className="page-heading report-heading"><p className="eyebrow">{tr('রিপোর্ট প্রস্তুত', 'Report ready')} · {date(analysis.created_at)}</p><h1 className="visually-hidden">{tr('যাচাইয়ের রিপোর্ট', 'Analysis report')}</h1></div> : <div className="page-heading"><p className="eyebrow">{tr('যাচাই চলছে', 'Analysis in progress')} · {date(analysis.created_at)}</p><h1>{tr('ছবিটি যাচাই করা হচ্ছে', 'Analyzing your image')}</h1><p className="muted">{tr('ছবির লেখা ও পাওয়া সূত্র মিলিয়ে দেখা হচ্ছে। প্রয়োজন হলে আপনার সাহায্য চাওয়া হবে।', 'We are reading the image and comparing available sources. We will ask if the claim needs clarification.')}</p></div>}
    {!reportReady && <ol className="progress" aria-label={tr('যাচাইয়ের অগ্রগতি', 'Analysis progress')}>{steps.map(([bn, en], index) => <li key={bn} className={index < stage ? 'done' : index === stage ? 'active' : ''} aria-current={index === stage ? 'step' : undefined}><span>{number(index + 1)}</span>{tr(bn, en)}</li>)}</ol>}
    {busy && <p className="notice compact" role="status">{busy === 'ocr' ? tr('ছবির লেখা পড়া হচ্ছে…', 'Reading image text…') : busy === 'extract' || busy === 'claim' ? tr('মূল দাবি বোঝা হচ্ছে…', 'Identifying the main claim…') : busy === 'search' ? tr('বিশ্বস্ত সূত্র খোঁজা হচ্ছে…', 'Searching for sources…') : tr('রিপোর্ট তৈরি হচ্ছে…', 'Creating report…')}</p>}
    {analysis.status === 'failed' && <p className="alert error" role="alert">{tr('বিশ্লেষণ সম্পন্ন হয়নি। আবার চেষ্টা করুন।', 'Analysis did not finish. Try again.')}</p>}
    {error && <div role="alert" className="alert error"><p>{displayError(error, language)}</p><button className="button secondary" onClick={() => { attempted.current.clear(); setAllowResume(true); setError(null) }}>{tr('আবার চেষ্টা করুন', 'Try again')}</button></div>}
    <div className={reportReady ? 'analysis-grid report-layout' : 'analysis-grid'}>
      <div className="analysis-main">
        {claimReady && reportReady && <><VerificationSummary report={analysis.verification!} evidence={analysis.evidence} claim={analysis.extraction?.claim || ''} retrieval={analysis.retrieval} partial={analysis.status === 'partial'} /><button className="button secondary" disabled={!!busy || !navigator.onLine} onClick={retrySources}>{tr('সূত্র আবার খুঁজে যাচাই করুন', 'Search sources and verify again')}</button></>}
        {claimReady && reportReady && <details className="panel report-evidence"><summary>{tr('সূত্র ও বিস্তারিত দেখুন', 'View evidence and details')}</summary><div className="report-evidence-content"><VerificationDetails report={analysis.verification!} evidence={analysis.evidence} retrieval={analysis.retrieval} /><GroupedEvidence claim={analysis.extraction?.claim || ''} evidence={analysis.evidence} /><LimitationsBanner limitations={analysis.limitations} fallbacks={analysis.verification?.fallbacks_used} /></div></details>}
        <div className={reportReady ? 'report-inputs' : ''}><section className="panel"><p className="eyebrow">{tr('আপলোড করা ছবি', 'Uploaded image')}</p><img className="source-image" src={imageUrl(analysis.image_url)} alt={tr('যাচাইয়ের জন্য আপলোড করা পোস্ট', 'Post uploaded for analysis')} />{analysis.caption && <p className="muted">{tr('ক্যাপশন:', 'Caption:')} {analysis.caption}</p>}</section>
        {needsCorrection && !reportReady && analysis.status !== 'processing' && <section className="panel correction-panel"><p className="eyebrow">{tr('একটি তথ্য নিশ্চিত করুন', 'One quick correction')}</p><h2>{tr('ছবির মূল দাবিটি কী?', 'What is the main claim?')}</h2><p className="muted">{tr('ছবিতে যা লেখা আছে তা দেখে এক বাক্যে মূল দাবিটি লিখুন। এরপর যাচাই নিজে থেকেই চলবে।', 'Read the image and enter its main claim in one sentence. Analysis will then continue automatically.')}</p><label className="field-label" htmlFor="correction-text">{tr('মূল দাবি', 'Main claim')}</label><textarea id="correction-text" rows={4} maxLength={1000} value={correction} onChange={event => setCorrection(event.target.value)} /><button className="button primary full" disabled={!correction.trim() || !!busy} onClick={submitCorrection}>{busy === 'correction' ? tr('সংরক্ষণ হচ্ছে…', 'Saving…') : tr('দাবি দিয়ে যাচাই চালিয়ে যান', 'Continue with this claim')}</button></section>}
        {reportReady && <section className="panel"><p className="eyebrow">{tr('যাচাই করা দাবি', 'Checked claim')}</p><p>{analysis.extraction?.claim}</p>{editingClaim ? <><label className="field-label" htmlFor="edit-claim">{tr('দাবি ঠিক করুন', 'Edit claim')}</label><textarea id="edit-claim" rows={3} maxLength={1000} value={claim} onChange={event => setClaim(event.target.value)} /><div className="button-row"><button className="button primary" disabled={!claim.trim() || !!busy} onClick={rerunClaim}>{tr('দাবি ঠিক করে আবার যাচাই করুন', 'Edit claim and rerun')}</button><button className="button secondary" onClick={() => { setClaim(analysis.extraction?.claim || ''); setEditingClaim(false) }}>{tr('বাতিল', 'Cancel')}</button></div></> : <button className="button secondary" onClick={() => setEditingClaim(true)}>{tr('দাবি ঠিক করে আবার যাচাই করুন', 'Edit claim and rerun')}</button>}</section>}
        </div>
        {reportReady && <details className="panel optional-detail"><summary>{tr('পুরোনো রেকর্ডের সঙ্গে মিল দেখুন', 'Compare with historical records')}</summary><div id="dataset-title"><p className="muted small">{tr('আগের কোনো রেকর্ডের মিল বর্তমান দাবির রায় নয়। একই ছবির নথিবদ্ধ উৎস থাকলে মূল ঘটনার তথ্য দেখানো হয়।', 'A historical match is not the verdict for this claim. An exact image match may show documented event details.')}</p>
          <button className="button secondary full" disabled={!!busy} onClick={() => act('match', () => matchDataset(analysisId))}>{busy === 'match' ? tr('মিল খোঁজা হচ্ছে…', 'Searching records…') : tr('ডেটাসেটে মিল খুঁজুন', 'Search historical records')}</button>
          {analysis.dataset_matches?.length > 0 && <div className="dataset-matches">{analysis.dataset_matches.map(item => <article className="evidence-card" key={`${item.dataset_id}:${item.record_id}`}><h3>{item.match_type === 'exact_image' ? tr('একই ছবির ফাইল পাওয়া গেছে', 'Exact image file found') : tr('সম্পর্কিত পুরোনো দাবি', 'Related historical claim')}</h3><p className="small muted">{item.dataset_id} · {tr('রেকর্ড', 'Record')} {item.record_id} · {tr('মিল', 'Match')} {number(Math.round(item.similarity * 100))}%</p>{item.claim_text && <p>{item.claim_text}</p>}{item.original_label && <p>{tr('ডেটাসেটের মূল রায়:', 'Dataset’s original label:')} {item.original_label} {tr('(বর্তমান রায় নয়)', '(not the current verdict)')}</p>}<p><a href={item.source_url} target="_blank" rel="noopener noreferrer">{tr('মূল রেকর্ড দেখুন', 'View original record')}</a> · {item.attribution} · {item.license}</p>{item.provenance_url && <div className="notice compact"><strong>{tr('নথিবদ্ধ মূল ঘটনা', 'Documented original event')}</strong><p>{item.original_event_date && `${tr('তারিখ:', 'Date:')} ${item.original_event_date} · `}{item.original_location && `${tr('স্থান:', 'Place:')} ${item.original_location}`}</p><a href={item.provenance_url} target="_blank" rel="noopener noreferrer">{tr('উৎসের প্রমাণ দেখুন', 'View provenance source')}</a></div>}</article>)}</div>}
        </div></details>}
        <div className="button-row bottom-actions"><a className="button secondary" href="#/history">{tr('ইতিহাসে ফিরুন', 'Back to History')}</a>{confirmDelete ? <span className="delete-confirm"><span>{tr('এই বিশ্লেষণ ও ছবিটি মুছবেন?', 'Delete this analysis and image?')}</span><button className="button danger" disabled={!!busy} onClick={remove}>{busy === 'delete' ? tr('মুছছে…', 'Deleting…') : tr('হ্যাঁ, মুছুন', 'Yes, delete')}</button><button className="button secondary" disabled={!!busy} onClick={() => setConfirmDelete(false)}>{tr('বাতিল', 'Cancel')}</button></span> : <button className="button danger" disabled={!!busy} onClick={() => setConfirmDelete(true)}>{tr('এই বিশ্লেষণ মুছুন', 'Delete this analysis')}</button>}</div>
      </div>
      {reportReady && <aside className="sidebar-note"><h2>{tr('রিপোর্ট বুঝবেন যেভাবে', 'How to read this report')}</h2><p>{tr('দাবির সিদ্ধান্ত পাওয়া সূত্রের ওপর নির্ভর করে। উৎস পরিচয়, প্রসঙ্গ ও ছবির সত্যতা আলাদা করে দেখানো হয়। যথেষ্ট প্রমাণ না থাকলে সেগুলো “এখনো নিশ্চিত নয়” থাকবে।', 'The claim conclusion depends on available sources. Source identity, context, and image authenticity are assessed separately. When evidence is lacking, their status remains unknown.')}</p></aside>}
    </div>
  </main>
}

import { useEffect, useState } from 'react'
import { deleteAnalysis, listAnalyses, type AnalysisRead } from '../api/truthlayer'
import HistoryList from '../components/HistoryList'
import { listCachedReports } from '../pwa/reportCache'
import { displayError, useI18n } from '../i18n'

export default function HistoryPage() {
  const { language, tr, date, number } = useI18n()
  const [items, setItems] = useState<AnalysisRead[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [offline, setOffline] = useState(() => !navigator.onLine)

  useEffect(() => {
    let active = true
    setLoading(true)
    if (!navigator.onLine) { setLoading(false); return () => { active = false } }
    listAnalyses(20, offset).then(page => { if (active) { setItems(page.items); setTotal(page.total); setError(null) } }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : tr('ইতিহাস আনা যায়নি।', 'Could not load History.')) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [offset])

  useEffect(() => {
    const update = () => {
      const isOffline = !navigator.onLine
      setOffline(isOffline)
      if (!isOffline) {
        setLoading(true)
        listAnalyses(20, offset).then(page => { setItems(page.items); setTotal(page.total); setError(null) }).catch(cause => setError(cause instanceof Error ? cause.message : tr('ইতিহাস আনা যায়নি।', 'Could not load History.'))).finally(() => setLoading(false))
      }
    }
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update) }
  }, [offset])

  async function remove(id: string) {
    setDeleting(id)
    setError(null)
    try { await deleteAnalysis(id); setItems(current => current.filter(item => item.analysis_id !== id)); setTotal(current => current - 1); setConfirming(null) }
    catch (cause) { setError(cause instanceof Error ? cause.message : tr('মুছতে পারিনি।', 'Could not delete the report.')) }
    finally { setDeleting(null) }
  }

  return <main className="page"><div className="page-heading"><p className="eyebrow">{tr('সংরক্ষিত বিশ্লেষণ', 'Saved analyses')}</p><h1>{tr('ইতিহাস', 'History')}</h1><p className="muted">{tr('আগের রিপোর্ট খুলুন বা প্রয়োজন না থাকলে মুছে ফেলুন। এই ব্রাউজারের তথ্য মুছে ফেললে বা অন্য ডিভাইস ব্যবহার করলে এই ইতিহাস আর পাওয়া যাবে না।', 'Open or delete earlier reports. Clearing this browser’s data or switching devices will remove access to this History.')}</p></div>
    {error && <p role="alert" className="alert error">{displayError(error, language)}</p>}
    {offline ? <><p className="notice" role="status">{tr('অফলাইনে আগে খোলা রিপোর্টের সংরক্ষিত কপি দেখাচ্ছে। নতুন যাচাই করতে সংযোগ প্রয়োজন।', 'Showing saved copies of reports opened earlier. New checks require a connection.')}</p><div className="history-list">{listCachedReports().length ? listCachedReports().map(report => <article className="history-item" key={report.analysis_id}><div><h2>{report.claim || tr('সংরক্ষিত রিপোর্ট', 'Saved report')}</h2><p className="muted small">{tr('সংরক্ষণ:', 'Saved:')} {date(report.saved_at)} · {tr('সূত্র পাওয়া:', 'Sources retrieved:')} {report.retrieved_at ? date(report.retrieved_at) : tr('অজানা', 'Unknown')}</p></div><a className="button secondary" href={`#/analysis/${report.analysis_id}`}>{tr('অফলাইন রিপোর্ট খুলুন', 'Open offline report')}</a></article>) : <p className="panel">{tr('আগে খোলা কোনো রিপোর্ট সংরক্ষিত নেই।', 'No previously opened reports were saved.')}</p>}</div></> : loading ? <p role="status" className="panel">{tr('ইতিহাস আসছে…', 'Loading History…')}</p> : <HistoryList items={items} onDelete={remove} deleting={deleting} confirming={confirming} onConfirm={setConfirming} onCancel={() => setConfirming(null)} />}
    {!offline && !loading && <div className="button-row pagination"><button className="button secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>{tr('আগের পাতা', 'Previous page')}</button><span className="muted small">{total ? `${number(Math.min(offset + 1, total))}–${number(Math.min(offset + 20, total))} / ${number(total)}` : tr('০টি', '0')}</span><button className="button secondary" disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>{tr('পরের পাতা', 'Next page')}</button></div>}
  </main>
}

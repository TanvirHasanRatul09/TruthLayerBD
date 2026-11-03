import { useEffect, useState } from 'react'
import { deleteAnalysis, listAnalyses, type AnalysisRead } from '../api/truthlayer'
import HistoryList from '../components/HistoryList'
import { listCachedReports } from '../pwa/reportCache'

export default function HistoryPage() {
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
    listAnalyses(20, offset).then(page => { if (active) { setItems(page.items); setTotal(page.total); setError(null) } }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : 'ইতিহাস আনা যায়নি।') }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [offset])

  useEffect(() => {
    const update = () => {
      const isOffline = !navigator.onLine
      setOffline(isOffline)
      if (!isOffline) {
        setLoading(true)
        listAnalyses(20, offset).then(page => { setItems(page.items); setTotal(page.total); setError(null) }).catch(cause => setError(cause instanceof Error ? cause.message : 'ইতিহাস আনা যায়নি।')).finally(() => setLoading(false))
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
    catch (cause) { setError(cause instanceof Error ? cause.message : 'মুছতে পারিনি।') }
    finally { setDeleting(null) }
  }

  return <main className="page"><div className="page-heading"><p className="eyebrow">সংরক্ষিত বিশ্লেষণ</p><h1>ইতিহাস</h1><p className="muted">আগের রিপোর্ট খুলুন বা প্রয়োজন না থাকলে মুছে ফেলুন। এই ব্রাউজারের তথ্য মুছে ফেললে বা অন্য ডিভাইস ব্যবহার করলে এই ইতিহাস আর পাওয়া যাবে না।</p></div>
    {error && <p role="alert" className="alert error">{error}</p>}
    {offline ? <><p className="notice" role="status">অফলাইনে আগে খোলা রিপোর্টের সংরক্ষিত কপি দেখাচ্ছে। নতুন যাচাই করতে সংযোগ প্রয়োজন।</p><div className="history-list">{listCachedReports().length ? listCachedReports().map(report => <article className="history-item" key={report.analysis_id}><div><h2>{report.claim || 'সংরক্ষিত রিপোর্ট'}</h2><p className="muted small">সংরক্ষণ: {new Date(report.saved_at).toLocaleString('bn-BD')} · সূত্র পাওয়া: {report.retrieved_at ? new Date(report.retrieved_at).toLocaleString('bn-BD') : 'অজানা'}</p></div><a className="button secondary" href={`#/analysis/${report.analysis_id}`}>অফলাইন রিপোর্ট খুলুন</a></article>) : <p className="panel">আগে খোলা কোনো রিপোর্ট সংরক্ষিত নেই।</p>}</div></> : loading ? <p role="status" className="panel">ইতিহাস আসছে…</p> : <HistoryList items={items} onDelete={remove} deleting={deleting} confirming={confirming} onConfirm={setConfirming} onCancel={() => setConfirming(null)} />}
    {!offline && !loading && <div className="button-row pagination"><button className="button secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>আগের পাতা</button><span className="muted small">{total ? `${Math.min(offset + 1, total)}–${Math.min(offset + 20, total)} / ${total}` : '০টি'}</span><button className="button secondary" disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>পরের পাতা</button></div>}
  </main>
}

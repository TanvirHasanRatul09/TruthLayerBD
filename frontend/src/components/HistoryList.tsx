import type { AnalysisRead } from '../api/truthlayer'

const statusLabels: Record<string, string> = { processing: 'চলছে', awaiting_confirmation: 'নিশ্চিত করা বাকি', completed: 'সম্পন্ন', partial: 'আংশিক', failed: 'ব্যর্থ' }
const coverageLabels: Record<string, string> = { low: 'কম প্রমাণ', medium: 'মাঝারি প্রমাণ', high: 'বেশি প্রমাণ' }

export default function HistoryList({ items, onDelete, deleting, confirming, onConfirm, onCancel }: { items: AnalysisRead[]; onDelete: (id: string) => void; deleting: string | null; confirming: string | null; onConfirm: (id: string) => void; onCancel: () => void }) {
  if (!items.length) return <p className="panel muted">এখনো কোনো বিশ্লেষণ নেই। নতুন ছবি দিয়ে শুরু করুন।</p>
  return <div className="history-list">{items.map(item => <article className="history-item" key={item.analysis_id}>
    <div><p className="eyebrow">{new Date(item.created_at).toLocaleString('bn-BD')}</p><h2>{item.extraction?.claim || item.ocr?.text || 'ছবির বিশ্লেষণ'}</h2><p className="muted small">{statusLabels[item.status] || item.status}{item.verification ? ` · ${coverageLabels[item.verification.evidence_coverage]}` : ''}</p></div>
    <div className="button-row"><a className="button secondary" href={`#/analysis/${item.analysis_id}`}>রিপোর্ট খুলুন</a>{confirming === item.analysis_id ? <span className="delete-confirm"><span>এই বিশ্লেষণ ও ছবিটি মুছবেন?</span><button type="button" className="button danger" disabled={deleting === item.analysis_id} onClick={() => onDelete(item.analysis_id)}>{deleting === item.analysis_id ? 'মুছছে…' : 'হ্যাঁ, মুছুন'}</button><button type="button" className="button secondary" disabled={deleting === item.analysis_id} onClick={onCancel}>বাতিল</button></span> : <button type="button" className="button danger" onClick={() => onConfirm(item.analysis_id)}>মুছুন</button>}</div>
  </article>)}</div>
}

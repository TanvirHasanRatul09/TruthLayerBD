import type { AnalysisRead } from '../api/truthlayer'
import { useI18n } from '../i18n'

const statusLabels: Record<string, string> = { processing: 'চলছে', awaiting_confirmation: 'নিশ্চিত করা বাকি', completed: 'সম্পন্ন', partial: 'আংশিক', failed: 'ব্যর্থ' }
const coverageLabels: Record<string, string> = { low: 'কম প্রমাণ', medium: 'মাঝারি প্রমাণ', high: 'বেশি প্রমাণ' }
const statusLabelsEn: Record<string, string> = { processing: 'Processing', awaiting_confirmation: 'Needs correction', completed: 'Completed', partial: 'Partial', failed: 'Failed' }
const coverageLabelsEn: Record<string, string> = { low: 'Low evidence', medium: 'Medium evidence', high: 'High evidence' }

export default function HistoryList({ items, onDelete, deleting, confirming, onConfirm, onCancel }: { items: AnalysisRead[]; onDelete: (id: string) => void; deleting: string | null; confirming: string | null; onConfirm: (id: string) => void; onCancel: () => void }) {
  const { language, tr, date } = useI18n()
  if (!items.length) return <p className="panel muted">{tr('এখনো কোনো বিশ্লেষণ নেই। নতুন ছবি দিয়ে শুরু করুন।', 'No analyses yet. Start with a new image.')}</p>
  return <div className="history-list">{items.map(item => <article className="history-item" key={item.analysis_id}>
    <div><p className="eyebrow">{date(item.created_at)}</p><h2>{item.extraction?.claim || item.ocr?.text || tr('ছবির বিশ্লেষণ', 'Image analysis')}</h2><p className="muted small">{(language === 'bn' ? statusLabels : statusLabelsEn)[item.status] || item.status}{item.verification ? ` · ${(language === 'bn' ? coverageLabels : coverageLabelsEn)[item.verification.evidence_coverage]}` : ''}</p></div>
    <div className="button-row"><a className="button secondary" href={`#/analysis/${item.analysis_id}`}>{tr('রিপোর্ট খুলুন', 'Open report')}</a>{confirming === item.analysis_id ? <span className="delete-confirm"><span>{tr('এই বিশ্লেষণ ও ছবিটি মুছবেন?', 'Delete this analysis and image?')}</span><button type="button" className="button danger" disabled={deleting === item.analysis_id} onClick={() => onDelete(item.analysis_id)}>{deleting === item.analysis_id ? tr('মুছছে…', 'Deleting…') : tr('হ্যাঁ, মুছুন', 'Yes, delete')}</button><button type="button" className="button secondary" disabled={deleting === item.analysis_id} onClick={onCancel}>{tr('বাতিল', 'Cancel')}</button></span> : <button type="button" className="button danger" onClick={() => onConfirm(item.analysis_id)}>{tr('মুছুন', 'Delete')}</button>}</div>
  </article>)}</div>
}

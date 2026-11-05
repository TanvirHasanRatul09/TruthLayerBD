import type { EvidenceResult } from '../api/truthlayer'
import { useI18n } from '../i18n'

const sourceLabels: Record<string, string> = { official_authority: 'বিষয়টির মূল কর্তৃপক্ষ', government_site: 'সরকারি ওয়েবসাইট (কর্তৃপক্ষ নয়)', claimed_publisher: 'দাবিকৃত প্রকাশক', fact_check: 'ফ্যাক্টচেক সূত্র', independent_news: 'সংবাদমাধ্যম', other: 'অন্যান্য সূত্র' }
const stanceLabels: Record<string, string> = { supports: 'দাবি সমর্থন করে', contradicts: 'দাবির বিরোধী', mentions_but_unclear: 'উল্লেখ আছে, অবস্থান অস্পষ্ট', unrelated: 'প্রাসঙ্গিক নয়', insufficient_content: 'তথ্য অপর্যাপ্ত' }
const sourceLabelsEn: Record<string, string> = { official_authority: 'Primary authority', government_site: 'Government website (not the authority)', claimed_publisher: 'Claimed publisher', fact_check: 'Fact-checking source', independent_news: 'News outlet', other: 'Other source' }
const stanceLabelsEn: Record<string, string> = { supports: 'Supports the claim', contradicts: 'Contradicts the claim', mentions_but_unclear: 'Mentions it; stance unclear', unrelated: 'Irrelevant', insufficient_content: 'Insufficient content' }

export default function EvidenceCard({ item }: { item: EvidenceResult }) {
  const { language, tr, date } = useI18n()
  return <article className="evidence-card">
    <div className="evidence-top"><span className="pill">{(language === 'bn' ? sourceLabels : sourceLabelsEn)[item.source_type] || item.source_type}</span>{item.stance && <span className="pill subtle">{(language === 'bn' ? stanceLabels : stanceLabelsEn)[item.stance] || item.stance}</span>}</div>
    <h4><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title || item.domain} <span aria-hidden="true">↗</span></a></h4>
    <p className="muted small break-anywhere">{item.domain} · {tr('অনুসন্ধানে পাওয়া তারিখ (যাচাই হয়নি):', 'Search-listed date (unverified):')} {item.published_at ? date(item.published_at, { dateStyle: 'medium' }) : tr('তারিখ অজানা', 'Date unknown')} · {tr('পাওয়া:', 'Retrieved:')} {date(item.retrieved_at, { dateStyle: 'medium' })}</p>
    {item.snippet && <p>{item.snippet}</p>}
    {item.quote && <blockquote>“{item.quote}”</blockquote>}
    {item.reason && <p className="small"><strong>{tr('কেন এভাবে চিহ্নিত:', 'Why classified this way:')}</strong> {item.reason}</p>}
    <p className="muted tiny break-anywhere">{tr('প্রমাণ ID:', 'Evidence ID:')} {item.evidence_id}</p>
  </article>
}

import type { EvidenceResult } from '../api/truthlayer'

const sourceLabels: Record<string, string> = { official_authority: 'বিষয়টির মূল কর্তৃপক্ষ', government_site: 'সরকারি ওয়েবসাইট (কর্তৃপক্ষ নয়)', claimed_publisher: 'দাবিকৃত প্রকাশক', fact_check: 'ফ্যাক্টচেক সূত্র', independent_news: 'সংবাদমাধ্যম', other: 'অন্যান্য সূত্র' }
const stanceLabels: Record<string, string> = { supports: 'দাবি সমর্থন করে', contradicts: 'দাবির বিরোধী', mentions_but_unclear: 'উল্লেখ আছে, অবস্থান অস্পষ্ট', unrelated: 'প্রাসঙ্গিক নয়', insufficient_content: 'তথ্য অপর্যাপ্ত' }

export default function EvidenceCard({ item }: { item: EvidenceResult }) {
  return <article className="evidence-card">
    <div className="evidence-top"><span className="pill">{sourceLabels[item.source_type] || item.source_type}</span>{item.stance && <span className="pill subtle">{stanceLabels[item.stance] || item.stance}</span>}</div>
    <h4><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title || item.domain} <span aria-hidden="true">↗</span></a></h4>
    <p className="muted small break-anywhere">{item.domain} · প্রকাশ: {item.published_at ? new Date(item.published_at).toLocaleDateString('bn-BD') : 'তারিখ অজানা'} · পাওয়া: {new Date(item.retrieved_at).toLocaleDateString('bn-BD')}</p>
    {item.snippet && <p>{item.snippet}</p>}
    {item.quote && <blockquote>“{item.quote}”</blockquote>}
    {item.reason && <p className="small"><strong>কেন এভাবে চিহ্নিত:</strong> {item.reason}</p>}
    <p className="muted tiny break-anywhere">প্রমাণ ID: {item.evidence_id}</p>
  </article>
}

import type { EvidenceResult } from '../api/truthlayer'
import type { CachedEvidence } from '../pwa/reportCache'
import EvidenceCard from './EvidenceCard'
import EvidenceGraph from './EvidenceGraph'

type Source = EvidenceResult | CachedEvidence

const groups = [
  { title: 'দাবি সমর্থন করে', matches: (item: Source) => item.stance === 'supports' },
  { title: 'দাবির বিরোধী', matches: (item: Source) => item.stance === 'contradicts' },
  { title: 'অস্পষ্ট বা অপর্যাপ্ত', matches: (item: Source) => item.stance !== 'supports' && item.stance !== 'contradicts' },
]

export default function GroupedEvidence({ claim, evidence }: { claim: string; evidence: Source[] }) {
  return <section className="panel" aria-labelledby="evidence-title">
    <p className="eyebrow">সূত্র ও প্রমাণ</p>
    <h2 id="evidence-title">পাওয়া সূত্র ({evidence.length.toLocaleString('bn-BD')})</h2>
    <p className="muted small">প্রতিটি লিংক খুলে মূল প্রকাশনা দেখুন। অস্পষ্ট সূত্র সিদ্ধান্তের প্রমাণ হিসেবে ধরা হয়নি।</p>
    {evidence.length ? groups.map(group => {
      const items = evidence.filter(group.matches)
      return items.length ? <div className="source-group" key={group.title}><h3>{group.title} <span>({items.length.toLocaleString('bn-BD')})</span></h3>{items.map(item => 'snippet' in item ? <EvidenceCard key={item.evidence_id} item={item} /> : <article className="evidence-card" key={item.evidence_id}><h4><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title || item.domain} ↗</a></h4><p className="muted small">{item.domain} · প্রকাশ: {item.published_at ? new Date(item.published_at).toLocaleDateString('bn-BD') : 'তারিখ অজানা'} · সংরক্ষিত সূত্র · প্রমাণ ID: {item.evidence_id}</p></article>)}</div> : null
    }) : <p className="notice compact">কোনো প্রাসঙ্গিক সূত্র পাওয়া যায়নি। সূত্রের অনুপস্থিতি দাবির বিরোধী প্রমাণ নয়।</p>}
    {evidence.length > 0 && <details className="evidence-detail"><summary>সূত্রের সম্পর্কচিত্র দেখুন</summary><EvidenceGraph claim={claim} evidence={evidence} /></details>}
  </section>
}

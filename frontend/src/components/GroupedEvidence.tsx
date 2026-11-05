import type { EvidenceResult } from '../api/truthlayer'
import type { CachedEvidence } from '../pwa/reportCache'
import EvidenceCard from './EvidenceCard'
import EvidenceGraph from './EvidenceGraph'
import { useI18n } from '../i18n'

type Source = EvidenceResult | CachedEvidence

const groups = [
  { title: 'দাবি সমর্থন করে', english: 'Supports the claim', matches: (item: Source) => item.stance === 'supports' },
  { title: 'দাবির বিরোধী', english: 'Contradicts the claim', matches: (item: Source) => item.stance === 'contradicts' },
  { title: 'অস্পষ্ট বা অপর্যাপ্ত', english: 'Unclear or insufficient', matches: (item: Source) => item.stance !== 'supports' && item.stance !== 'contradicts' },
]

export default function GroupedEvidence({ claim, evidence }: { claim: string; evidence: Source[] }) {
  const { tr, number, date } = useI18n()
  return <section className="panel" aria-labelledby="evidence-title">
    <p className="eyebrow">{tr('সূত্র ও প্রমাণ', 'Sources and evidence')}</p>
    <h2 id="evidence-title">{tr('পাওয়া সূত্র', 'Sources found')} ({number(evidence.length)})</h2>
    <p className="muted small">{tr('প্রতিটি লিংক খুলে মূল প্রকাশনা দেখুন। অস্পষ্ট সূত্র সিদ্ধান্তের প্রমাণ হিসেবে ধরা হয়নি।', 'Open each link to inspect the original publication. Unclear sources were not treated as proof.')}</p>
    {evidence.length ? groups.map(group => {
      const items = evidence.filter(group.matches)
      return items.length ? <div className="source-group" key={group.title}><h3>{tr(group.title, group.english)} <span>({number(items.length)})</span></h3>{items.map(item => 'snippet' in item ? <EvidenceCard key={item.evidence_id} item={item} /> : <article className="evidence-card" key={item.evidence_id}><h4><a href={item.url} target="_blank" rel="noopener noreferrer">{item.title || item.domain} ↗</a></h4><p className="muted small">{item.domain} · {tr('অনুসন্ধানে পাওয়া তারিখ (যাচাই হয়নি):', 'Search-listed date (unverified):')} {item.published_at ? date(item.published_at, { dateStyle: 'medium' }) : tr('তারিখ অজানা', 'Date unknown')} · {tr('সংরক্ষিত সূত্র', 'Saved source')} · {tr('প্রমাণ ID:', 'Evidence ID:')} {item.evidence_id}</p></article>)}</div> : null
    }) : <p className="notice compact">{tr('কোনো প্রাসঙ্গিক সূত্র পাওয়া যায়নি। সূত্রের অনুপস্থিতি দাবির বিরোধী প্রমাণ নয়।', 'No relevant sources were found. Absence of sources is not evidence against the claim.')}</p>}
    {evidence.length > 0 && <details className="evidence-detail"><summary>{tr('সূত্রের সম্পর্কচিত্র দেখুন', 'View evidence graph')}</summary><EvidenceGraph claim={claim} evidence={evidence} /></details>}
  </section>
}

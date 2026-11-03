import type { CachedEvidence } from '../pwa/reportCache'

type GraphEvidence = Pick<CachedEvidence, 'evidence_id' | 'title' | 'url' | 'domain' | 'stance'>
const stanceLabels: Record<string, string> = {
  supports: 'সমর্থন', contradicts: 'বিরোধিতা', mentions_but_unclear: 'উল্লেখ আছে',
  unrelated: 'প্রাসঙ্গিক নয়', insufficient_content: 'তথ্য অপর্যাপ্ত',
}

export default function EvidenceGraph({ claim, evidence }: { claim: string; evidence: GraphEvidence[] }) {
  if (!evidence.length) return null
  return <div className="evidence-graph" aria-label="দাবি ও সূত্রের সম্পর্ক" role="group">
    <div className="graph-claim"><strong>মূল দাবি</strong><span>{claim || 'নিশ্চিত দাবি'}</span></div>
    <div className="graph-branches">{evidence.map(item => <div className={`graph-node graph-${item.stance || 'pending'}`} key={item.evidence_id}>
      <span className="graph-relation">{stanceLabels[item.stance || ''] || 'তুলনা হয়নি'}</span>
      <a href={item.url} target="_blank" rel="noopener noreferrer">{item.title || item.domain}</a>
      <small>{item.evidence_id}</small>
    </div>)}</div>
    <p className="muted small">নিচের তালিকায় একই প্রমাণ ID, লিংক ও বিস্তারিত তথ্য আছে। সম্পর্কের রেখা কোনো রায়ের নিশ্চয়তা বোঝায় না।</p>
  </div>
}

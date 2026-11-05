import type { CachedEvidence } from '../pwa/reportCache'
import { useI18n } from '../i18n'

type GraphEvidence = Pick<CachedEvidence, 'evidence_id' | 'title' | 'url' | 'domain' | 'stance'>
const stanceLabels: Record<string, string> = {
  supports: 'সমর্থন', contradicts: 'বিরোধিতা', mentions_but_unclear: 'উল্লেখ আছে',
  unrelated: 'প্রাসঙ্গিক নয়', insufficient_content: 'তথ্য অপর্যাপ্ত',
}
const stanceLabelsEn: Record<string, string> = { supports: 'Supports', contradicts: 'Contradicts', mentions_but_unclear: 'Mentions', unrelated: 'Irrelevant', insufficient_content: 'Insufficient content' }

export default function EvidenceGraph({ claim, evidence }: { claim: string; evidence: GraphEvidence[] }) {
  const { language, tr } = useI18n()
  if (!evidence.length) return null
  return <div className="evidence-graph" aria-label={tr('দাবি ও সূত্রের সম্পর্ক', 'Claim and source relationships')} role="group">
    <div className="graph-claim"><strong>{tr('মূল দাবি', 'Main claim')}</strong><span>{claim || tr('নিশ্চিত দাবি', 'Confirmed claim')}</span></div>
    <div className="graph-branches">{evidence.map(item => <div className={`graph-node graph-${item.stance || 'pending'}`} key={item.evidence_id}>
      <span className="graph-relation">{(language === 'bn' ? stanceLabels : stanceLabelsEn)[item.stance || ''] || tr('তুলনা হয়নি', 'Not compared')}</span>
      <a href={item.url} target="_blank" rel="noopener noreferrer">{item.title || item.domain}</a>
      <small>{item.evidence_id}</small>
    </div>)}</div>
    <p className="muted small">{tr('নিচের তালিকায় একই প্রমাণ ID, লিংক ও বিস্তারিত তথ্য আছে। সম্পর্কের রেখা কোনো রায়ের নিশ্চয়তা বোঝায় না।', 'The list below contains the same evidence IDs, links, and details. Graph lines do not guarantee a verdict.')}</p>
  </div>
}

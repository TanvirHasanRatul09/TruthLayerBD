import type { EvidenceResult, RetrievalResult, VerificationResult } from '../api/truthlayer'
import type { CachedEvidence } from '../pwa/reportCache'
import { useI18n } from '../i18n'

type Source = EvidenceResult | CachedEvidence

const verdicts: Record<string, [string, string]> = {
  verified: ['সত্য', 'True'], supported: ['সত্য', 'True'], contradicted: ['মিথ্যা', 'False'],
  conflicting: ['যাচাই করা যায়নি', 'Could not verify'], unverified: ['যাচাই করা যায়নি', 'Could not verify'],
  insufficient_evidence: ['যাচাই করা যায়নি', 'Could not verify'],
}

function citedSource(report: VerificationResult, evidence: Source[]) {
  for (const reason of report.reasons) {
    const source = evidence.find(item => item.evidence_id === reason.evidence_id && item.url === reason.url && item.stance === reason.stance)
    const quote = source?.quote?.trim()
    if (!source || !quote || !['supports', 'contradicts'].includes(reason.stance)) continue
    if ('snippet' in source && !((source.title + ' ' + source.snippet).includes(quote))) continue
    return { source, quote }
  }
  return null
}

export default function VerificationSummary({ report, evidence = [], claim, retrieval }: { report: VerificationResult; evidence?: Source[]; claim?: string; retrieval?: RetrievalResult | null; partial?: boolean }) {
  const { tr } = useI18n()
  const citation = citedSource(report, evidence)
  const supported = report.label === 'verified' || report.label === 'supported'
  const contradicted = report.label === 'contradicted'
  const conclusive = (supported || contradicted) && !!citation
  const label = conclusive ? report.label : 'unverified'
  const officialAddress = conclusive && contradicted && citation?.source.source_type === 'official_authority'
    ? /^The official source gives an address in ([A-Za-z -]+), not the claimed place\.$/.exec(report.reasons.find(item => item.evidence_id === citation.source.evidence_id)?.summary || '')?.[1]
    : undefined
  const reason = conclusive
    ? supported
      ? tr('প্রাসঙ্গিক সূত্রের উদ্ধৃতি দাবিটি সরাসরি সমর্থন করে।', 'A relevant cited passage directly supports the claim.')
      : officialAddress
        ? tr('সরকারি সূত্রে এই স্থানটির ঠিকানা ' + officialAddress + '-এ দেওয়া হয়েছে; দাবিতে অন্য শহর বলা হয়েছে।', 'The official source gives this place’s address in ' + officialAddress + '; the claim names a different city.')
        : tr('প্রাসঙ্গিক সূত্রের উদ্ধৃতি দাবিটির সঙ্গে সরাসরি বিরোধী।', 'A relevant cited passage directly contradicts the claim.')
    : retrieval?.status === 'unavailable'
      ? tr('সূত্র অনুসন্ধান ব্যর্থ হয়েছে; তাই এখন সিদ্ধান্ত দেওয়া যাচ্ছে না।', 'Source search failed, so a conclusion is not available yet.')
      : retrieval?.status === 'no_results'
        ? tr('প্রাসঙ্গিক সূত্র পাওয়া যায়নি। সূত্র না পাওয়া মানেই দাবিটি মিথ্যা নয়।', 'No relevant source was found. Missing evidence does not mean the claim is false.')
        : report.label === 'conflicting'
          ? tr('সূত্রগুলো একমত নয়; নিশ্চিত সিদ্ধান্তের জন্য আরও প্রমাণ দরকার।', 'The sources disagree; more evidence is needed for a conclusion.')
          : tr('পাওয়া সূত্রগুলো এই নির্দিষ্ট দাবি নিশ্চিত বা খণ্ডন করার জন্য যথেষ্ট নয়।', 'The available sources do not establish or refute this exact claim.')
  return <section className="panel report quick-report" aria-labelledby="report-title">
    <p className="eyebrow">{tr('এক নজরে ফলাফল', 'At a glance')}</p>
    <h2 id="report-title">{tr(...verdicts[label])}</h2>
    {claim && <p className="report-claim"><strong>{tr('যাচাই করা দাবি:', 'Checked claim:')}</strong> {claim}</p>}
    <p className="report-lead">{reason}</p>
    {conclusive && citation && <div className="key-facts">
      <h3>{supported ? tr('সূত্রে যা পাওয়া গেছে', 'What the source establishes') : tr('সূত্রে পাওয়া সংশোধিত তথ্য', 'What the source says instead')}</h3>
      <p>“{citation.quote}” <a href={citation.source.url} target="_blank" rel="noopener noreferrer">{citation.source.title || citation.source.domain} ↗</a></p>
    </div>}
  </section>
}

export function VerificationDetails({ report, evidence = [], retrieval }: { report: VerificationResult; evidence?: Source[]; retrieval?: RetrievalResult | null }) {
  const { tr, date, number } = useI18n()
  const publisher = report.publisher
  const publisherSource = evidence.find(row => row.evidence_id === publisher?.evidence?.evidence_id && row.url === publisher?.evidence?.url && row.quote?.includes(publisher?.evidence?.value || ''))
  const detailNames: Record<string, [string, string]> = {
    what: ['কী ঘটেছে', 'What happened'], when: ['ঘটনার তারিখ', 'Event date'], where: ['কোথায়', 'Where'], reported_by: ['কে জানিয়েছে', 'Who reported it'],
  }
  const details = report.event_details
  const verifiedDetails = (report.label === 'verified' || report.label === 'supported' ? ['what', 'when', 'where', 'reported_by'] as const : []).flatMap(key => {
    const item = details?.[key]
    const source = evidence.find(row => row.evidence_id === item?.evidence_id && row.url === item?.url)
    if (!item || !source || !item.value || !item.url) return []
    if (key !== 'reported_by' && !source.quote?.includes(item.value)) return []
    return [{ key, item }]
  })
  return <section className="report-technical" aria-label={tr('বিস্তারিত যাচাই', 'Detailed checks')}>
    {publisher?.status !== 'unverified' && publisher?.evidence && publisherSource && <div className="report-facts"><h3>{tr('প্রকাশকের তথ্য', 'Publisher finding')}</h3><p>{publisher.status === 'confirmed_published'
      ? tr((publisher.claimed_name || '') + ' নিজেদের সাইটে দাবিটি প্রকাশ করেছে; এই ছবির উৎস যাচাই হয়নি।', (publisher.claimed_name || '') + ' published the claim on its site; this image’s origin is unverified.')
      : tr((publisher.claimed_name || '') + ' এই ছবি বা পোস্ট নিজেদের নয় বলে জানিয়েছে।', (publisher.claimed_name || '') + ' denied publishing this image or post.')} <a href={publisher.evidence.url} target="_blank" rel="noopener noreferrer">{tr('সূত্র ↗', 'Source ↗')}</a></p></div>}
    {verifiedDetails.length > 0 && <div className="report-facts"><h3>{tr('সূত্রে প্রতিষ্ঠিত ঘটনা', 'Established event details')}</h3><dl>{verifiedDetails.map(({ key, item }) => <div key={key}><dt>{tr(...detailNames[key])}</dt><dd>{item.value} <a href={item.url} target="_blank" rel="noopener noreferrer">{tr('সূত্র ↗', 'Source ↗')}</a></dd></div>)}</dl></div>}
    {retrieval && <p className="small muted">{tr(number(retrieval.query_count) + 'টি অনুসন্ধান চেষ্টা করা হয়েছে; ' + number(evidence.length) + 'টি লিংক পাওয়া গেছে।', number(retrieval.query_count) + ' searches attempted; ' + number(evidence.length) + ' links found.')}</p>}
    {retrieval?.status === 'unavailable' && <p className="report-caveat">{tr('লাইভ সূত্র অনুসন্ধান ব্যর্থ হয়েছে। আবার চেষ্টা করুন।', 'Live source search failed. Try again.')}</p>}
    {retrieval?.status === 'no_results' && <p className="report-caveat">{tr('প্রাসঙ্গিক সূত্র পাওয়া যায়নি।', 'No relevant sources were found.')}</p>}
    {report.comparison_method !== 'gemini' && report.comparison_method !== 'none' && <p className="report-caveat">{tr('AI তুলনা অসম্পূর্ণ ছিল; সীমিত নিয়মভিত্তিক পরীক্ষা ব্যবহার করা হয়েছে।', 'AI comparison was incomplete; a limited rule check was used.')}</p>}
    <p className="small muted">{tr('দাবির সিদ্ধান্ত ছবির সত্যতা বা মূল উৎস প্রমাণ করে না।', 'The claim result does not establish the image’s authenticity or origin.')}</p>
    <p className="coverage">{tr('প্রমাণের পরিধি:', 'Evidence coverage:')} <strong>{report.evidence_coverage === 'high' ? tr('বেশি', 'High') : report.evidence_coverage === 'medium' ? tr('মাঝারি', 'Medium') : tr('কম', 'Low')}</strong></p>
    {report.flags.length > 0 && <p className="notice compact">{tr('অতিরিক্ত চিহ্ন:', 'Additional flags:')} {report.flags.join(', ')}</p>}
    <p className="small muted">{tr('সূত্র অনুসন্ধানের সময়:', 'Sources retrieved:')} {retrieval?.retrieved_at ? date(retrieval.retrieved_at) : tr('অজানা', 'Unknown')}</p>
  </section>
}

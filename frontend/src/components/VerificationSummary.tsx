import type { VerificationResult } from '../api/truthlayer'

const labels: Record<string, string> = { verified: 'সরকারি সূত্রে সমর্থিত', supported: 'একাধিক সূত্রে সমর্থিত', contradicted: 'প্রমাণে বিরোধী', conflicting: 'পরস্পরবিরোধী প্রমাণ', unverified: 'যাচাই নিশ্চিত হয়নি', insufficient_evidence: 'প্রমাণ অপর্যাপ্ত' }
labels.documented_match = 'নথিবদ্ধ ছবির মিল'
const coverage: Record<string, string> = { low: 'কম', medium: 'মাঝারি', high: 'বেশি' }
const layerLabels: Record<string, string> = { claim: 'মূল দাবি', source: 'উৎস পরিচয়', context: 'প্রসঙ্গ', media: 'ছবির সত্যতা' }
const explanations: Record<string, string> = {
  'A direct official source supports the claim.': 'সরাসরি সরকারি সূত্র দাবিটি সমর্থন করে।',
  'Multiple independent credible sources support the claim.': 'একাধিক স্বতন্ত্র নির্ভরযোগ্য সূত্র দাবিটি সমর্থন করে।',
  'Direct official or multiple independent credible sources contradict the claim.': 'সরকারি বা একাধিক স্বতন্ত্র নির্ভরযোগ্য সূত্র দাবির বিরোধিতা করে।',
  'Credible sources both support and contradict the claim.': 'নির্ভরযোগ্য সূত্রগুলোর মধ্যে সমর্থন ও বিরোধিতা দুটোই আছে।',
  'Search results do not establish a consistent conclusion.': 'পাওয়া সূত্র থেকে একমুখী সিদ্ধান্তে পৌঁছানো যায়নি।',
  'Available evidence is insufficient to assess the claim.': 'দাবিটি মূল্যায়নের জন্য যথেষ্ট প্রমাণ নেই।',
  'Source identity was not independently authenticated.': 'উৎসের পরিচয় স্বাধীনভাবে যাচাই করা হয়নি।',
  'Image or event provenance was not independently established.': 'ছবি বা ঘটনার মূল উৎস স্বাধীনভাবে প্রতিষ্ঠিত হয়নি।',
  'Exact image bytes match a reviewed archival record; see its cited date and location below. This does not establish media authenticity.': 'ছবির ফাইলটি পর্যালোচিত পুরোনো রেকর্ডের সঙ্গে হুবহু মিলেছে। নিচে তারিখ, স্থান ও উৎস দেখুন। এতে ছবির সত্যতা প্রমাণ হয় না।',
  'Media authenticity was not tested.': 'ছবির সত্যতা পরীক্ষা করা হয়নি।',
}
const translate = (text: string) => explanations[text] || text

export default function VerificationSummary({ report }: { report: VerificationResult }) {
  return <section className="panel report" aria-labelledby="report-title">
    <p className="eyebrow">যাচাইয়ের সারাংশ</p>
    <h2 id="report-title">{labels[report.label] || report.label}</h2>
    <p>{translate(report.summary)}</p>
    <p className="coverage">প্রমাণের পরিধি: <strong>{coverage[report.evidence_coverage]}</strong> <span>· এটি সত্য হওয়ার সম্ভাবনার শতাংশ নয়</span></p>
    <div className="event-details"><h3>ঘটনা সম্পর্কে যা জানা গেছে</h3><p className="muted small">নিচের তথ্য শুধু পাওয়া সূত্রের লেখা থেকে নেওয়া। প্রকাশিত সাইটের নাম ছবির উৎস বা সত্যতার প্রমাণ নয়।</p><dl>{([['what', 'কী ঘটেছে'], ['when', 'কখন'], ['where', 'কোথায়'], ['reported_by', 'কোন সাইটে প্রকাশিত']] as const).map(([key, label]) => { const detail = report.event_details?.[key]; return <div key={key}><dt>{label}</dt><dd>{detail ? <>{detail.value} <a href={detail.url} target="_blank" rel="noopener noreferrer" aria-label={`${label} তথ্যের সূত্র`}>সূত্র ↗</a></> : 'অজানা'}</dd></div> })}</dl></div>
    <div className="layer-grid">
      {(['claim', 'source', 'context', 'media'] as const).map(key => {
        const layer = report.layers[key]
        return <article className="layer-card" key={key}><h3>{layerLabels[key]}</h3><p className="layer-status">{layer?.status === 'inconclusive' ? 'এখনো নিশ্চিত নয়' : labels[layer?.status] || layer?.status || 'এখনো নিশ্চিত নয়'}</p><p className="small muted">{layer?.summary ? translate(layer.summary) : 'এই স্তরের জন্য যথেষ্ট প্রমাণ নেই।'}</p></article>
      })}
    </div>
    {report.reasons.length > 0 && <div className="reasons"><h3>সিদ্ধান্তের ভিত্তি</h3><ul>{report.reasons.map(reason => <li key={reason.evidence_id}><a href={reason.url} target="_blank" rel="noopener noreferrer">{reason.evidence_id}</a> — {reason.summary}</li>)}</ul></div>}
    {report.flags.length > 0 && <p className="alert">অতিরিক্ত চিহ্ন: {report.flags.join(', ')}</p>}
  </section>
}

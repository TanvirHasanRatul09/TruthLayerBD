import type { CachedReport } from '../pwa/reportCache'
import GroupedEvidence from './GroupedEvidence'
import VerificationSummary from './VerificationSummary'
import LimitationsBanner from './LimitationsBanner'

export default function CachedReportView({ report, onRetry, retrying }: { report: CachedReport; onRetry: () => void; retrying: boolean }) {
  return <main className="page" lang="bn">
    <div className="page-heading"><p className="eyebrow">আগের রিপোর্ট</p><h1>সংরক্ষিত রিপোর্ট</h1></div>
    <div className="notice" role="status"><strong>অফলাইনে সংরক্ষিত কপি</strong><p>সংরক্ষণ: {new Date(report.saved_at).toLocaleString('bn-BD')} · সূত্র পাওয়া: {report.retrieved_at ? new Date(report.retrieved_at).toLocaleString('bn-BD') : 'সময় অজানা'}</p><p>এটি নতুন যাচাই নয়। বর্তমান তথ্য দেখতে ইন্টারনেট সংযোগ দিয়ে আবার খুলুন।</p><button className="button secondary" onClick={onRetry} disabled={retrying || !navigator.onLine}>{retrying ? 'আবার খুলছে…' : 'সংযোগে আবার খুলুন'}</button></div>
    <VerificationSummary report={report.verification} />
    <GroupedEvidence claim={report.claim} evidence={report.evidence} />
    <section className="panel"><p className="eyebrow">যাচাই করা দাবি</p><h2>মূল দাবি</h2><p>{report.claim || 'দাবির লেখা সংরক্ষিত নেই।'}</p></section>
    <LimitationsBanner limitations={report.limitations} fallbacks={report.verification.fallbacks_used} />
    <a className="button secondary" href="#/history">সংরক্ষিত রিপোর্টে ফিরুন</a>
  </main>
}

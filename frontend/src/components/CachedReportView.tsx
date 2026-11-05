import type { CachedReport } from '../pwa/reportCache'
import GroupedEvidence from './GroupedEvidence'
import VerificationSummary, { VerificationDetails } from './VerificationSummary'
import LimitationsBanner from './LimitationsBanner'
import { useI18n } from '../i18n'

export default function CachedReportView({ report, onRetry, retrying }: { report: CachedReport; onRetry: () => void; retrying: boolean }) {
  const { language, tr, date } = useI18n()
  return <main className="page" lang={language}>
    <div className="page-heading"><p className="eyebrow">{tr('আগের রিপোর্ট', 'Earlier report')}</p><h1>{tr('সংরক্ষিত রিপোর্ট', 'Saved report')}</h1></div>
    <div className="notice" role="status"><strong>{tr('অফলাইনে সংরক্ষিত কপি', 'Offline saved copy')}</strong><p>{tr('সংরক্ষণ:', 'Saved:')} {date(report.saved_at)} · {tr('সূত্র পাওয়া:', 'Sources retrieved:')} {report.retrieved_at ? date(report.retrieved_at) : tr('সময় অজানা', 'Time unknown')}</p><p>{tr('এটি নতুন যাচাই নয়। বর্তমান তথ্য দেখতে ইন্টারনেট সংযোগ দিয়ে আবার খুলুন।', 'This is a saved copy, not a new check. Reconnect to view current information.')}</p><button className="button secondary" onClick={onRetry} disabled={retrying || !navigator.onLine}>{retrying ? tr('আবার খুলছে…', 'Reopening…') : tr('সংযোগে আবার খুলুন', 'Reopen online')}</button></div>
    <VerificationSummary report={report.verification} evidence={report.evidence} claim={report.claim} />
    <details className="panel report-evidence"><summary>{tr('সূত্র ও বিস্তারিত দেখুন', 'View evidence and details')}</summary><div className="report-evidence-content"><VerificationDetails report={report.verification} evidence={report.evidence} /><GroupedEvidence claim={report.claim} evidence={report.evidence} /><LimitationsBanner limitations={report.limitations} fallbacks={report.verification.fallbacks_used} /></div></details>
    <section className="panel"><p className="eyebrow">{tr('যাচাই করা দাবি', 'Checked claim')}</p><h2>{tr('মূল দাবি', 'Main claim')}</h2><p>{report.claim || tr('দাবির লেখা সংরক্ষিত নেই।', 'Claim text was not saved.')}</p></section>
    <a className="button secondary" href="#/history">{tr('সংরক্ষিত রিপোর্টে ফিরুন', 'Back to saved reports')}</a>
  </main>
}

import { useEffect, useState } from 'react'
import UploadCard from '../components/UploadCard'
import AnalysisPage from './AnalysisPage'
import HistoryPage from './HistoryPage'
import OfflineBanner from '../components/OfflineBanner'

function route() {
  const hash = window.location.hash
  if (hash === '#/history') return { name: 'history' as const }
  const match = /^#\/analysis\/(an_[a-zA-Z0-9]+)$/.exec(hash)
  if (match) return { name: 'analysis' as const, id: match[1] }
  return { name: 'home' as const }
}

export default function HomePage() {
  const [current, setCurrent] = useState(route)
  useEffect(() => {
    const update = () => setCurrent(route())
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])

  return <div className="app-shell" lang="bn">
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>মূল অংশে যান</a>
    <header className="site-header"><div className="header-inner"><a href="#/" className="brand"><span className="brand-mark">T</span><span>TruthLayer <strong>BD</strong></span></a><nav aria-label="প্রধান নেভিগেশন"><a href="#/" aria-current={current.name === 'home' ? 'page' : undefined}>নতুন যাচাই</a><a href="#/history" aria-current={current.name === 'history' ? 'page' : undefined}>ইতিহাস</a></nav></div></header>
    <OfflineBanner />
    <div id="main-content" tabIndex={-1}>
      {current.name === 'history' ? <HistoryPage /> : current.name === 'analysis' ? <AnalysisPage analysisId={current.id} /> : <main className="page home-page"><div className="hero"><p className="eyebrow">TruthLayer BD · তথ্য যাচাই সহজ করে</p><h1>ছবি দিন।<br /><span>সত্যের সূত্র দেখুন।</span></h1><p>কোনো খবরের পোস্ট বা স্ক্রিনশট আপলোড করুন। আমরা দাবিটি খুঁজে পাওয়া সূত্রের সঙ্গে মিলিয়ে সহজ ভাষায় রিপোর্ট দেখাব। প্রমাণ যথেষ্ট না হলে সেটিও জানাব।</p><a className="button primary hero-cta" href="#upload">ছবি দিয়ে শুরু করুন <span aria-hidden="true">↗</span></a></div><div id="upload"><UploadCard onUploaded={result => { window.location.hash = `#/analysis/${result.analysis_id}` }} /></div><div className="home-steps"><span>০১ · ছবি আপলোড</span><span>০২ · সূত্রের সঙ্গে মিল</span><span>০৩ · পরিষ্কার রিপোর্ট</span></div></main>}
    </div>
    <footer className="site-footer">TruthLayer BD · সূত্র যাচাইয়ে মানুষের বিচারও জরুরি</footer>
  </div>
}

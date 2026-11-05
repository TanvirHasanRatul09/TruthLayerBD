import { useEffect, useState } from 'react'
import UploadCard from '../components/UploadCard'
import AnalysisPage from './AnalysisPage'
import HistoryPage from './HistoryPage'
import OfflineBanner from '../components/OfflineBanner'
import { useI18n } from '../i18n'

function route() {
  const hash = window.location.hash
  if (hash === '#/history') return { name: 'history' as const }
  const match = /^#\/analysis\/(an_[a-zA-Z0-9]+)$/.exec(hash)
  if (match) return { name: 'analysis' as const, id: match[1] }
  return { name: 'home' as const }
}

export default function HomePage() {
  const { language, setLanguage, tr } = useI18n()
  const [current, setCurrent] = useState(route)
  useEffect(() => {
    const update = () => setCurrent(route())
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])
  useEffect(() => {
    const update = () => document.documentElement.classList.toggle('page-hidden', document.hidden)
    update()
    document.addEventListener('visibilitychange', update)
    return () => { document.removeEventListener('visibilitychange', update); document.documentElement.classList.remove('page-hidden') }
  }, [])

  return <div className="app-shell" lang={language}>
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>{tr('মূল অংশে যান', 'Skip to content')}</a>
    <header className="site-header"><div className="header-inner"><a href="#/" className="brand"><span className="brand-mark">T</span><span>TruthLayer <strong>BD</strong></span></a><div className="header-actions"><nav aria-label={tr('প্রধান নেভিগেশন', 'Main navigation')}><a href="#/" aria-current={current.name === 'home' ? 'page' : undefined}>{tr('নতুন যাচাই', 'New check')}</a><a href="#/history" aria-current={current.name === 'history' ? 'page' : undefined}>{tr('ইতিহাস', 'History')}</a></nav><div className="language-switch" role="group" aria-label={tr('ভাষা নির্বাচন', 'Choose language')}><button type="button" lang="bn" aria-pressed={language === 'bn'} onClick={() => setLanguage('bn')}>বাংলা</button><button type="button" lang="en" aria-pressed={language === 'en'} onClick={() => setLanguage('en')}>English</button></div></div></div><div className="buildathon-strip"><span>{tr('এই আয়োজনে নির্মিত', 'Built for')}</span><img src="/official-buildathon-sticker.png" alt="Ostad presents YUNet AIgnite Buildathon 2026 official sticker" /></div></header>
    <OfflineBanner />
    <div id="main-content" tabIndex={-1}>
      {current.name === 'history' ? <HistoryPage /> : current.name === 'analysis' ? <AnalysisPage analysisId={current.id} /> : <main className="page home-page"><div className="hero"><p className="eyebrow">TruthLayer BD</p><h1>{tr('ছবি আপলোড করুন,', 'Upload an image.')}<br /><span>{tr('দাবিটির পেছনের প্রমাণ দেখুন।', 'See the evidence behind its claim.')}</span></h1><p>{tr('TruthLayer BD ছবির মূল দাবি খুঁজে পাওয়া সূত্রের সঙ্গে মিলিয়ে সহজ একটি রিপোর্ট দেয়। প্রমাণ যথেষ্ট না হলে সেটিও জানায়।', 'TruthLayer BD identifies the main claim in an image, compares it with available sources, and gives you a clear report—even when the evidence is insufficient.')}</p><a className="button primary hero-cta" href="#upload">{tr('ছবি আপলোড করুন', 'Upload an image')} <span aria-hidden="true">↗</span></a><div className="hero-scene" aria-hidden="true"><div className="hero-scene-grid" /><div className="hero-scene-source hero-scene-source-left"><span /><span /><span /></div><div className="hero-scene-source hero-scene-source-right"><span /><span /><span /></div><div className="hero-scene-card"><div className="hero-scene-card-top"><span className="hero-scene-dot" /><span className="hero-scene-dot" /><span className="hero-scene-dot" /></div><div className="hero-scene-image"><div className="hero-scene-horizon" /><div className="hero-scene-orb" /></div><div className="hero-scene-line hero-scene-line-long" /><div className="hero-scene-line" /><div className="hero-scene-line hero-scene-line-short" /></div><div className="hero-scene-lens"><span /></div><div className="hero-scene-connection hero-scene-connection-left" /><div className="hero-scene-connection hero-scene-connection-right" /></div></div><div id="upload"><UploadCard onUploaded={result => { window.location.hash = `#/analysis/${result.analysis_id}` }} /></div><div className="home-steps"><span>{tr('০১ · ছবি আপলোড', '01 · Upload image')}</span><span>{tr('০২ · সূত্রের সঙ্গে মিল', '02 · Compare sources')}</span><span>{tr('০৩ · পরিষ্কার রিপোর্ট', '03 · Clear report')}</span></div></main>}
    </div>
    <footer className="site-footer">{tr('TruthLayer BD · সূত্র যাচাইয়ে মানুষের বিচারও জরুরি', 'TruthLayer BD · Your judgment still matters when reviewing sources')}</footer>
  </div>
}

import { useEffect, useState } from 'react'

export default function OfflineBanner() {
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update) }
  }, [])
  if (online) return null
  return <div className="offline-banner" role="alert">ইন্টারনেট সংযোগ নেই। নতুন যাচাই করতে সংযোগ প্রয়োজন। সংযোগ ফিরে এলে আবার চেষ্টা করুন।</div>
}

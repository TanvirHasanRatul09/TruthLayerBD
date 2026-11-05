import { useEffect, useState } from 'react'
import { useI18n } from '../i18n'

export default function OfflineBanner() {
  const { tr } = useI18n()
  const [online, setOnline] = useState(() => navigator.onLine)
  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update) }
  }, [])
  if (online) return null
  return <div className="offline-banner" role="alert">{tr('ইন্টারনেট সংযোগ নেই। নতুন যাচাই করতে সংযোগ প্রয়োজন। সংযোগ ফিরে এলে আবার চেষ্টা করুন।', 'You are offline. New checks require a connection. Reconnect and try again.')}</div>
}

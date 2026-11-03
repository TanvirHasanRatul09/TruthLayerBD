import { useEffect, useState } from 'react'
import { retryOcrWithVision, saveOcrText, type OcrResult } from '../api/truthlayer'

type Props = { analysisId: string; ocr: OcrResult; onConfirmed: () => void; onChanged: () => void; onRetried: () => void }

export default function OcrEditor({ analysisId, ocr, onConfirmed, onChanged, onRetried }: Props) {
  const [text, setText] = useState(ocr.text)
  const [confirmed, setConfirmed] = useState(!ocr.needs_confirmation)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [visionSuggestion, setVisionSuggestion] = useState(false)

  useEffect(() => {
    setText(ocr.text)
    setConfirmed(!ocr.needs_confirmation)
    setError(null)
  }, [analysisId, ocr.text, ocr.needs_confirmation])

  async function retryVision() {
    setRetrying(true)
    setError(null)
    try {
      const result = await retryOcrWithVision(analysisId)
      setText(result.ocr?.text || '')
      setConfirmed(false)
      setVisionSuggestion(true)
      onRetried()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'ছবি আবার পড়া যায়নি।')
    } finally {
      setRetrying(false)
    }
  }

  async function save() {
    if (!text.trim()) return
    setBusy(true)
    setError(null)
    try {
      const saved = await saveOcrText(analysisId, text)
      setText(saved.text)
      setConfirmed(!saved.needs_confirmation)
      if (!saved.needs_confirmation) onConfirmed()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'লেখা সংরক্ষণ করা যায়নি।')
    } finally {
      setBusy(false)
    }
  }

  const lowConfidence = ocr.confidence === null || ocr.confidence < 0.55
  return <section className="panel">
    <p className="eyebrow">{lowConfidence ? 'আপনার সাহায্য প্রয়োজন' : 'ছবি থেকে পাওয়া লেখা'}</p>
    <h2>ছবির লেখাটি দেখুন</h2>
    <p className="muted small">ভুল থাকলে ঠিক করে নিশ্চিত করুন।</p>
    {lowConfidence && <p className="notice compact">লেখা স্পষ্টভাবে পড়া যায়নি। ছবির মূল দাবিটি নিজে লিখে নিশ্চিত করুন।</p>}
    {visionSuggestion && <p className="notice compact">AI ছবিটি আবার পড়েছে। এই লেখায় ভুল থাকতে পারে; মূল ছবির সঙ্গে মিলিয়ে ঠিক করে নিশ্চিত করুন।</p>}
    <label className="field-label" htmlFor="ocr-text">ছবির লেখা</label>
    <textarea id="ocr-text" value={text} onChange={event => { setText(event.target.value); setConfirmed(false); onChanged() }} rows={5} maxLength={4000} />
    <button onClick={save} disabled={!text.trim() || busy} className="button primary full">
      {busy ? 'সংরক্ষণ হচ্ছে…' : 'লেখা নিশ্চিত করুন'}
    </button>
    <button type="button" onClick={retryVision} disabled={busy || retrying} className="button secondary full">{retrying ? 'ছবি আবার পড়ছে…' : 'AI দিয়ে ছবি আবার পড়ুন'}</button>
    {error && <p role="alert" className="alert error">{error}</p>}
    {confirmed && <p role="status" className="notice compact">লেখা নিশ্চিত হয়েছে। যাচাই এগোচ্ছে।</p>}
  </section>
}

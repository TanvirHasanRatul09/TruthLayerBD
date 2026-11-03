import { useEffect, useRef, useState, type ChangeEvent, type ClipboardEvent, type DragEvent } from 'react'
import { uploadAnalysis, type UploadResult } from '../api/truthlayer'

const supportedTypes = new Set(['image/jpeg', 'image/png', 'image/webp'])
const maxBytes = 8 * 1024 * 1024

export default function UploadCard({ onUploaded }: { onUploaded: (result: UploadResult) => void }) {
  const galleryRef = useRef<HTMLInputElement>(null)
  const cameraRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [caption, setCaption] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!file) { setPreview(null); return }
    const url = URL.createObjectURL(file)
    setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [file])

  function selectFile(next: File | null) {
    if (!next) return
    if (!supportedTypes.has(next.type)) { setError('JPEG, PNG বা WebP ছবি বেছে নিন।'); return }
    if (next.size > maxBytes) { setError('ছবির আকার ৮ MB-এর মধ্যে রাখুন।'); return }
    setFile(next)
    setError(null)
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0] ?? null)
    event.target.value = ''
  }

  function onPaste(event: ClipboardEvent<HTMLElement>) {
    const pasted = Array.from(event.clipboardData.files).find(item => supportedTypes.has(item.type))
    if (pasted) { event.preventDefault(); selectFile(pasted) }
  }

  function onDrop(event: DragEvent<HTMLElement>) {
    event.preventDefault()
    selectFile(event.dataTransfer.files[0] ?? null)
  }

  async function startUpload() {
    if (!file) return
    setBusy(true)
    setError(null)
    try { onUploaded(await uploadAnalysis(file, caption)) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'ছবি আপলোড করা যায়নি।') }
    finally { setBusy(false) }
  }

  return <section className="panel" onPaste={onPaste} onDragOver={event => event.preventDefault()} onDrop={onDrop}>
    <p className="eyebrow">নতুন যাচাই</p>
    <h2>একটি পোস্টের ছবি দিন</h2>
    <p className="muted">গ্যালারি, ক্যামেরা, ড্র্যাগ–ড্রপ বা ক্লিপবোর্ড থেকে ছবি দিন। JPEG, PNG, WebP; সর্বোচ্চ ৮ MB।</p>
    <div className="button-row">
      <button type="button" className="button primary" onClick={() => galleryRef.current?.click()}>গ্যালারি থেকে বেছে নিন</button>
      <button type="button" className="button secondary" onClick={() => cameraRef.current?.click()}>ক্যামেরা খুলুন</button>
      <input ref={galleryRef} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={onFileChange} aria-label="গ্যালারি থেকে ছবি বেছে নিন" />
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="sr-only" onChange={onFileChange} aria-label="ক্যামেরা দিয়ে ছবি তুলুন" />
    </div>
    <div className="drop-zone" aria-label="ছবি ড্রপ বা পেস্ট করার জায়গা">এখানে ছবি ড্রপ করুন বা স্ক্রিনশট পেস্ট করুন</div>
    {preview && <div className="preview"><img src={preview} alt="বাছাই করা পোস্টের ছবি" /><button type="button" className="text-button" onClick={() => setFile(null)}>ছবি সরান</button></div>}
    <label className="field-label" htmlFor="caption">ক্যাপশন বা প্রাসঙ্গিক তথ্য (ঐচ্ছিক)</label>
    <textarea id="caption" value={caption} onChange={event => setCaption(event.target.value)} rows={3} maxLength={500} />
    <button type="button" className="button primary full" disabled={!file || busy} onClick={startUpload}>{busy ? 'ছবি পাঠানো ও লেখা পড়া হচ্ছে…' : 'ছবি আপলোড করুন'}</button>
    {error && <p role="alert" className="alert error">{error}</p>}
  </section>
}

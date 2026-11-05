import { useEffect, useRef, useState, type ChangeEvent, type ClipboardEvent, type DragEvent } from 'react'
import { uploadAnalysis, type UploadResult } from '../api/truthlayer'
import { displayError, useI18n } from '../i18n'

const supportedTypes = new Set(['image/jpeg', 'image/png', 'image/webp'])
const maxBytes = 8 * 1024 * 1024

export default function UploadCard({ onUploaded }: { onUploaded: (result: UploadResult) => void }) {
  const { language, tr } = useI18n()
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
    if (!supportedTypes.has(next.type)) { setError(tr('JPEG, PNG বা WebP ছবি বেছে নিন।', 'Choose a JPEG, PNG, or WebP image.')); return }
    if (next.size > maxBytes) { setError(tr('ছবির আকার ৮ MB-এর মধ্যে রাখুন।', 'Keep the image under 8 MB.')); return }
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
    catch (cause) { setError(cause instanceof Error ? cause.message : tr('ছবি আপলোড করা যায়নি।', 'Upload failed.')) }
    finally { setBusy(false) }
  }

  return <section className="panel" onPaste={onPaste} onDragOver={event => event.preventDefault()} onDrop={onDrop}>
    <p className="eyebrow">{tr('নতুন যাচাই', 'New check')}</p>
    <h2>{tr('একটি পোস্টের ছবি দিন', 'Upload a post image')}</h2>
    <p className="muted">{tr('গ্যালারি, ক্যামেরা, ড্র্যাগ–ড্রপ বা ক্লিপবোর্ড থেকে ছবি দিন। JPEG, PNG, WebP; সর্বোচ্চ ৮ MB।', 'Choose an image from your gallery or camera, drag and drop it, or paste it. JPEG, PNG, or WebP; up to 8 MB.')}</p>
    <div className="button-row">
      <button type="button" className="button primary" onClick={() => galleryRef.current?.click()}>{tr('গ্যালারি থেকে বেছে নিন', 'Choose from gallery')}</button>
      <button type="button" className="button secondary" onClick={() => cameraRef.current?.click()}>{tr('ক্যামেরা খুলুন', 'Open camera')}</button>
      <input ref={galleryRef} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={onFileChange} aria-label={tr('গ্যালারি থেকে ছবি বেছে নিন', 'Choose an image from gallery')} />
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" className="sr-only" onChange={onFileChange} aria-label={tr('ক্যামেরা দিয়ে ছবি তুলুন', 'Take a photo with camera')} />
    </div>
    <div className="drop-zone" aria-label={tr('ছবি ড্রপ বা পেস্ট করার জায়গা', 'Image drop or paste area')}>{tr('এখানে ছবি ড্রপ করুন বা স্ক্রিনশট পেস্ট করুন', 'Drop an image here or paste a screenshot')}</div>
    {preview && <div className="preview"><img src={preview} alt={tr('বাছাই করা পোস্টের ছবি', 'Selected post image')} /><button type="button" className="text-button" onClick={() => setFile(null)}>{tr('ছবি সরান', 'Remove image')}</button></div>}
    <label className="field-label" htmlFor="caption">{tr('ক্যাপশন বা প্রাসঙ্গিক তথ্য (ঐচ্ছিক)', 'Caption or context (optional)')}</label>
    <textarea id="caption" value={caption} onChange={event => setCaption(event.target.value)} rows={3} maxLength={500} />
    <button type="button" className="button primary full" disabled={!file || busy} onClick={startUpload}>{busy ? tr('ছবি পাঠানো ও লেখা পড়া হচ্ছে…', 'Uploading and reading the image…') : tr('ছবি আপলোড করুন', 'Upload image')}</button>
    {error && <p role="alert" className="alert error">{displayError(error, language)}</p>}
  </section>
}

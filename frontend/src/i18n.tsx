import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Language = 'bn' | 'en'
const KEY = 'truthlayer-language'
const initialLanguage = (): Language => {
  try { return localStorage.getItem(KEY) === 'en' ? 'en' : 'bn' } catch { return 'bn' }
}

export function currentLanguage(): Language { return initialLanguage() }

type I18n = {
  language: Language
  setLanguage: (language: Language) => void
  tr: (bangla: string, english: string) => string
  date: (value: string, options?: Intl.DateTimeFormatOptions) => string
  number: (value: number) => string
}

const fallback: I18n = {
  language: 'bn', setLanguage: () => {}, tr: bangla => bangla,
  date: value => new Date(value).toLocaleString('bn-BD'),
  number: value => value.toLocaleString('bn-BD'),
}
const Context = createContext<I18n>(fallback)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(initialLanguage)
  useEffect(() => {
    document.documentElement.lang = language
    try { localStorage.setItem(KEY, language) } catch { /* The switch still works for this visit. */ }
  }, [language])
  const value = useMemo<I18n>(() => ({
    language, setLanguage,
    tr: (bangla, english) => language === 'bn' ? bangla : english,
    date: (value, options) => new Date(value).toLocaleString(language === 'bn' ? 'bn-BD' : 'en-US', options),
    number: value => value.toLocaleString(language === 'bn' ? 'bn-BD' : 'en-US'),
  }), [language])
  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useI18n(): I18n { return useContext(Context) }

const errors: Record<string, string> = {
  'ইন্টারনেট সংযোগ নেই। সংযোগ ফিরে এলে আবার চেষ্টা করুন।': 'You are offline. Reconnect and try again.',
  'ছবি পাঠানো যায়নি। সংযোগ পরীক্ষা করে আবার চেষ্টা করুন; বাছাই করা ছবিটি এখানেই আছে।': 'Could not upload the image. Check your connection and try again; your selected image is still here.',
  'ছবির ফাইলটি খালি। অন্য ছবি বেছে নিন।': 'The image file is empty. Choose another image.',
  'ছবির আকার ৮ MB-এর মধ্যে রাখুন।': 'Keep the image under 8 MB.',
  'JPEG, PNG বা WebP ছবি বেছে নিন। ফাইলের ধরন ও ভেতরের তথ্য মিলতে হবে।': 'Choose a valid JPEG, PNG, or WebP image.',
  'ছবিটি খোলা যাচ্ছে না। অন্য ছবি বেছে নিন।': 'This image cannot be opened. Choose another image.',
  'অল্প সময়ে অনেক ছবি পাঠানো হয়েছে। কিছুক্ষণ পরে আবার চেষ্টা করুন; বাছাই করা ছবিটি এখানেই আছে।': 'Too many uploads. Wait a moment and try again; your selected image is still here.',
  'ছবি আপলোড করা যায়নি। আবার চেষ্টা করুন; বাছাই করা ছবিটি এখানেই আছে।': 'Upload failed. Try again; your selected image is still here.',
  'Analysis not found.': 'Report not found in this browser.',
  'Image not found.': 'Image not found.',
  'Service is busy. Try again shortly.': 'The service is busy. Try again shortly.',
  'Too many requests. Try again shortly.': 'Too many requests. Try again shortly.',
  'Invalid request data.': 'Invalid request data.',
  'AI could not read this image. Please enter the text yourself.': 'AI could not read this image. Enter the claim yourself.',
  'AI image reading is not configured.': 'AI image reading is unavailable.',
}

export function displayError(message: string, language: Language): string {
  if (language === 'bn') return message
  return errors[message] || message
}

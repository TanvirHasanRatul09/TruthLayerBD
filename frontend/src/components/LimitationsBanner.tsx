import { useI18n } from '../i18n'

const translations: Record<string, string> = {
  'Live web retrieval is unavailable because Tavily is not configured.': 'লাইভ ওয়েব অনুসন্ধান পাওয়া যাচ্ছে না: Tavily কনফিগার করা নেই।',
  'Live web retrieval failed; no current evidence was obtained.': 'লাইভ ওয়েব অনুসন্ধান ব্যর্থ হয়েছে; বর্তমান কোনো সূত্র পাওয়া যায়নি।',
  'Some live searches failed; results may be incomplete.': 'কিছু অনুসন্ধান ব্যর্থ হয়েছে; সূত্র অসম্পূর্ণ হতে পারে।',
  'No relevant search results were returned; absence is not proof.': 'প্রাসঙ্গিক ফল পাওয়া যায়নি; ফল না পাওয়া দাবিটি মিথ্যা প্রমাণ করে না।',
  'Evidence has not yet been compared or scored.': 'সূত্রগুলো এখনো দাবির সঙ্গে তুলনা করা হয়নি।',
  'Only search result titles and snippets were compared; full pages and image provenance were not checked.': 'শুধু সার্চ ফলের শিরোনাম ও সংক্ষিপ্ত লেখা তুলনা করা হয়েছে; পুরো পৃষ্ঠা বা ছবির উৎস যাচাই করা হয়নি।',
  'Some or all evidence comparisons used conservative rule fallback.': 'কিছু বা সব সূত্রে সীমিত নিয়মভিত্তিক তুলনা ব্যবহার হয়েছে।',
  'Search without confirmation does not establish that the claim is false.': 'নিশ্চিত প্রমাণ না পাওয়া মানে দাবিটি মিথ্যা প্রমাণিত নয়।',
  'Rule comparison cannot establish support or contradiction.': 'নিয়মভিত্তিক তুলনা দাবি সমর্থন বা বিরোধিতা নিশ্চিত করতে পারে না।',
  'Undated, outdated, proposed, or price-mismatched snippets cannot establish a current price.': 'তারিখহীন, পুরোনো, প্রস্তাবিত বা ভিন্ন অঙ্কের সূত্র বর্তমান দাম নিশ্চিত করতে পারে না।',
  'A country-specific claim needs a cited passage naming that country.': 'দেশ নির্দিষ্ট দাবির জন্য উদ্ধৃত অংশে সেই দেশের নাম স্পষ্ট থাকতে হবে।',
  'This saved report predates the improved source and date checks. Rerun verification.': 'এই পুরোনো রিপোর্টে নতুন উৎস ও তারিখ যাচাই নেই। আবার যাচাই করুন।',
  'This saved report predates current evidence checks. Rerun verification.': 'এই পুরোনো রিপোর্টে বর্তমান সূত্র যাচাই নেই। আবার যাচাই করুন।',
  'Unrelated search results were excluded; no claim-specific source was found. Correct the claim if needed, then search again.': 'অপ্রাসঙ্গিক সার্চ ফল বাদ দেওয়া হয়েছে; দাবিটি নিয়ে নির্দিষ্ট কোনো সূত্র পাওয়া যায়নি। প্রয়োজনে দাবির লেখা ঠিক করে আবার খুঁজুন।',
  'Some unrelated search results were excluded.': 'কিছু অপ্রাসঙ্গিক সার্চ ফল বাদ দেওয়া হয়েছে।',
}

export default function LimitationsBanner({ limitations, fallbacks = [] }: { limitations: string[]; fallbacks?: string[] }) {
  const { language, tr } = useI18n()
  const items = [...new Set([...limitations, ...fallbacks])]
  if (!items.length) return null
  return <aside className="notice" aria-label={tr('সীমাবদ্ধতা', 'Limitations')}><h3>{tr('যা জানা যায়নি', 'What remains unknown')}</h3><ul>{items.map(item => <li key={item}>{language === 'bn' ? translations[item] || item : item}</li>)}</ul></aside>
}

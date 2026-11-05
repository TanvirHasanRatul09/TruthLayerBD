# Evidence-first verification run — 5 November 2026

## Method

All 23 category cards (C01–C23) and five manual cards (M01–M05) went through the actual FastAPI upload, OCR, claim extraction/correction, automatic retrieval, comparison, and report endpoints. `backend/scripts/evaluate_categories.py --set all` used temporary storage and live Tavily/Gemini providers. No provider answers were embedded in these cards. The six Apollo cards C03, C04, C19, C21, C22, and M03 were rerun after the destination-matching fix. The results below use the latest run for each card. Raw run data is kept locally in ignored `category-evaluation-v8-live.json` and `category-evaluation-v9-landing-rerun.json`.

The generated cards contain test labels and footers. In all 28 API runs, the extracted claim required the one correction step before analysis; these runs establish the corrected-claim flow, not reliable automatic extraction from every news image. The UI verdicts below translate `verified` to **True**, `contradicted` to **False**, and `unverified`/`insufficient_evidence` to **Could not verify**. The `expected_claim` in the manifests is a reference finding, not the observed app verdict.

## Live-provider outcomes

| Category / difficulty | True | False | Could not verify |
| --- | --- | --- | --- |
| Easy (11) | C01 | C05, M05 | C03, C06, C11, C18, C19, C20, C21, M01 |
| Medium (9) | C09 | C22 | C04, C07, C08, C12, C16, C23, M03 |
| Hard (8) | — | — | C02, C10, C13, C14, C15, C17, M02, M04 |
| **Total (28)** | **2** | **3** | **23** |

Categories overlap. The two True cases concern UNESCO inscription and a WHO emergency decision. The three False cases concern the Eiffel Tower's location (two cards) and Michael Collins's Apollo 11 role. Exact dates, prices, mixed claims, and publisher-attribution examples mostly remained unresolved. The unverified outcomes are not False and should not be presented as factual refutations.

For the five conclusive reports, the decisive citation was checked against the named subject and fact: C01 cited [UNESCO's Bangladesh Sundarbans decision](https://whc.unesco.org/en/decisions/5700); C09 cited [WHO on the end of the global COVID-19 emergency](https://www.who.int/europe/emergencies/situations/covid-19); C05 and M05 cited [the Eiffel Tower's official Paris address](https://www.toureiffel.paris/en/access-map); C22 cited [NASA's account of Collins remaining in lunar orbit](https://www.nasa.gov/former-astronaut-michael-collins). India's separately listed [1987 Sundarbans property](https://whc.unesco.org/en/list/452/) was not accepted as proof for Bangladesh's 1987 claim. No generated card can establish the origin or authenticity of its depicted image or confirm that a named publisher posted it.

## Failure, fix, and retest

C19 initially produced an incorrect True result. Reproduce by uploading C19, correcting the extracted claim to its manifest claim, and examining the NASA citation: the cited sentence said Apollo 11 **landed back on Earth** in 1969, while the claim concerned landing **on the Moon**. The comparator matched a landing verb and year but failed to require the claimed destination. The general movement/arrival guard now requires that a cited passage name the claimed destination before it can support or contradict a landing, walking, or touchdown claim. A regression test covers this mismatch. After rerunning the six Apollo cards with live providers, C19 changed to Could not verify; C22 still returned False with a NASA citation about Collins's actual role. C03, C04, C21, and M03 remained Could not verify in that run. Provider variability and insufficient passages explain unresolved cases; the fix does not encode Apollo-specific answers.

The production frontend previously honored an ignored local development API URL during build, which could send a deployed frontend to a developer's localhost. The API client now uses same-origin `/api/v1` in production. A frontend regression test covers a build with a development URL present.

## Browser checks and fixtures

The real browser was checked at desktop and approximately 390 px mobile width in বাংলা and English. The live-provider Eiffel report showed False with an official Eiffel link. A separate provider-disabled browser run showed a one-step OCR correction, progress, an honest provider-failure result, History/reopen, and a claim rerun that removed the previous report while processing. A separate test-only fixture backend exercised no results, mixed evidence, False, and True. These fixture reports use `.example` URLs and verify UI behavior only; they are **not live factual verification**. Expanded evidence, language switching, mobile overflow, and rerun clearing were checked. The fixture no-results and mixed reports displayed Could not verify. After rerun, the old verdict and citation were absent before the new report appeared.

## Automated checks and limitations

- Backend: **110 passed** (one dependency deprecation warning).
- Frontend: **22 passed**.
- Production frontend build: **passed**; JavaScript 283.49 kB (84.95 kB gzip), CSS 27.07 kB (7.59 kB gzip).

Live Gemini calls intermittently returned server errors, timeouts, or invalid output; retrieval sometimes supplied passages too weak to decide an exact claim. The remaining 23 Could not verify cases include expected true, expected false, mixed, and deliberately unsupported claims. This is a conservative result, not a measure of general news-verification accuracy. The generated cards' text also forced correction, so fully automatic OCR/extraction on diverse real news images remains unproven. Browser fixtures validate transitions and layout, while factual findings come only from the live runs and cited primary sources.

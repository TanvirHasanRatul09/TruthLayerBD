# Browser test cases

These four images are **test cards created for this project**, not real social posts. Upload one at a time at `http://localhost:5173`. The claims are intentionally simple so OCR errors and irrelevant search results are easy to spot. The cards themselves are not evidence.

## Before starting

1. Check `http://localhost:8000/api/v1/health` returns `status: ok`. For live evidence checks, `providers.tavily.configured` should be `true`; Gemini improves claim extraction and source comparison when configured.
2. Open the frontend, choose an image, check its preview, and upload it. The app reads the image and continues through search and comparison automatically.
3. If the app asks for a correction, replace the draft with the **main claim only** and click **দাবি দিয়ে যাচাই চালিয়ে যান**. The test cards contain a “TEST CLAIM” header that should not be part of the claim.
4. Read the report and open each cited source. Check that the title/snippet refers to the *same* place, event, and date. A source merely mentioning the same keyword is not enough. The optional graph is below the source groups.

| Image | Claim to confirm | Reference | What a sound result looks like |
|---|---|---|---|
| `01-sundarbans-1997-supported.png` | UNESCO listed the Sundarbans in Bangladesh as a World Heritage Site in 1997. | [UNESCO Bangladesh site 798](https://whc.unesco.org/en/list/798/) | Relevant UNESCO evidence supports 1997. A supported/verified conclusion is reasonable only if a cited source states this fact. |
| `02-sundarbans-1987-contradicted.png` | UNESCO listed the Sundarbans in Bangladesh as a World Heritage Site in 1987. | [UNESCO Bangladesh site 798](https://whc.unesco.org/en/list/798/); [UNESCO India site 452](https://whc.unesco.org/en/list/452/) | The Bangladesh listing is **1997**; 1987 belongs to the adjoining Indian site. The app must not treat the India result as support for the Bangladesh claim. |
| `03-apollo-1972-contradicted.png` | Apollo 11 first landed humans on the Moon in 1972. | [NASA Apollo 11](https://www.nasa.gov/mission/apollo-11/) | NASA gives **20 July 1969**. If a relevant source is found, 1972 should not be accepted as supporting evidence. |
| `04-untraceable-claim.png` | A blue whale was seen in Dhaka city lake on 12 February 2032. | No reference; deliberately untraceable future claim. | The app should say it lacks sufficient evidence. It must not invent a source or treat missing results as proof of the event. |

**Verdict labels are not guaranteed.** Live search may return no suitable source, providers may be disabled, and the app compares search snippets rather than full articles. `insufficient_evidence` is acceptable for any case when retrieval fails or the sources do not establish the claim. For the last case, a future date may be flagged separately; that is also acceptable if the app still avoids an invented factual verdict.

## Workflow checks

- **OCR/claim correction:** When asked to correct an unclear card, enter the main claim in the single correction box. On a completed report, use **দাবি ঠিক করে আবার যাচাই করুন**, change one digit, and verify the old report is replaced after automatic search and comparison. Restore the intended claim afterward.
- **Irrelevant links:** Search results about India’s Sundarbans must not be shown as proof of the Bangladesh listing. Likewise, generic Moon or whale pages do not establish the exact claim.
- **History:** Complete a report, visit History, reopen it, and check the image, claim, evidence links, and decision are preserved.
- **Offline:** Open a completed report online, switch the browser offline, then reopen it from History. It should show a dated cached report; new searches and uploads should not run offline.
- **Delete:** Delete only a test analysis, then check that it disappears from History. Do not use a real upload for this check.
- **Upload validation:** Try a text file and an image larger than 8 MB. The form should reject each with a useful message. Do not use the four cards for this check; they are valid PNGs.
- **Refresh during processing:** Refresh while a provider request is running. The page should wait for the saved server result, then continue; it must not show an old report as the new conclusion. If a request stalls, use the retry action.
- **Provider failure:** With a key absent or a provider unavailable, the app should request one claim correction or show a partial/insufficient report with a limitation. It must not invent a citation.
- **Mobile:** At about 390 px viewport width, check upload, the correction box, buttons, evidence cards, history, and report without horizontal scrolling.

Record for each case: OCR text, confirmed claim, number of relevant sources, source URLs, final label, layer statuses, provider configuration, and any error. “Unknown” source/context/media layers can be correct even when a claim is supported, because a text test card does not prove publisher identity or image provenance.

The automated `backend/tests/test_end_to_end_cards.py` suite runs these four images through the API with clearly synthetic source fixtures. It checks the expected supported, contradicted, and insufficient paths without claiming that provider responses are stable. A live browser run can legitimately end with insufficient evidence when current search fails or returns no relevant source.

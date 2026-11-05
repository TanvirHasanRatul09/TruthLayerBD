# Claim-category evaluation set (phase 1)

This is a **source-backed test plan, not a test-results report**. The 23 PNGs in `category-cards/` are locally generated text cards, clearly marked as synthetic. They are not screenshots of the cited organizations and cannot prove image origin, publisher attribution, or manipulation. `category-evaluation.json` is the machine-readable case list. Regenerate the cards with `backend/.venv/Scripts/python.exe docs/manual-test-cases/generate_category_cards.py` from the repository root on Windows.

The local Pillow build lacks complex Bangla shaping support. A few Bangla glyph combinations in these generated cards show dotted-circle artifacts, which makes those cards useful as OCR stress cases but unsuitable as polished Bangla news mockups. Check the expected claim in the JSON if OCR struggles. This is a test-asset limitation, not a claim that the app handled the card correctly.

## Claim categories

| Category | What must match | Easy | Medium | Hard |
|---|---|---|---|---|
| Event occurrence | Same event, not merely the same topic | C03 | C08 | C15 |
| Date | Event date versus article publication date | C01 | C04 | C02 |
| Location | Original subject and exact city and country | C05 | C23 | C02 |
| Person or organization | Exact person, role, and institution | C21 | C22 | C17 |
| Numbers and prices | Unit, product, effective period, total | C11 | C12 | C13 |
| Announcement or policy | Decision versus implication or later effect | C18 | C09 | C10 |
| Quoted or attributed statement | Speaker, wording, and scope | C20 | C09 | C17 |
| Publisher attribution | Publisher's own claim versus origin of this image | C19 | C16 | C14 |
| Miscaption or image authenticity | Claim context versus actual image provenance | C05 | C22 | C14/C15 |

Some IDs appear in several categories because real news claims combine them. Difficulty reflects disambiguation, not certainty. The *publisher* and *image* rows test separation: even an easy claim does not establish who made this locally generated card. These synthetic cards **cannot test visual manipulation detection**. A separate set of permission-cleared original and altered photos would be needed for that.

## Source-backed cases

The exact claim, expected claim finding, people, place, date, and source relevance are recorded per ID in `category-evaluation.json`. The key references were checked against the organizations' own pages on 5 November 2026:

| IDs | Primary source | Expected distinction |
|---|---|---|
| C01, C02, C14 | [UNESCO Bangladesh property](https://whc.unesco.org/en/list/798/) and [distinct India property](https://whc.unesco.org/en/list/452/) | Bangladesh 1997; India 1987. The Indian record cannot support a Bangladesh 1987 claim. |
| C03, C04, C19, C21, C22 | [NASA Apollo program](https://nssdc.gsfc.nasa.gov/planetary/lunar/apollo.html), [Apollo 11 mission](https://www.nasa.gov/mission/apollo-11/), [NASA crew explanation](https://www.nasa.gov/learning-resources/for-kids-and-students/what-was-the-apollo-program-grades-5-8/) | Apollo 11 landed in 1969; Armstrong and Aldrin walked, Collins stayed in orbit. A 1972 mission is different. |
| C05, C23 | [Eiffel Tower official access page](https://www.toureiffel.paris/en/access-map) | Original Eiffel Tower is in Paris, France; Berlin replicas or TV towers are different subjects. C23 checks the country even though its city is correct. |
| C06, C07 | [UN member-state list](https://www.un.org/en/about-us/member-states) | Bangladesh was admitted 17 September 1974, not 1972. |
| C08–C10, C16, C17, C20 | [WHO COVID chronology](https://www.who.int/europe/emergencies/situations/covid-19), [WHO Director-General remarks](https://www.who.int/news-room/speeches/item/who-director-general-s-opening-remarks-at-the-media-briefing---5-may-2023), [WHO press transcript](https://www.who.int/publications/m/item/virtual-press-conference-on-covid-19-and-other-global-health-issues-transcript---5-may-2023) | Pandemic characterization: 11 March 2020. Global emergency ended 5 May 2023; that did not mean COVID disappeared or that WHO certified the image. |
| C11, C12 | [BERC monthly LPG table](https://berc.org.bd/pages/static-pages/6922df94933eb65569e22e27) | December 2025, 12 kg, Tk 1,253. Check all three dimensions before a price verdict. The page's later update date is not the price period. |
| C13, C18 | [UNESCO International Mother Language Day](https://www.unesco.org/en/days/mother-language) | Approved in 1999; observed worldwide since 2000; held on 21 February. C13 contains one true and one false clause. |
| C15 | No reference | Deliberately unsupported future event. Expected finding is insufficient evidence, not false. |

## Scoring rules for the next phase

- `supported`, `verified`, and `contradicted` are **expected only when the run actually retrieves a relevant cited passage**. If a provider fails or yields no usable evidence, score the run as an evidence-availability failure; do not force the benchmark verdict.
- `mixed` and `contradicted_with_related_true_fact` are evaluation descriptions, not required API labels. Score the claim's clauses and the explanation separately. For C10, the emergency ending is true while “virus disappeared” is false.
- C14, C16, and C19 may establish that an organization published a *claim* on its own site. The test card was generated here, so the app must never claim that the organization published *this image*. A Jamuna TV label on C14 is only a claimed identity.
- Record OCR text, corrected claim, search/provider status, cited URL and passage, verdict, event date, publication date, publisher finding, and image-authenticity status for each run. A publication date or publisher status that the source does not establish remains unknown.
- Bangla cards test OCR and claim extraction in Bangla. English-language source passages may still be needed for comparison. Do not translate source titles or quotations inside citations.

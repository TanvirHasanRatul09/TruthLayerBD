# Dataset import and rights record

The app loads only local `*.jsonl` files in this directory. No third-party dataset or image is bundled. Each line is a JSON object with:

`dataset_id`, `record_id`, `source_url`, `license`, `attribution`, and optionally `claim_text`, `original_label`, `image_sha256`, `original_event_date`, `original_location`, `provenance_url`, `provenance_reviewed`.

Before importing a dataset, record its publisher, source URL, terms URL, allowed use, attribution requirements, download date and reviewer in a separate file here. Do not import source images or bulk text unless those terms permit it. The app retains only supplied metadata and links. A `provenance_reviewed: true` value means a human checked that the cited source independently documents the exact image and the event date/location. Without that review, even an exact byte match does not expose an original-incident finding.

The original dataset label is displayed with attribution and never changes the current claim verdict. Text matching uses a token Jaccard threshold of 0.78 with at least four tokens on each side. Image matching uses exact SHA-256 bytes, so crops and recompressed copies will not match. A missing match proves nothing.

## Source review

Google's Fact Check Tools API can search historical ClaimReview records but requires an API key and is subject to its API terms: https://developers.google.com/fact-check/tools/api/ . It is **not imported or redistributed** by this build. Wikimedia Commons files have item-specific licenses and attribution requirements; no Commons files are imported: https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia . Review each file's license before any future use.

This build has no approved real-world corpus. The synthetic held-out fixtures in `tests/fixtures/dataset_eval.jsonl` are project-created test data, not a real-world accuracy study.

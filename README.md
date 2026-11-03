# TruthLayer BD

TruthLayer BD is a React/Vite and FastAPI app for checking claims in news cards and screenshots. It keeps SQLite history, reads Bangla/English text with EasyOCR, uses Gemini for bounded claim extraction and source comparison when available, retrieves current links with Tavily, and shows a cited report. The root-level `TruthLayer-BD` guide is the product specification.

## Run frontend and backend locally

These commands use **PowerShell on Windows**. Install Python 3.11 or newer and Node.js with npm first. Run the commands from the repository root (`D:\ostad\TruthLayerBD`). Keep two terminals open: one for the backend and one for the frontend.

### One-time setup

In the **backend terminal**:

```powershell
cd D:\ostad\TruthLayerBD\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

In the **frontend terminal**:

```powershell
cd D:\ostad\TruthLayerBD\frontend
npm install
Copy-Item .env.example .env
```

The example environment files already connect the frontend at port **5173** to the backend at port **8000**. To enable Gemini or Tavily, add the respective API keys to `backend/.env`. Leave the keys blank to run without those providers. Do not put provider keys in `frontend/.env` or any `VITE_*` variable.

### Start the app each time

In the **backend terminal**:

```powershell
cd D:\ostad\TruthLayerBD\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In the **frontend terminal**, while the backend stays running:

```powershell
cd D:\ostad\TruthLayerBD\frontend
npm run dev
```

Open **http://localhost:5173** in your browser. To check the backend separately, open **http://localhost:8000/api/v1/health**. Stop either server with `Ctrl+C` in its terminal. You only need to repeat the one-time setup after changing dependencies or recreating the environment.

On the first OCR run, EasyOCR downloads its Bangla/English model files into `backend/data/models/`. This can take several minutes. If the models are unavailable, the app keeps the image and asks for the main claim.

### Upload to report

1. Open the welcome page and choose one JPEG, PNG, or WebP image (up to 8 MB). A caption is optional. Click **ছবি আপলোড করুন**.
2. The progress page automatically reads the image, identifies the main claim, searches for sources, compares them, and builds a report. If the text or claim is unclear, enter the main claim once and click **দাবি দিয়ে যাচাই চালিয়ে যান**. The rest continues automatically. Refreshing during a server request waits for its saved result; if it stalls, use **আবার চেষ্টা করুন**.
3. Read the conclusion, event details, grouped source links, separate claim/source/context/image statuses, and limitations. Dates and places without source support remain unknown. **দাবি ঠিক করে আবার যাচাই করুন** is available on the report.

Gemini and Tavily keys stay on the backend. If a provider is unavailable or times out, the app offers manual claim correction or an honest partial report. A search result, logo, or model response does not establish image authenticity or publisher identity. History reopens or deletes analyses.

### If configured providers still fail

Check `/api/v1/health` to confirm the keys are configured, then run the backend from a normal PowerShell session with outbound HTTPS access. A backend launched inside a restricted test environment may be unable to open provider connections even when the keys are valid. Restart the backend after changing its environment. The app records `NETWORK_ERROR` for connection failures and keeps a partial report instead of inventing evidence. If the primary Gemini model is unavailable, the configured fallback is tried automatically; set `GEMINI_MODEL` in `backend/.env` to a model your account can access if the primary repeatedly returns an error. Never place provider keys in frontend settings.

The production frontend includes an installable PWA manifest and service worker. Serve it over HTTPS (or localhost) for installation. Previously opened reports are kept locally, up to ten small snapshots, and can be reopened offline with their saved and source-retrieval times. The graph and source list show the same evidence IDs. New uploads, searches and verdicts require a connection. The offline copy omits the uploaded image and raw provider responses; it is replaced with the live report on reconnection.

### Historical dataset matching

The analysis page can search locally imported historical claim and image records. Place reviewed JSONL metadata in `backend/data/datasets/`; use only records with permission to reuse their metadata and attribution. No real-world corpus is bundled. A related historical claim is shown with its original label and source, but does not change the current verdict. An original date or location is shown only for an exact image-file match with a reviewed provenance link. Cropped or recompressed copies will not match. To inspect the synthetic matching evaluation, run `.\.venv\Scripts\python.exe -m scripts.evaluate_dataset` from `backend/`.

## Verification

The four PNG cards in `docs/manual-test-cases/` cover the complete upload flow. The local Markdown guides are excluded from Git.

From `backend/`, run `.\.venv\Scripts\python.exe -m pytest`. This includes deterministic end-to-end tests using all four browser cards and synthetic provider responses. From `frontend/`, run `npm run build`, then `node --test tests/phase8.test.mjs tests/phase9.test.mjs tests/phase11.test.mjs`. Live verdicts depend on provider access and the sources returned at test time.


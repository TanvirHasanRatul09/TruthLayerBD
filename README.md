# TruthLayer BD

TruthLayer BD helps people check a claim in a news image. Upload a JPEG, PNG, or WebP image and the app reads its text, identifies the main claim, searches for relevant sources, and produces a short report: **True**, **False**, or **Could not verify**. It shows a reason and a link beside each supported or corrected fact. A missing search result is never proof that a claim is false.

The interface is available in **বাংলা and English**. Reports and History belong to a private browser session; no account is required. Previously opened reports can be viewed offline on that device. New uploads and searches require internet access. Clearing browser data or switching devices loses access to that browser's History.

## How it works

1. EasyOCR reads the image. If the text or main claim is unclear, the app asks for one correction.
2. Tavily searches for sources. Gemini assists with claim extraction and evidence comparison when available.
3. The report puts the result and reason first; source cards and limitations are under **View evidence**.
4. Claim accuracy, publisher identity, and image authenticity remain separate. A logo or matching news story alone does not prove who created the uploaded image.

The frontend uses React, Vite, and TypeScript. The backend uses FastAPI and SQLite. FastAPI can also serve the built frontend from one public origin.

## Run it for the first time

### Prerequisites

Install Python **3.11 or newer**, Node.js **22 or newer** with npm, and Git. Internet access is needed for the first OCR model download and for live source searches. The commands below use **PowerShell on Windows**.

Clone the repository and open two terminals in its root folder:

```powershell
git clone https://github.com/TanvirHasanRatul09/TruthLayerBD.git
cd TruthLayerBD
```

If you downloaded a ZIP, open the extracted folder instead.

### Set up the backend (terminal 1)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `backend/.env`. Add your own `GEMINI_API_KEY` and `TAVILY_API_KEY` for live analysis. You can start without keys, but searches or comparisons may be unavailable and reports may say **Could not verify**. Keep keys only in the backend environment; never commit `.env` or put keys in a `VITE_*` setting.

The first OCR request downloads Bangla and English model files into `backend/data/models/`. This may take several minutes and needs disk space. If OCR cannot read the image, the app lets you enter the claim manually.

### Set up the frontend (terminal 2)

From the repository root:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
```

The example frontend setting points to the backend at `http://localhost:8000/api/v1`.

### Start the app

In the **backend terminal**:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In the **frontend terminal**:

```powershell
npm run dev
```

Open **http://localhost:5173**. If the frontend cannot connect, open **http://localhost:8000/api/v1/health** to check the backend. Its provider fields show whether keys are configured, not whether a provider is currently responding. Stop each server with `Ctrl+C`.

On later runs, open terminals in `backend/` and `frontend/` and repeat only the two start commands. Restart the backend after changing `backend/.env`. Reinstall dependencies only when they change.

**macOS/Linux:** use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, `cp .env.example .env`, and `.venv/bin/python -m uvicorn app.main:app --reload --port 8000`. The frontend commands are the same, using `cp .env.example .env` for its environment file.

## Use the app

Upload one image, up to **8 MB**, from the welcome page. Analysis starts automatically. If the correction screen appears, enter the main claim once and continue. The report shows a short answer and cited reason before the detailed evidence. You can edit the claim and rerun; the old verdict and citations are cleared first. History can reopen or delete saved reports. The language switch changes app-written text while extracted claims and source quotations stay in their original language.

**True** requires relevant, direct support; **False** requires direct contradiction. **Could not verify** covers missing, mixed, weak, or unavailable evidence. Publisher identity and image authenticity stay unknown unless separately supported. The app cannot guarantee that every news image or claim can be verified.

## Test locally

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

From `frontend/`:

```powershell
node --test tests/*.test.mjs
npm run build
```

The cards in [`docs/manual-test-cases/`](docs/manual-test-cases/README.md) provide upload examples. The [28-card evaluation report](docs/manual-test-cases/EVIDENCE_FIRST_TEST_RUN_2026-11-05.md) separates live-provider findings from fixtures and records unresolved cases. Passing automated tests does not establish live news-verification accuracy.

## Deployment notes

The root [`Dockerfile`](Dockerfile) builds the frontend and runs FastAPI on the host's `PORT`, serving both from one origin. Set `APP_ENV=production`, a unique `APP_SECRET_KEY` of at least 32 characters, and provider keys in the host's private environment settings. On Railway, mount persistent storage at `/app/backend/data` and set `DATABASE_URL=sqlite:////app/backend/data/truthlayer.db` and `UPLOAD_DIR=/app/backend/data/uploads`. SQLite, uploads, and OCR models need persistent storage. The production frontend uses `/api/v1` on its own origin.

Check the host's current memory, storage, and trial limits. EasyOCR can exceed a small free instance's memory or disk allowance. Trial storage is not a permanent archive. Test an actual upload on the public URL before sharing it.

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

Gemini and Tavily keys stay on the backend. If a provider is unavailable or times out, the app offers manual claim correction or an honest partial report. A search result, logo, or model response does not establish image authenticity or publisher identity. History reopens or deletes analyses. Each browser receives a private, signed visitor cookie; reports and images are available only to that browser. Clearing its cookies or switching devices loses access to its online History. Previously saved offline copies on that device may still be present until browser storage is cleared.

Analyses saved before visitor isolation have no owner mapping. They stay in SQLite but cannot be accessed through the public API. Back up the database before any manual cleanup; there is no safe way to assign these rows to an anonymous visitor automatically.

### If configured providers still fail

Check `/api/v1/health` to confirm the keys are configured, then run the backend from a normal PowerShell session with outbound HTTPS access. A backend launched inside a restricted test environment may be unable to open provider connections even when the keys are valid. Restart the backend after changing its environment. The app records `NETWORK_ERROR` for connection failures and keeps a partial report instead of inventing evidence. If the primary Gemini model is unavailable, the configured fallback is tried automatically; set `GEMINI_MODEL` in `backend/.env` to a model your account can access if the primary repeatedly returns an error. Never place provider keys in frontend settings.

The production frontend includes an installable PWA manifest and service worker. Serve it over HTTPS (or localhost) for installation. Previously opened reports are kept locally, up to ten small snapshots, and can be reopened offline with their saved and source-retrieval times. The graph and source list show the same evidence IDs. New uploads, searches and verdicts require a connection. The offline copy omits the uploaded image and raw provider responses; it is replaced with the live report on reconnection.

### Historical dataset matching

The analysis page can search locally imported historical claim and image records. Place reviewed JSONL metadata in `backend/data/datasets/`; use only records with permission to reuse their metadata and attribution. No real-world corpus is bundled. A related historical claim is shown with its original label and source, but does not change the current verdict. An original date or location is shown only for an exact image-file match with a reviewed provenance link. Cropped or recompressed copies will not match. To inspect the synthetic matching evaluation, run `.\.venv\Scripts\python.exe -m scripts.evaluate_dataset` from `backend/`.

## Verification

The four PNG cards in `docs/manual-test-cases/` cover the complete upload flow. The local Markdown guides are excluded from Git.

From `backend/`, run `.\.venv\Scripts\python.exe -m pytest`. This includes deterministic end-to-end tests using all four browser cards and synthetic provider responses. From `frontend/`, run `npm run build`, then `node --test tests/phase8.test.mjs tests/phase9.test.mjs tests/phase11.test.mjs`. Live verdicts depend on provider access and the sources returned at test time.

## Free temporary share link on Windows

This is for a short demo from your own computer. It uses a Cloudflare Quick Tunnel, which needs no hosting account or domain. Keep your computer and the terminal windows running; the link changes each time. Use disposable test images. See [Cloudflare's Quick Tunnel guide](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

1. Install the current `cloudflared` for Windows from [Cloudflare's downloads](https://developers.cloudflare.com/tunnel/downloads/). Open a new PowerShell window and check `cloudflared --version`.
2. In the repository's `frontend` directory, build with a same-origin API address:

   ```powershell
   cd D:\ostad\TruthLayerBD\frontend
   $env:VITE_API_BASE_URL='/api/v1'
   npm run build
   ```

3. In a second PowerShell window, start the backend, which now serves the built frontend at the same address:

   ```powershell
   cd D:\ostad\TruthLayerBD\backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

   Check `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/api/v1/health` before sharing.

4. In a third PowerShell window, start the tunnel. Replace the example address with the email of someone you are inviting; add more addresses with a comma:

   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8000 --allowed-mail 'friend@example.com'
   ```

5. Share the printed `https://...trycloudflare.com` link. The visitor enters their allowed email and the one-time code sent to it. Test upload, report, History, and image loading through that link. Stop the tunnel with `Ctrl+C` when finished.

Quick Tunnels are for development and have no uptime guarantee. This is not a permanent public deployment. Never put Gemini or Tavily keys into `VITE_*` variables.

## Deploy one container with persistent data

The root `Dockerfile` builds the React app with `/api/v1` on the same origin and runs one FastAPI worker. A host must provide enough memory for EasyOCR and a **persistent directory mounted at `/app/backend/data`**. This directory contains SQLite, uploaded images, optional historical datasets, and downloaded OCR models. Keep the service to one instance while using SQLite. Back up the volume regularly. The root `compose.yaml` provides the same volume layout for a Linux VM; it binds port 8000 only to localhost so you can put HTTPS in front of it.

1. Push the current branch to GitHub after tests pass: `git add .`, `git commit -m "Isolate visitors and add deployment container"`, then `git push origin Ratul`. Do not push `backend/.env` or API keys.
2. Choose a container host with a persistent volume and enough memory for OCR. Connect the GitHub repository and select the `Ratul` branch. Use the root `Dockerfile` and one service instance.
3. Create one volume mounted at `/app/backend/data` **before the first deployment**. Set these backend environment variables in the host's secret settings: `APP_ENV=production`, `APP_SECRET_KEY` (a unique random string of at least 32 characters), `DATABASE_URL=sqlite:///./data/truthlayer.db`, `UPLOAD_DIR=./data/uploads`, `OFFLINE_DATASET_DIR=./data/datasets`, and, if available, `GEMINI_API_KEY` and `TAVILY_API_KEY`. Leave provider keys blank for a partial-report demo. Keep the same `APP_SECRET_KEY` across redeployments; rotating it invalidates visitor cookies. Never set a public `VITE_*` API key.
4. Deploy, then enable the host's HTTPS public domain. Open `/api/v1/health` and the root page on that domain. Upload a disposable card, wait for its report, refresh, reopen it from History, and test a separate browser or private window: its History must be empty and the first browser's report URL and image must return 404. Test again after a service restart to confirm the volume persists.

The provided `compose.yaml` is useful on a VM with Docker Compose: create `backend/.env` from `.env.example`, replace `APP_SECRET_KEY`, then run `docker compose up --build -d`. Configure your VM firewall and an HTTPS reverse proxy before sharing a domain. The container image has not been built on this Windows machine because its Docker engine is unavailable; test the build on your host before inviting users.

Free-host limits matter for this app. [Render Free](https://render.com/docs/free) loses SQLite and uploaded images whenever its service restarts or sleeps, so it cannot preserve History with this storage design. [Railway Free and Trial](https://docs.railway.com/pricing/plans) provide at most 0.5–1 GB RAM and a [0.5 GB volume](https://docs.railway.com/volumes/reference); EasyOCR may exceed those limits. Its trial credit and volume retention are limited. A VM with persistent storage and more memory is the safer fit, but availability and account requirements vary. No free tier here is guaranteed to run this OCR app continuously.

### Railway trial walkthrough (resource-limited demo)

1. Sign in at [Railway](https://railway.com/) using GitHub and create a new project from the pushed `TruthLayerBD` repository. Select the `Ratul` branch. Railway detects the root `Dockerfile`.
2. In the service's **Variables**, add the production variables listed above. Generate `APP_SECRET_KEY` locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and paste only the result into Railway's secret variable. Do not paste it into Git or screenshots.
3. In the service settings, add a **Volume** with mount path `/app/backend/data`. Do this before the first upload. Keep one replica.
4. Deploy and inspect the build and service logs. If the image exceeds the plan's image limit, OCR cannot start within RAM, or model files exceed the 0.5 GB volume, stop here and use a larger persistent VM or paid plan; changing the frontend host alone will not fix it.
5. In **Settings → Networking → Public Networking**, select **Generate Domain**. Open the generated HTTPS link and `/api/v1/health`. Run the two-browser checks from step 4 above, then monitor usage and volume storage. The trial grants limited one-time credit; after expiry, the Free plan has a small monthly credit and trial volumes have a retention limit. Check [Railway trial terms](https://docs.railway.com/pricing/free-trial) before relying on the link for other people.

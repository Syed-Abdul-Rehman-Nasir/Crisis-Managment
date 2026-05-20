# CIRO - Crisis Intelligence & Response Orchestrator

This repository contains the CIRO full-stack demo system. 

- For complete architecture and functional details, see `PROJECT_DOCUMENTATION.md`.
- For mobile app development roadmap and technical blueprint, see `APP_DEVELOPMENT_BLUEPRINT.md`.

### Recent Updates
- **Agentic AI Fusion**: Integrated Google Gemini for signal fusion, credibility assessment, and resource allocation explainability.
- **New Scenarios**: Added support for earthquake, industrial fire, and smog emergencies.
- **Tactical Ops Center UI**: Redesigned frontend to provide a dark, data-dense operations dashboard.
- **Deployment Ready**: Included Render and Vercel configurations for easy free-tier deployment.

## Quick Start (Local Development)

### Backend
1. `cd backend`
2. Configure environment:
   - Create `backend/.env` using `backend/.env.example` as a template.
   - Set your API keys (the app will fall back gracefully to mock modes if real keys fail or are omitted).
3. Start the server:
   - `python -m uvicorn main:app --reload`
   - The backend will run on `http://localhost:8000`.

### Frontend
1. `cd frontend`
2. Configure environment:
   - Create `frontend/.env` using `frontend/.env.example` as a template.
   - For local development, `VITE_BACKEND_URL=http://localhost:8000`
3. Install dependencies and start:
   - `npm install`
   - `npm run dev`

## Deploy backend on Render (free)

1. Push this repository to GitHub (see below).
2. In [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint** (or **Web Service**).
3. Connect the GitHub repo. Render reads `render.yaml` at the repo root, or configure manually:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment variables (also in `render.yaml`):
   - `USE_GEMINI=false`
   - `DEMO_MODE=true`
   - `ALLOWED_ORIGINS=*` (set to your frontend URL after deploying Vercel)
5. After deploy, test: `https://YOUR-SERVICE.onrender.com/health`

**Note:** Free tier sleeps when idle; first request may take ~30s.

## Deploy frontend (optional — Vercel / Netlify)

- **Root directory:** `frontend`
- **Build:** `npm run build`
- **Env:** `VITE_BACKEND_URL=https://YOUR-SERVICE.onrender.com`
- Do **not** use `build:mobile` for web deploy (that enables offline-only mode).

## Mobile APK (offline)

See `frontend/MOBILE.md` — `npm run build:mobile` then Capacitor Android build.

## Push to GitHub (no secrets)

```bash
git init
git add .
git status   # confirm .env and venv are NOT listed
git commit -m "Initial commit: CIRO crisis orchestration system"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

Set commit author to your own identity before committing:

```bash
git config user.name "Your Name"
git config user.email "your-email@example.com"
```

## Security
- Do not commit `.env` files.
- See `SECURITY_NOTE.md` regarding API keys.

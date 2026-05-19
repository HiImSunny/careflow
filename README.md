# CareFlow Orchestrator

A multi-agent clinical decision support platform that transforms clinician-provided inputs — typed notes, uploaded images, and spoken audio — into unified, cross-specialty care plans powered by Gemini AI.

Built for the **AI Agent Olympics at Milan AI Week 2026**.

**🚀 Live demo:** [careflow-agents.vercel.app](https://careflow-agents.vercel.app)

---

## Project Overview

CareFlow Orchestrator accepts a patient case as free-text, an image (e.g. chest X-ray, ECG), or dictated audio. A Gemini **Orchestrator Agent** (model configurable via `GEMINI_MODEL`, defaults to `gemini-3.1-flash-lite`) decomposes the case and identifies which medical specialties are relevant. It then dispatches up to four parallel **Specialty Agents** (Radiology, Oncology, Cardiology, Pharmacy). A **Coordinator Agent** reconciles their findings into a structured **Care Plan** containing:

- A chronological **timeline** of recommended actions
- A **recommendations** list
- An **alerts** list (drug interactions, critical findings, agent failures)
- **Findings** grouped by specialty

The React frontend presents the care plan in a three-panel dashboard with real-time agent streaming, and supports PDF and EMR text export.

---

## Architecture

```mermaid
graph TD
    A[Clinician Input<br/>text / image / audio] --> B[UploadWidget<br/>React Frontend]
    B --> C[POST /api/orchestrate<br/>FastAPI Backend]
    C --> D[Orchestrator Agent<br/>Gemini API]
    D --> E[Parallel Dispatch<br/>ThreadPoolExecutor]
    E --> F[Radiology Agent]
    E --> G[Oncology Agent]
    E --> H[Cardiology Agent]
    E --> I[Pharmacy Agent]
    F --> J[Coordinator Agent]
    G --> J
    H --> J
    I --> J
    J --> K[Care Plan JSON<br/>timeline / recommendations / alerts / findings]
    K --> L[SQLite via SQLAlchemy]
    K --> M[Frontend State<br/>Zustand Store]
    M --> N[TimelineView]
    M --> O[CarePlanPanel]
    M --> P[AgentChat SSE]
    M --> Q[ExportBar]

    R[Web Speech API / Speechmatics] --> B
    Q --> S[PDF Export — reportlab]
    Q --> T[EMR Text Export]
```

### Directory Structure

```
careflow/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── database.py              # SQLAlchemy engine + init_db()
│   ├── models.py                # Case, Guideline ORM models
│   ├── schemas.py               # Pydantic request/response schemas
│   ├── requirements.txt
│   ├── .env.example
│   ├── agents/
│   │   ├── orchestrator.py      # Decomposes case, identifies specialties
│   │   ├── radiology.py
│   │   ├── oncology.py
│   │   ├── cardiology.py
│   │   ├── pharmacy.py
│   │   └── coordinator.py       # Reconciles findings into Care Plan
│   ├── routers/
│   │   ├── orchestrate.py       # POST /api/orchestrate (202), GET /api/orchestrate/{id}/result
│   │   ├── cases.py             # GET /api/cases, GET /api/cases/samples
│   │   ├── chat.py              # GET /api/chat/{case_id} (SSE)
│   │   └── speech.py            # WS /api/speech/transcribe
│   ├── services/
│   │   ├── gemini.py            # Gemini API client (multimodal, model configurable)
│   │   ├── speechmatics.py      # Speechmatics WebSocket client
│   │   ├── crew.py              # Multi-agent orchestration flow
│   │   ├── export.py            # PDF + EMR text export
│   │   └── data_loader.py       # Loads guidelines.json / sample_cases.json
│   └── data/
│       ├── guidelines.json      # Specialty clinical guidelines
│       └── sample_cases.json    # Pre-loaded demo cases
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.tsx    # Three-panel layout
│   │   │   ├── UploadWidget.tsx # Text / image / mic input
│   │   │   ├── TimelineView.tsx # Vertical care timeline
│   │   │   ├── CarePlanPanel.tsx# Findings / recommendations / alerts
│   │   │   ├── AgentChat.tsx    # Real-time agent message stream (SSE)
│   │   │   ├── SampleCases.tsx  # Demo case selector
│   │   │   └── ExportBar.tsx    # PDF / EMR export buttons
│   │   ├── hooks/
│   │   │   ├── useOrchestrate.ts
│   │   │   └── useSpeech.ts
│   │   ├── store/caseStore.ts   # Zustand global state
│   │   └── types/index.ts       # Shared TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
└── README.md
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker | 24+ | Includes Docker Compose v2 |
| Docker Compose | 2.x | `docker compose` (no hyphen) |
| Gemini API key | — | [Get one at ai.google.dev](https://ai.google.dev) |
| Speechmatics API key | — | [speechmatics.com](https://www.speechmatics.com) — optional, falls back to Web Speech API |

> **No local Python or Node.js installation is required** when running via Docker Compose.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/HiImSunny/careflow.git
cd careflow
```

### 2. Create your environment file

```bash
cp backend/.env.example .env
```

Open `.env` and fill in your API keys:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
# Optional: override the Gemini model (default: gemini-3.1-flash-lite)
# Options: gemini-3.1-flash-lite, gemini-2.5-flash, gemini-3-flash, gemini-2.5-pro
GEMINI_MODEL=gemini-3.1-flash-lite
SPEECHMATICS_API_KEY=your_speechmatics_api_key_here
DATABASE_URL=sqlite:///./careflow.db
```

> `SPEECHMATICS_API_KEY` can be left blank — the app falls back to the browser's built-in Web Speech API automatically.

---

## Running

### Start both services with Docker Compose

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend (React + Vite) | http://localhost:5173 |
| Backend API (FastAPI) | http://localhost:8000 |
| API docs (Swagger UI) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

The backend automatically initializes the SQLite database on first startup — no manual migration step is needed.

To run in detached mode:

```bash
docker compose up --build -d
docker compose logs -f   # tail logs
docker compose down      # stop and remove containers
```

---

## Sample Cases

Three pre-loaded clinical scenarios are available in the left panel of the dashboard under **Sample Cases**. Click any card to populate the input field, then click **Submit** to run the full orchestration pipeline.

| Case | Specialties | Scenario |
|---|---|---|
| Chest Pain with Imaging | Cardiology, Radiology | 65-year-old male with ST-elevation and crushing chest pain |
| Lung Mass with Medication Review | Radiology, Oncology, Pharmacy | 58-year-old female with spiculated right upper lobe mass and medication interactions |
| Multi-Specialty Complex Case | All four specialties | 72-year-old male with CAD, new DLBCL diagnosis, and R-CHOP consideration |

You can also type or paste your own clinical note directly into the text area, optionally attach an image (drag-and-drop or click to browse), and click **Submit**.

---

## API Reference

All endpoints are prefixed with `/api`. The interactive Swagger UI is available at `http://localhost:8000/docs`.

### `POST /api/orchestrate`

Start the multi-agent orchestration pipeline. Returns **202 Accepted** immediately with a `case_id` — orchestration runs in the background.

**Request body** (`application/json`):

```json
{
  "text": "65-year-old male with chest pain...",
  "image_b64": "<base64-encoded image, optional>",
  "case_id": "<UUID, optional — generated server-side if omitted>"
}
```

**Response** (`202 Accepted`):

```json
{ "case_id": "550e8400-...", "status": "processing" }
```

Connect to `GET /api/chat/{case_id}` to stream agent messages, then fetch `GET /api/orchestrate/{case_id}/result` when the SSE `type: complete` event fires.

---

### `GET /api/orchestrate/{case_id}/result`

Returns the completed care plan once orchestration finishes. Returns `404` while still processing.

---

### `GET /api/cases/samples`

Returns the three pre-loaded sample cases.

---

### `GET /api/chat/{case_id}`

Streams real-time agent messages as **Server-Sent Events**. Each event carries:

```json
{ "agent": "radiology", "content": "...", "timestamp": "..." }
```

A final event with `"type": "complete"` signals orchestration is done.

---

### `GET /api/export/pdf/{case_id}` · `GET /api/export/emr/{case_id}`

Download the care plan as PDF or structured plain-text EMR file.

---

### `GET /health`

Returns `{ "status": "ok" }`.

---

## Development

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

---

## Deployment

### Backend → Render

1. Push the repo to GitHub
2. Create a new **Web Service** on [Render](https://render.com)
3. Set **Root Directory** to `backend`
4. Set **Build Command**: `pip install -r requirements.txt`
5. Set **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables:
   - `GEMINI_API_KEY`
   - `GEMINI_MODEL` — optional, defaults to `gemini-3.1-flash-lite`
   - `SPEECHMATICS_API_KEY` — optional
   - `DATABASE_URL` — e.g. `sqlite:///./careflow.db`

### Frontend → Vercel

1. Import the repo on [Vercel](https://vercel.com)
2. Set **Root Directory** to `frontend`
3. Set **Build Command**: `npm run build`
4. Set **Output Directory**: `dist`
5. Add environment variable:
   - `VITE_API_URL` — your Render backend URL

> **Contact:** duykhang.sunext@gmail.com

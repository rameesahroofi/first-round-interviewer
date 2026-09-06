# Vetto — AI-Powered Interviewer

An AI-powered vetto technical interviewer that conducts realistic, resume-aware voice interviews using a live LLM agent, evaluates candidate responses with Gemini, and produces structured performance reports.

## Features

- **Resume-aware question generation** — LangGraph pipeline analyzes your resume + job description to generate tailored interview questions
- **Live voice interview** — Real-time voice conversation powered by a LiveKit agent with Google's realtime model (supports barge-in / interruption)
- **Monaco code editor** — In-browser code execution via Pyodide (Python) and sandboxed iframes (JavaScript/TypeScript) for coding questions
- **Video proctoring** — Optional webcam proctoring with MediaPipe face detection (no-face, multiple-faces, tab-switch detection) and 3-strike auto-halt
- **AI evaluation** — Full performance analysis covering technical ability, communication, and JD alignment
- **LinkedIn optimizer** — Standalone tool to analyze and improve your LinkedIn profile
- **CV rater** — Standalone tool to score and improve your resume

## Project Structure

```
vetto-interviewer/
├── api.py                     # FastAPI backend (REST API)
├── app.py                     # Streamlit question review tool
├── frontend/                  # Vite + React frontend
│   └── src/App.tsx            # Main interview UI
├── src/
│   ├── agents/                # LangGraph pipeline agents
│   │   ├── resume_parser.py   # Parse resume PDF
│   │   ├── jd_parser.py       # Parse job description
│   │   ├── gap_analyzer.py    # Identify skill gaps
│   │   ├── question_planner.py# Generate interview questions
│   │   ├── answer_extractor.py# Extract answers from transcript
│   │   ├── answer_evaluation.py# Evaluate individual answers
│   │   ├── code_evaluator.py  # Evaluate code submissions
│   │   ├── final_analyzer.py  # Generate final analysis
│   │   ├── linkedin_optimizer.py
│   │   └── resume_rater.py
│   ├── realtime/
│   │   └── agent.py           # LiveKit voice agent
│   ├── graph.py               # LangGraph orchestration
│   └── report_generator.py    # Markdown report generation
├── inputs/                    # Sample resume + JD
├── output/                    # Pipeline outputs (JSON + reports)
└── pyproject.toml
```

## Setup

### Prerequisites

- Python >= 3.12, < 3.13
- Node.js 18+
- A Google GenAI API key
- A LiveKit Cloud project (free tier available at livekit.io)

### 1. Clone and configure environment

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

### 2. Install Python dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 3. Install frontend dependencies

```bash
cd frontend
npm install
```

### 4. Launch all services

Run these in separate terminals:

**FastAPI backend:**
```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

**Frontend dev server:**
```bash
cd frontend
npm run dev
```

**LiveKit agent worker:**
```bash
livekit-agent dev
```
This uses the `[tool.livekit]` config in `pyproject.toml` which points to `src/realtime/agent.py`.

**Streamlit question reviewer (optional):**
```bash
streamlit run app.py
```

## Usage

1. Open the frontend at `http://localhost:5173`
2. Upload your resume PDF, paste the job description, and select a role
3. Click "Generate Interview Plan" to run the LangGraph pipeline
4. (Optional) Open Streamlit at `http://localhost:8501` to review and edit the generated questions, then approve the plan
5. Click "Begin" to start the live voice interview
6. Answer questions naturally — the AI interviewer speaks and listens in real time
7. For coding questions, use the Monaco editor (Run Code executes Python via Pyodide, JS/TS via sandboxed iframe)
8. When finished, the system generates a full performance report with scores, strengths, weaknesses, and recommendations

## Standalone Tools

- **LinkedIn Optimizer** — Navigate to the LinkedIn tab, paste your profile text, and get actionable improvement suggestions
- **CV Rater** — Upload your resume PDF and optionally a target JD to get a scored evaluation with specific fixes

## Tech Stack

- **Backend:** FastAPI, LangGraph, LangChain, Google GenAI (Gemini)
- **Frontend:** React 19, Vite, TypeScript, Monaco Editor, MediaPipe
- **Voice:** LiveKit Agents, Google Realtime Model
- **Code Execution:** Pyodide (Python/WebAssembly), sandboxed iframe (JS/TS)

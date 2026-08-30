# Architecture

## Overview

FirstRound is an AI-powered first-round interviewer with two modes:

1. **Full interview experience** — FastAPI backend + React frontend + LiveKit voice agent
2. **Streamlit reviewer tool** — Question review/approval and results viewing

## Main Interview Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PREPARATION PHASE                            │
│                                                                     │
│  resume.pdf + jd.txt + role                                         │
│        │                                                            │
│        ▼                                                            │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────┐              │
│  │ ResumeParser │   │  JDParser   │   │ GapAnalyzer  │              │
│  │ (Gemini)    │   │  (Gemini)   │   │  (Gemini)    │              │
│  └──────┬──────┘   └──────┬──────┘   └──────┬───────┘              │
│         │                  │                  │                      │
│         ▼                  ▼                  ▼                      │
│  resume.json          jd.json          gap_analysis.json             │
│         │                  │                  │                      │
│         └──────────────────┴──────────────────┘                      │
│                            │                                         │
│                            ▼                                         │
│                ┌──────────────────────┐                              │
│                │  QuestionPlanner     │                              │
│                │  (Gemini)            │                              │
│                └──────────┬───────────┘                              │
│                           │                                          │
│                           ▼                                          │
│                  question_plan.json                                  │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     HUMAN REVIEW (Streamlit)                        │
│                                                                     │
│  question_plan.json → Review/Edit → approved_plan.json              │
│  (app.py provides a UI to edit questions, adjust competencies,      │
│   and approve the interview plan)                                    │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     LIVE INTERVIEW (LiveKit)                        │
│                                                                     │
│  Frontend (React)                Backend (FastAPI)                  │
│  ┌─────────────────┐            ┌────────────────────┐              │
│  │ POST /api/livekit-token │───▶│ Mint JWT token     │              │
│  └────────┬────────┘            └────────────────────┘              │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────┐            ┌────────────────────┐              │
│  │ Room.connect()  │◀──────────▶│ LiveKit Cloud      │              │
│  │ (livekit-client)│   audio    │ Room               │              │
│  └────────┬────────┘            └────────┬───────────┘              │
│           │                              │                           │
│           │                    ┌─────────▼──────────┐                │
│           │                    │ LiveKit Agent       │                │
│           │                    │ (src/realtime/      │                │
│           │                    │  agent.py)          │                │
│           │                    │                     │                │
│           │                    │ • Reads approved    │                │
│           │                    │   questions         │                │
│           │                    │ • Asks one at a time│                │
│           │                    │ • Paraphrase +      │                │
│           │                    │   transition style  │                │
│           │                    │ • Server-side VAD   │                │
│           │                    │   for barge-in      │                │
│           │                    │ • Writes transcript │                │
│           │                    │   to disk           │                │
│           │                    └─────────────────────┘                │
│           │                                                         │
│           ▼                                                         │
│  interview_transcript.json (written by agent during conversation)   │
└─────────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     EVALUATION PHASE                                │
│                                                                     │
│  POST /api/finish-interview                                         │
│        │                                                            │
│        ▼                                                            │
│  ┌────────────────────┐                                             │
│  │ AnswerExtractor    │  Reads transcript + approved_plan          │
│  │ (Gemini)           │  → maps answers to questions               │
│  └────────┬───────────┘                                             │
│           │                                                         │
│           ▼                                                         │
│  ┌────────────────────┐                                             │
│  │ AnswerEvaluator    │  Scores each answer individually           │
│  │ (Gemini)           │  (relevance, technical quality, comms)      │
│  └────────┬───────────┘                                             │
│           │                                                         │
│           ▼                                                         │
│  ┌────────────────────┐  ┌────────────────────┐                     │
│  │ CodeEvaluator      │  │ FinalAnalyzer       │                     │
│  │ (Gemini, per code  │  │ (Gemini)            │                     │
│  │  submission)       │  │ Combines everything │                     │
│  └────────┬───────────┘  └────────┬───────────┘                     │
│           │                       │                                  │
│           └───────────┬───────────┘                                  │
│                       ▼                                              │
│              final_analysis.json                                     │
│              final_report.md                                         │
└─────────────────────────────────────────────────────────────────────┘
```

## LiveKit Agent Dispatch

The LiveKit agent (`src/realtime/agent.py`) is configured in `pyproject.toml`:

```toml
[tool.livekit]
agent = "src/realtime/agent.py"
```

It is launched via:

```bash
livekit-agent dev
```

The agent registers with `agent_name="first-round-interviewer"`. When the frontend
creates a room via `POST /api/livekit-token` and joins it, the LiveKit Cloud
automatically dispatches the agent worker into the room based on the job request
created during token generation. The agent then loads the approved interview
questions and candidate context, initializes the Google RealtimeModel with
server-side VAD, and begins the conversation.

## Standalone Tools

These tools sit outside the main interview pipeline and can be used independently:

- **LinkedIn Optimizer** (`src/agents/linkedin_optimizer.py`) — Accepts LinkedIn profile text, returns section-by-section scoring, issues, and suggested rewrites via Gemini.
- **CV Rater** (`src/agents/resume_rater.py`) — Accepts a resume PDF (+ optional JD), returns ATS score, bullet quality, structure, and JD alignment via Gemini.

Both are exposed as REST endpoints (`/api/linkedin`, `/api/cv-rate`) and have dedicated UI tabs in the frontend.

## Code Execution

Coding questions use in-browser execution — no server-side execution or external API:

- **Python:** Pyodide (CPython compiled to WebAssembly, loaded from CDN)
- **JavaScript/TypeScript:** Sandboxed `<iframe>` with `sandbox="allow-scripts"` (no network, no same-origin)
- **Other languages:** Static code review only (no execution); CodeEvaluator is prompted to not penalize for missing execution results

## Data Flow (File-Based)

All pipeline outputs are written to `output/prep/` as JSON files:

| File | Written By | Read By |
|------|-----------|---------|
| `resume.json` | ResumeParser | QuestionPlanner, FinalAnalyzer |
| `jd.json` | JDParser | QuestionPlanner, FinalAnalyzer |
| `gap_analysis.json` | GapAnalyzer | QuestionPlanner, FinalAnalyzer |
| `question_plan.json` | QuestionPlanner | Streamlit (app.py), agent.py |
| `approved_plan.json` | Streamlit (app.py) | agent.py, AnswerExtractor, AnswerEvaluator |
| `interview_transcript.json` | agent.py | AnswerExtractor |
| `answers.json` | AnswerExtractor | (reference) |
| `answer_evaluation.json` | AnswerEvaluator | FinalAnalyzer |
| `final_analysis.json` | FinalAnalyzer | Streamlit (app.py), Frontend results screen |
| `final_report.md` | report_generator.py | Streamlit (app.py) |

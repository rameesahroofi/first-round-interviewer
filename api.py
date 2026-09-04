import json
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import livekit.api as lk_api
from pydantic import BaseModel

# Phase 1 - Phase 5 Modules
from src.realtime.session_memory import InterviewSessionMemory
from src.agents.adaptive_planner import AdaptivePlannerAgent
from src.agents.explainable_evaluator import ExplainableEvaluator
from src.agents.audio_analytics import AudioAnalyticsEngine
from src.agents.persona_builder import PersonaBuilderAgent
from src.agents.report_and_progress import ProgressTrackerDB, ProfessionalPDFReportGenerator
from src.agents.post_interview_coach import PostInterviewCoachAgent

print("All Phase 1 - Phase 5 Modules Loaded Successfully!")

# Legacy / Pipeline Imports
from src.agents.answer_evaluation import AnswerEvaluator
from src.agents.answer_extractor import AnswerExtractor
from src.agents.code_evaluator import CodeEvaluator
from src.agents.final_analyzer import FinalAnalyzer
from src.agents.linkedin_optimizer import LinkedInOptimizer
from src.agents.resume_parser import ResumeParser
from src.agents.resume_rater import ResumeRater
from src.report_generator import generate_report
from src.graph import run_pipeline

load_dotenv(override=True)


# --------------------------------------------------
# FILE PATHS
# --------------------------------------------------

APPROVED_PLAN_PATH = Path("output/prep/approved_plan.json")
ANSWERS_PATH = Path("output/prep/answers.json")
ANSWER_EVALUATION_PATH = Path("output/prep/answer_evaluation.json")
FINAL_ANALYSIS_PATH = Path("output/prep/final_analysis.json")
FINAL_REPORT_PATH = Path("output/prep/final_report.md")
JD_PATH = Path("output/prep/jd.json")
RESUME_PATH = Path("output/prep/resume.json")
GAP_ANALYSIS_PATH = Path("output/prep/gap_analysis.json")
HISTORY_DIR = Path("output/history")


# --------------------------------------------------
# GLOBAL SESSION STORE
# --------------------------------------------------

active_sessions: Dict[str, InterviewSessionMemory] = {}


# --------------------------------------------------
# FASTAPI APP & CORS
# --------------------------------------------------

app = FastAPI(title="Vetto API")

# Serve output files (PDF reports, etc.) as static files
output_dir = Path("output")
output_dir.mkdir(parents=True, exist_ok=True)
app.mount("/output", StaticFiles(directory="output"), name="output")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# REQUEST & RESPONSE MODELS
# --------------------------------------------------

class CodeSubmission(BaseModel):
    question_id: int
    question: str
    language: str
    code: str
    stdout: str = ""
    stderr: str = ""
    competency: str = ""
    evaluation: Optional[dict] = None


class IntegrityFlag(BaseModel):
    type: str
    timestamp: str
    duration: float = 0.0
    details: str = ""


class InterviewAnswer(BaseModel):
    question_id: int
    question: str
    category: str
    competency: str
    candidate_answer: str


class InterviewSubmission(BaseModel):
    answers: List[InterviewAnswer]
    code_submissions: List[CodeSubmission] = []
    integrity_flags: List[IntegrityFlag] = []
    flagged_for_review: bool = False
    duration_seconds: int = 0
    body_language_score: Optional[float] = None


class LinkedInRequest(BaseModel):
    profile_text: str


class CodeEvalRequest(BaseModel):
    question_id: int
    question: str
    language: str
    code: str
    stdout: str = ""
    stderr: str = ""
    competency: str = ""


class LiveKitTokenRequest(BaseModel):
    candidate_name: str = "candidate"
    room_name: str = ""


class FinishInterviewRequest(BaseModel):
    code_submissions: List[CodeSubmission] = []
    integrity_flags: List[IntegrityFlag] = []
    flagged_for_review: bool = False
    duration_seconds: int = 0
    body_language_score: Optional[float] = None


class StartSessionRequest(BaseModel):
    session_id: str
    candidate_name: str
    job_role: str
    persona: Optional[str] = "technical_lead"
    stress_mode: Optional[str] = "normal"
    language: Optional[str] = "english"


class TurnProcessRequest(BaseModel):
    session_id: str
    question_id: str
    question_text: str
    candidate_answer: str
    audio_duration_seconds: float
    approved_questions: List[Dict[str, Any]]
    followup_depth: int = 0


class PostChatRequest(BaseModel):
    session_id: str
    message: str
    session_summary: Dict[str, Any]


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def save_interview_history(
    final_analysis,
    answers,
    answer_evaluation,
    duration_seconds=0,
    body_language_score=None,
):
    """Save a completed interview as a permanent history record."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    interview_id = uuid.uuid4().hex

    history_record = {
        "interview_id": interview_id,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "duration_seconds": duration_seconds,
        "body_language_score": body_language_score,
        "answers": answers,
        "answer_evaluation": answer_evaluation,
        "analysis": final_analysis,
    }

    history_path = HISTORY_DIR / f"{interview_id}.json"
    history_path.write_text(
        json.dumps(history_record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Interview history saved: {history_path}")
    return interview_id


def compute_metrics(answers_list, duration_seconds: int, body_language_score: Optional[float]):
    filler_words_list = ["um", "uh", "like", "you know"]
    filler_counts = {w: 0 for w in filler_words_list}
    total_words = 0
    
    for ans in answers_list:
        text = ans.get("candidate_answer", "").lower() if isinstance(ans, dict) else ans.candidate_answer.lower()
        if not text:
            continue
        
        words = re.findall(r'\b\w+\b', text)
        total_words += len(words)
        
        for word in filler_words_list:
            if " " in word:
                filler_counts[word] += text.count(word)
            else:
                filler_counts[word] += words.count(word)
            
    wpm = 0
    if duration_seconds and duration_seconds > 0:
        wpm = total_words / (duration_seconds / 60.0)
        
    speech_metrics = {
        "filler_words": filler_counts,
        "wpm": round(wpm, 2),
        "total_words": total_words,
        "total_filler_words": sum(filler_counts.values())
    }
    
    body_language_metrics = None
    if body_language_score is not None:
        posture = "Good"
        if body_language_score < 50:
            posture = "Poor"
        elif body_language_score < 75:
            posture = "Needs Improvement"
        
        body_language_metrics = {
            "eye_contact_score": round(body_language_score, 1),
            "posture_feedback": posture
        }
        
    return speech_metrics, body_language_metrics


# --------------------------------------------------
# NEW ADVANCED AI COACHING ENDPOINTS (PHASES 1 - 5)
# --------------------------------------------------

@app.post("/api/interview/start")
async def start_interview_session(req: StartSessionRequest):
    """Initializes real-time session memory and returns configured persona system prompt."""
    memory = InterviewSessionMemory(
        session_id=req.session_id,
        candidate_name=req.candidate_name,
        job_role=req.job_role
    )
    active_sessions[req.session_id] = memory
    
    system_prompt = PersonaBuilderAgent.build_system_prompt(
        persona_key=req.persona,
        stress_mode=req.stress_mode,
        language=req.language
    )
    
    return {
        "status": "initialized",
        "session_id": req.session_id,
        "system_prompt": system_prompt
    }


@app.post("/api/interview/process-turn")
async def process_interview_turn(req: TurnProcessRequest):
    """
    Processes a live candidate turn: calculates WPM/fillers, 
    evaluates response quality, logs memory, and plans next adaptive step.
    """
    memory = active_sessions.get(req.session_id)
    if not memory:
        memory = InterviewSessionMemory(session_id=req.session_id, job_role="Software Engineer")
        active_sessions[req.session_id] = memory

    # 1. Speech analytics (WPM and Fillers)
    speech_metrics = AudioAnalyticsEngine.analyze_transcript_segment(
        transcript=req.candidate_answer,
        duration_seconds=req.audio_duration_seconds
    )

    # 2. Evaluation using Explainable Evaluator
    evaluator = AnswerEvaluator()
    raw_eval = evaluator.evaluate(
        question=req.question_text,
        answer=req.candidate_answer,
        competency="Technical & Delivery"
    )
    eval_result = ExplainableEvaluator.parse_and_validate_evaluation(json.dumps(raw_eval))

    # 3. Log turn in memory
    memory.record_turn(
        question_id=req.question_id,
        question=req.question_text,
        answer=req.candidate_answer,
        evaluation=eval_result
    )

    # 4. Adaptive next question logic
    planner = AdaptivePlannerAgent(max_followup_depth=2)
    next_step = planner.plan_next_step(
        current_question={"id": req.question_id, "text": req.question_text, "topic": "Core Concept"},
        candidate_answer=req.candidate_answer,
        evaluation=eval_result,
        memory=memory,
        approved_question_bank=req.approved_questions,
        current_followup_depth=req.followup_depth
    )

    return {
        "speech_metrics": speech_metrics,
        "evaluation": eval_result,
        "next_step": next_step,
        "session_context": memory.get_prompt_context()
    }


@app.get("/api/interview/history")
async def get_progress_history():
    """Returns historical session scores for progress tracking dashboard."""
    return ProgressTrackerDB.load_history()


@app.post("/api/interview/post-chat")
async def post_interview_chat(req: PostChatRequest):
    """Answers candidate follow-up questions grounded strictly in session telemetry."""
    reply = PostInterviewCoachAgent.answer_candidate_query(req.message, req.session_summary)
    return {"reply": reply}


@app.get("/api/interview/next-target")
async def get_next_interview_target():
    """Returns focus areas and difficulty targets for the candidate's next practice session."""
    return PostInterviewCoachAgent.plan_next_interview_focus()


# --------------------------------------------------
# PREPARE (LangGraph Pipeline)
# --------------------------------------------------

@app.post("/api/prepare")
async def prepare_interview(
    role: str = Form(...),
    jd_text: str = Form(...),
    resume_file: UploadFile = File(...),
    persona: str = Form(default="Friendly HR"),
    language: str = Form(default="English"),
):
    if not resume_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Resume must be a PDF file.")

    if not jd_text.strip():
        raise HTTPException(status_code=400, detail="Job description text cannot be empty.")

    if not role.strip():
        raise HTTPException(status_code=400, detail="Role cannot be empty.")

    try:
        prefs_path = Path("output/prep/preferences.json")
        prefs_path.parent.mkdir(parents=True, exist_ok=True)
        prefs_path.write_text(json.dumps({"persona": persona, "language": language}), encoding="utf-8")
        resume_bytes = await resume_file.read()

        final_state = run_pipeline(
            role=role.strip(),
            jd_text=jd_text.strip(),
            resume_bytes=resume_bytes,
        )

        APPROVED_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
        APPROVED_PLAN_PATH.write_text(
            json.dumps(final_state["question_plan"], indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return {
            "success": True,
            "message": "Interview preparation complete.",
            "question_plan": final_state["question_plan"],
            "gap_analysis": final_state["gap_analysis"],
            "resume_summary": {
                "name": final_state["resume_data"].get("candidate_name", ""),
                "skills": final_state["resume_data"].get("skills", [])[:10],
                "experience_count": len(final_state["resume_data"].get("experience", [])),
                "projects_count": len(final_state["resume_data"].get("projects", [])),
            },
        }

    except RuntimeError as e:
        raise HTTPException(status_code=422, detail=f"Pipeline error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preparation failed: {e}")


# --------------------------------------------------
# QUESTIONS
# --------------------------------------------------

@app.get("/api/questions")
def get_questions():
    plan_path = APPROVED_PLAN_PATH if APPROVED_PLAN_PATH.exists() else Path("output/prep/question_plan.json")
    if not plan_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Interview plan not found. Please complete preparation first.",
        )
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        return {"questions": plan.get("questions", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load questions: {e}")


# --------------------------------------------------
# SUBMIT INTERVIEW ANSWERS
# --------------------------------------------------

@app.post("/api/answers")
def submit_answers(submission: InterviewSubmission):
    try:
        answers_data = {"answers": [a.model_dump() for a in submission.answers]}
        ANSWERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        ANSWERS_PATH.write_text(
            json.dumps(answers_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        evaluator = AnswerEvaluator()
        evaluations = []

        for answer_data in submission.answers:
            if not answer_data.candidate_answer.strip() or answer_data.category == "candidate_questions":
                evaluation = {
                    "score": 0, "relevance": 0, "technical_quality": 0,
                    "communication": 0, "strengths": [], "weaknesses": [],
                    "feedback": "No answer provided." if not answer_data.candidate_answer.strip() else "Candidate question round - not scored.",
                    "recommendation": "N/A"
                }
            else:
                evaluation = evaluator.evaluate(
                    question=answer_data.question,
                    answer=answer_data.candidate_answer,
                    competency=answer_data.competency,
                )

            evaluations.append({
                "question_id": answer_data.question_id,
                "question": answer_data.question,
                "category": answer_data.category,
                "competency": answer_data.competency,
                "candidate_answer": answer_data.candidate_answer,
                "evaluation": evaluation,
            })

        answer_evaluation = {"evaluations": evaluations}
        ANSWER_EVALUATION_PATH.write_text(
            json.dumps(answer_evaluation, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        for path in [JD_PATH, RESUME_PATH, GAP_ANALYSIS_PATH]:
            if not path.exists():
                raise FileNotFoundError(f"Required file not found: {path}")

        jd = json.loads(JD_PATH.read_text(encoding="utf-8"))
        resume = json.loads(RESUME_PATH.read_text(encoding="utf-8"))
        gap_analysis = json.loads(GAP_ANALYSIS_PATH.read_text(encoding="utf-8"))

        code_subs = [cs.model_dump() for cs in submission.code_submissions]
        integrity_flags = [f.model_dump() for f in submission.integrity_flags]

        speech_metrics, body_language_metrics = compute_metrics(
            submission.answers, submission.duration_seconds, submission.body_language_score
        )
        analyzer = FinalAnalyzer()
        final_analysis = analyzer.analyze(
            jd=jd,
            resume=resume,
            gap_analysis=gap_analysis,
            answer_evaluation=answer_evaluation,
            code_submissions=code_subs if code_subs else None,
            integrity_flags=integrity_flags if integrity_flags else None,
            flagged_for_review=submission.flagged_for_review,
            speech_metrics=speech_metrics,
            body_language_metrics=body_language_metrics,
        )

        FINAL_ANALYSIS_PATH.write_text(
            json.dumps(final_analysis, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Save session into ProgressTrackerDB
        ProgressTrackerDB.save_session({
            "session_id": uuid.uuid4().hex[:8],
            "job_role": jd.get("title", "Software Engineer"),
            "overall_score": final_analysis.get("overall_score", 0),
            "technical_score": final_analysis.get("technical_score", 0),
            "communication_score": final_analysis.get("communication_score", 0),
            "wpm": speech_metrics.get("wpm", 0),
            "filler_count": speech_metrics.get("total_filler_words", 0),
            "weak_areas": final_analysis.get("areas_for_improvement", [])
        })

        interview_id = save_interview_history(
            final_analysis=final_analysis,
            answers=answers_data,
            answer_evaluation=answer_evaluation,
            duration_seconds=submission.duration_seconds,
            body_language_score=submission.body_language_score,
        )

        try:
            report_md = generate_report(final_analysis)
            FINAL_REPORT_PATH.write_text(report_md, encoding="utf-8")
        except Exception as err:
            print(f"Failed to generate report markdown: {err}")

        # Generate downloadable PDF
        try:
            ProfessionalPDFReportGenerator.generate_pdf({
                "candidate_name": resume.get("candidate_name", "Candidate"),
                "job_role": jd.get("title", "Software Engineer"),
                "overall_score": final_analysis.get("overall_score", 0),
                "technical_score": final_analysis.get("technical_score", 0),
                "communication_score": final_analysis.get("communication_score", 0),
                "wpm": speech_metrics.get("wpm", 0),
                "filler_count": speech_metrics.get("total_filler_words", 0),
                "questions": [
                    {
                        "question": ev.get("question"),
                        "score": ev.get("evaluation", {}).get("score", 0),
                        "answer": ev.get("candidate_answer"),
                        "rationale": ev.get("evaluation", {}).get("feedback", "")
                    } for ev in evaluations
                ]
            }, output_path="output/prep/interview_report.pdf")
        except Exception as pdf_err:
            print(f"Failed to generate PDF report: {pdf_err}")

        return {
            "success": True,
            "message": "Interview evaluated successfully.",
            "analysis": final_analysis,
            "interview_id": interview_id,
        }

    except Exception as e:
        print(f"Interview evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------
# GET ANALYSIS
# --------------------------------------------------

@app.get("/api/analysis")
def get_analysis():
    if not FINAL_ANALYSIS_PATH.exists():
        raise HTTPException(status_code=404, detail="Final analysis not found.")
    try:
        return json.loads(FINAL_ANALYSIS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read analysis: {e}")


# --------------------------------------------------
# LIVEKIT TOKEN
# --------------------------------------------------

@app.post("/api/livekit-token")
def mint_livekit_token(request: LiveKitTokenRequest):
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")

    if not api_key or not api_secret or not livekit_url:
        return {
            "available": False,
            "token": None,
            "url": None,
            "room_name": None,
            "message": "LiveKit credentials not set. Using browser AI voice engine."
        }

    room_name = request.room_name or f"interview-{uuid.uuid4()}"
    identity = f"candidate-{uuid.uuid4().hex[:8]}"

    token = (
        lk_api.AccessToken(api_key, api_secret)
        .with_identity(identity)
        .with_name(request.candidate_name or "Candidate")
        .with_grants(
            lk_api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        .to_jwt()
    )

    return {
        "available": True,
        "token": token,
        "url": livekit_url,
        "room_name": room_name,
    }



# --------------------------------------------------
# FINISH INTERVIEW
# --------------------------------------------------

@app.post("/api/finish-interview")
def finish_interview(request: FinishInterviewRequest):
    try:
        extractor = AnswerExtractor()
        extracted = extractor.extract()
        extracted_answers = extracted.get("answers", [])

        evaluator = AnswerEvaluator()
        evaluations = []

        for ans in extracted_answers:
            candidate_answer = ans.get("candidate_answer", "")
            category = ans.get("category", "")

            if not candidate_answer.strip() or category == "candidate_questions":
                evaluation = {
                    "score": 0, "relevance": 0, "technical_quality": 0,
                    "communication": 0, "strengths": [], "weaknesses": [],
                    "feedback": "No answer provided." if not candidate_answer.strip() else "Candidate question round - not scored.",
                    "recommendation": "N/A"
                }
            else:
                evaluation = evaluator.evaluate(
                    question=ans.get("question", ""),
                    answer=candidate_answer,
                    competency=ans.get("competency", ""),
                )

            evaluations.append({
                "question_id": ans.get("question_id"),
                "question": ans.get("question", ""),
                "category": category,
                "competency": ans.get("competency", ""),
                "candidate_answer": candidate_answer,
                "evaluation": evaluation,
            })

        answer_evaluation = {"evaluations": evaluations}
        ANSWER_EVALUATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        ANSWER_EVALUATION_PATH.write_text(
            json.dumps(answer_evaluation, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        for path in [JD_PATH, RESUME_PATH, GAP_ANALYSIS_PATH]:
            if not path.exists():
                raise FileNotFoundError(f"Required file not found: {path}")

        jd = json.loads(JD_PATH.read_text(encoding="utf-8"))
        resume = json.loads(RESUME_PATH.read_text(encoding="utf-8"))
        gap_analysis = json.loads(GAP_ANALYSIS_PATH.read_text(encoding="utf-8"))

        code_subs = [cs.model_dump() for cs in request.code_submissions]
        integrity_flags = [f.model_dump() for f in request.integrity_flags]

        speech_metrics, body_language_metrics = compute_metrics(
            extracted_answers, request.duration_seconds, request.body_language_score
        )
        analyzer = FinalAnalyzer()
        final_analysis = analyzer.analyze(
            jd=jd,
            resume=resume,
            gap_analysis=gap_analysis,
            answer_evaluation=answer_evaluation,
            code_submissions=code_subs if code_subs else None,
            integrity_flags=integrity_flags if integrity_flags else None,
            flagged_for_review=request.flagged_for_review,
            speech_metrics=speech_metrics,
            body_language_metrics=body_language_metrics,
        )

        FINAL_ANALYSIS_PATH.write_text(
            json.dumps(final_analysis, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Save session into ProgressTrackerDB
        ProgressTrackerDB.save_session({
            "session_id": uuid.uuid4().hex[:8],
            "job_role": jd.get("title", jd.get("role", "Software Engineer")),
            "overall_score": final_analysis.get("overall_score", 0),
            "technical_score": final_analysis.get("technical_score", 0),
            "communication_score": final_analysis.get("communication_score", 0),
            "wpm": speech_metrics.get("wpm", 0),
            "filler_count": speech_metrics.get("total_filler_words", 0),
            "weak_areas": final_analysis.get("areas_for_improvement", final_analysis.get("weaknesses", []))
        })

        interview_id = save_interview_history(
            final_analysis=final_analysis,
            answers=extracted,
            answer_evaluation=answer_evaluation,
            duration_seconds=request.duration_seconds,
            body_language_score=request.body_language_score,
        )

        try:
            report_md = generate_report(final_analysis)
            FINAL_REPORT_PATH.write_text(report_md, encoding="utf-8")
        except Exception as err:
            print(f"Failed to generate report markdown: {err}")

        # Generate downloadable PDF
        try:
            ProfessionalPDFReportGenerator.generate_pdf({
                "candidate_name": resume.get("candidate_name", "Candidate"),
                "job_role": jd.get("title", jd.get("role", "Software Engineer")),
                "overall_score": final_analysis.get("overall_score", 0),
                "technical_score": final_analysis.get("technical_score", 0),
                "communication_score": final_analysis.get("communication_score", 0),
                "wpm": speech_metrics.get("wpm", 0),
                "filler_count": speech_metrics.get("total_filler_words", 0),
                "questions": [
                    {
                        "question": ev.get("question"),
                        "score": ev.get("evaluation", {}).get("score", 0),
                        "answer": ev.get("candidate_answer"),
                        "rationale": ev.get("evaluation", {}).get("feedback", "")
                    } for ev in evaluations
                ]
            }, output_path="output/prep/interview_report.pdf")
        except Exception as pdf_err:
            print(f"Failed to generate PDF report: {pdf_err}")

        return {
            "success": True,
            "message": "Interview evaluated successfully.",
            "analysis": final_analysis,
            "interview_id": interview_id,
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------
# EVALUATE CODE
# --------------------------------------------------

@app.post("/api/evaluate-code")
def evaluate_code(request: CodeEvalRequest):
    try:
        evaluator = CodeEvaluator()
        result = evaluator.evaluate(
            question=request.question,
            code=request.code,
            language=request.language,
            stdout=request.stdout,
            stderr=request.stderr,
            competency=request.competency,
        )
        return {"success": True, "evaluation": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code evaluation failed: {e}")


# --------------------------------------------------
# LINKEDIN OPTIMIZER
# --------------------------------------------------

@app.post("/api/linkedin")
def optimize_linkedin(request: LinkedInRequest):
    if not request.profile_text.strip():
        raise HTTPException(status_code=400, detail="Profile text cannot be empty.")
    try:
        optimizer = LinkedInOptimizer()
        result = optimizer.analyze(request.profile_text)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LinkedIn analysis failed: {e}")


# --------------------------------------------------
# CV / RESUME RATER
# --------------------------------------------------

@app.post("/api/cv-rate")
async def rate_cv(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(default=""),
):
    if not resume_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Resume must be a PDF file.")
    try:
        resume_bytes = await resume_file.read()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(resume_bytes)
            tmp_path = Path(tmp.name)

        parser = ResumeParser()
        resume_text = parser.extract_text(tmp_path)
        tmp_path.unlink(missing_ok=True)

        if not resume_text.strip():
            raise ValueError("No text could be extracted from the PDF.")

        rater = ResumeRater()
        result = rater.rate(resume_text, jd_text)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV rating failed: {e}")


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/")
def root():
    return {"message": "Vetto API is running."}
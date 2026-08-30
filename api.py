import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import livekit.api as lk_api
from pydantic import BaseModel

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


# --------------------------------------------------
# FASTAPI
# --------------------------------------------------

app = FastAPI(title="FirstRound API")

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
# REQUEST MODELS
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
    answers: list[InterviewAnswer]
    code_submissions: list[CodeSubmission] = []
    integrity_flags: list[IntegrityFlag] = []
    flagged_for_review: bool = False


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
    code_submissions: list[CodeSubmission] = []
    integrity_flags: list[IntegrityFlag] = []
    flagged_for_review: bool = False


# --------------------------------------------------
# PREPARE (LangGraph pipeline)
# --------------------------------------------------

@app.post("/api/prepare")
async def prepare_interview(
    role: str = Form(...),
    jd_text: str = Form(...),
    resume_file: UploadFile = File(...),
):
    """
    Run the full preparation pipeline:
    resume_parser -> jd_parser -> gap_analyzer -> question_planner
    Saves all JSON outputs to output/prep/ and returns the question plan.
    """
    if not resume_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Resume must be a PDF file.")

    if not jd_text.strip():
        raise HTTPException(status_code=400, detail="Job description text cannot be empty.")

    if not role.strip():
        raise HTTPException(status_code=400, detail="Role cannot be empty.")

    try:
        resume_bytes = await resume_file.read()

        final_state = run_pipeline(
            role=role.strip(),
            jd_text=jd_text.strip(),
            resume_bytes=resume_bytes,
        )

        # Initialize approved_plan.json with generated plan so questions are immediately ready
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
        # 1. Save raw answers
        answers_data = {"answers": [a.model_dump() for a in submission.answers]}
        ANSWERS_PATH.parent.mkdir(parents=True, exist_ok=True)
        ANSWERS_PATH.write_text(
            json.dumps(answers_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Saved {len(submission.answers)} interview answers.")

        # 2. Actually evaluate each answer with Gemini (no more stub zeros)
        evaluator = AnswerEvaluator()
        evaluations = []

        for answer_data in submission.answers:
            # Skip evaluation for empty answers or candidate_questions category
            if not answer_data.candidate_answer.strip() or answer_data.category == "candidate_questions":
                evaluation = {
                    "score": 0, "relevance": 0, "technical_quality": 0,
                    "communication": 0, "strengths": [], "weaknesses": [],
                    "feedback": "No answer provided." if not answer_data.candidate_answer.strip() else "Candidate question round - not scored.",
                    "recommendation": "N/A"
                }
            else:
                print(f"Evaluating question {answer_data.question_id}...")
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

        # 3. Save evaluations
        answer_evaluation = {"evaluations": evaluations}
        ANSWER_EVALUATION_PATH.write_text(
            json.dumps(answer_evaluation, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 4. Load JD / Resume / Gap Analysis
        for path in [JD_PATH, RESUME_PATH, GAP_ANALYSIS_PATH]:
            if not path.exists():
                raise FileNotFoundError(f"Required file not found: {path}")

        jd = json.loads(JD_PATH.read_text(encoding="utf-8"))
        resume = json.loads(RESUME_PATH.read_text(encoding="utf-8"))
        gap_analysis = json.loads(GAP_ANALYSIS_PATH.read_text(encoding="utf-8"))

        # 5. Prepare code submissions for final analysis
        code_subs = [cs.model_dump() for cs in submission.code_submissions]
        integrity_flags = [f.model_dump() for f in submission.integrity_flags]

        # 6. Generate final analysis
        analyzer = FinalAnalyzer()
        final_analysis = analyzer.analyze(
            jd=jd,
            resume=resume,
            gap_analysis=gap_analysis,
            answer_evaluation=answer_evaluation,
            code_submissions=code_subs if code_subs else None,
            integrity_flags=integrity_flags if integrity_flags else None,
            flagged_for_review=submission.flagged_for_review,
        )

        # 7. Save final analysis
        FINAL_ANALYSIS_PATH.write_text(
            json.dumps(final_analysis, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print("Final interview analysis generated successfully.")

        # 8. Generate and save human-readable report
        try:
            report_md = generate_report(final_analysis)
            FINAL_REPORT_PATH.write_text(report_md, encoding="utf-8")
            print("Final interview report markdown generated successfully.")
        except Exception as err:
            print(f"Failed to generate report markdown: {err}")

        return {
            "success": True,
            "message": "Interview evaluated successfully.",
            "analysis": final_analysis,
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
    """
    Mint a LiveKit access token so the frontend can join a room.
    The LiveKit agent worker (configured with agent_name='first-round-interviewer')
    is automatically dispatched into rooms created via the LiveKit Cloud dashboard
    or via `livekit-agent dev` which watches for new rooms.
    """
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")

    if not api_key or not api_secret or not livekit_url:
        raise HTTPException(
            status_code=500,
            detail="LiveKit environment variables are not configured.",
        )

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
        "token": token,
        "url": livekit_url,
        "room_name": room_name,
    }


# --------------------------------------------------
# FINISH INTERVIEW (transcript-derived answers)
# --------------------------------------------------

@app.post("/api/finish-interview")
def finish_interview(request: FinishInterviewRequest):
    """
    End the interview by extracting answers from the LiveKit transcript
    server-side via AnswerExtractor, then running the full evaluation pipeline.
    """
    try:
        # 1. Extract answers from transcript using AnswerExtractor
        extractor = AnswerExtractor()
        extracted = extractor.extract()
        extracted_answers = extracted.get("answers", [])
        print(f"Extracted {len(extracted_answers)} answers from transcript.")

        # 2. Evaluate each answer with Gemini
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
                print(f"Evaluating question {ans.get('question_id', '?')}...")
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

        # 3. Save answer evaluations
        answer_evaluation = {"evaluations": evaluations}
        ANSWER_EVALUATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        ANSWER_EVALUATION_PATH.write_text(
            json.dumps(answer_evaluation, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # 4. Load JD / Resume / Gap Analysis
        for path in [JD_PATH, RESUME_PATH, GAP_ANALYSIS_PATH]:
            if not path.exists():
                raise FileNotFoundError(f"Required file not found: {path}")

        jd = json.loads(JD_PATH.read_text(encoding="utf-8"))
        resume = json.loads(RESUME_PATH.read_text(encoding="utf-8"))
        gap_analysis = json.loads(GAP_ANALYSIS_PATH.read_text(encoding="utf-8"))

        # 5. Prepare code submissions and integrity flags
        code_subs = [cs.model_dump() for cs in request.code_submissions]
        integrity_flags = [f.model_dump() for f in request.integrity_flags]

        # 6. Generate final analysis
        analyzer = FinalAnalyzer()
        final_analysis = analyzer.analyze(
            jd=jd,
            resume=resume,
            gap_analysis=gap_analysis,
            answer_evaluation=answer_evaluation,
            code_submissions=code_subs if code_subs else None,
            integrity_flags=integrity_flags if integrity_flags else None,
            flagged_for_review=request.flagged_for_review,
        )

        # 7. Save final analysis
        FINAL_ANALYSIS_PATH.write_text(
            json.dumps(final_analysis, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print("Final interview analysis generated successfully.")

        # 8. Generate and save human-readable report
        try:
            report_md = generate_report(final_analysis)
            FINAL_REPORT_PATH.write_text(report_md, encoding="utf-8")
            print("Final interview report markdown generated successfully.")
        except Exception as err:
            print(f"Failed to generate report markdown: {err}")

        return {
            "success": True,
            "message": "Interview evaluated successfully.",
            "analysis": final_analysis,
        }

    except FileNotFoundError as e:
        print(f"Finish interview failed (missing file): {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"Finish interview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------
# EVALUATE CODE (in-browser execution result -> Gemini scoring)
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
    return {"message": "FirstRound API is running."}

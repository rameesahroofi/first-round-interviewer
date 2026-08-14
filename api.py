import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.agents.answer_evaluation import AnswerEvaluator
from src.agents.final_analyzer import FinalAnalyzer


# --------------------------------------------------
# FILE PATHS
# --------------------------------------------------

APPROVED_PLAN_PATH = Path(
    "output/prep/approved_plan.json"
)

ANSWERS_PATH = Path(
    "output/prep/answers.json"
)

ANSWER_EVALUATION_PATH = Path(
    "output/prep/answer_evaluation.json"
)

FINAL_ANALYSIS_PATH = Path(
    "output/prep/final_analysis.json"
)

JD_PATH = Path(
    "output/prep/jd.json"
)

RESUME_PATH = Path(
    "output/prep/resume.json"
)

GAP_ANALYSIS_PATH = Path(
    "output/prep/gap_analysis.json"
)


# --------------------------------------------------
# FASTAPI
# --------------------------------------------------

app = FastAPI(
    title="FirstRound API"
)

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
# REQUEST MODEL
# --------------------------------------------------

class InterviewAnswer(BaseModel):
    question_id: int
    question: str
    category: str
    competency: str
    candidate_answer: str


class InterviewSubmission(BaseModel):
    answers: list[InterviewAnswer]


# --------------------------------------------------
# QUESTIONS
# --------------------------------------------------

@app.get("/api/questions")
def get_questions():

    if not APPROVED_PLAN_PATH.exists():
        return {
            "questions": [],
            "error": "Approved interview plan not found."
        }

    try:
        plan = json.loads(
            APPROVED_PLAN_PATH.read_text(
                encoding="utf-8"
            )
        )

        return {
            "questions": plan.get(
                "questions",
                []
            )
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load questions: {e}"
        )


# --------------------------------------------------
# SUBMIT INTERVIEW
# --------------------------------------------------

@app.post("/api/answers")
def submit_answers(
    submission: InterviewSubmission
):

    try:

        # ------------------------------------------
        # 1. Save the NEW answers
        # ------------------------------------------

        answers_data = {
            "answers": [
                answer.model_dump()
                for answer in submission.answers
            ]
        }

        ANSWERS_PATH.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        ANSWERS_PATH.write_text(
            json.dumps(
                answers_data,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        print(
            f"Saved {len(submission.answers)} interview answers."
        )

        # ------------------------------------------
        # 2. Prepare answers for final analysis
        # ------------------------------------------

        evaluations = []

        for answer_data in submission.answers:

            evaluations.append(
                {
                    "question_id": answer_data.question_id,
                    "question": answer_data.question,
                    "competency": answer_data.competency,
                    "candidate_answer": answer_data.candidate_answer,
                    "evaluation": {
                        "score": 0,
                        "relevance": 0,
                        "technical_quality": 0,
                        "communication": 0,
                        "strengths": [],
                        "weaknesses": [],
                        "feedback": "",
                        "recommendation": ""
                    }
                }
            )

        # ------------------------------------------
        # 3. Save answer evaluation
        # ------------------------------------------

        answer_evaluation = {
            "evaluations": evaluations
        }

        ANSWER_EVALUATION_PATH.write_text(
            json.dumps(
                answer_evaluation,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        # ------------------------------------------
        # 4. Load JD / Resume / Gap Analysis
        # ------------------------------------------

        if not JD_PATH.exists():
            raise FileNotFoundError(
                f"JD file not found: {JD_PATH}"
            )

        if not RESUME_PATH.exists():
            raise FileNotFoundError(
                f"Resume file not found: {RESUME_PATH}"
            )

        if not GAP_ANALYSIS_PATH.exists():
            raise FileNotFoundError(
                f"Gap analysis not found: {GAP_ANALYSIS_PATH}"
            )

        jd = json.loads(
            JD_PATH.read_text(
                encoding="utf-8"
            )
        )

        resume = json.loads(
            RESUME_PATH.read_text(
                encoding="utf-8"
            )
        )

        gap_analysis = json.loads(
            GAP_ANALYSIS_PATH.read_text(
                encoding="utf-8"
            )
        )

        # ------------------------------------------
        # 5. Generate final analysis
        # ------------------------------------------

        analyzer = FinalAnalyzer()

        final_analysis = analyzer.analyze(
            jd=jd,
            resume=resume,
            gap_analysis=gap_analysis,
            answer_evaluation=answer_evaluation,
        )

        # ------------------------------------------
        # 6. Save NEW final analysis
        # ------------------------------------------

        FINAL_ANALYSIS_PATH.write_text(
            json.dumps(
                final_analysis,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        print(
            "Final interview analysis generated successfully."
        )

        # ------------------------------------------
        # 7. Return NEW analysis to React
        # ------------------------------------------

        return {
            "success": True,
            "message": "Interview evaluated successfully.",
            "analysis": final_analysis,
        }

    except Exception as e:

        print(
            f"Interview evaluation failed: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# --------------------------------------------------
# GET ANALYSIS
# --------------------------------------------------

@app.get("/api/analysis")
def get_analysis():

    if not FINAL_ANALYSIS_PATH.exists():

        return {
            "error": "Final analysis not found."
        }

    try:

        return json.loads(
            FINAL_ANALYSIS_PATH.read_text(
                encoding="utf-8"
            )
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"Failed to read analysis: {e}"
        )


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/")
def root():

    return {
        "message": "FirstRound API is running."
    }
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)

TECHNICAL_ROLES = {
    "software engineer", "backend engineer", "frontend engineer",
    "full stack engineer", "full-stack engineer", "mobile engineer",
    "data engineer", "ml engineer", "ai engineer", "ai/ml engineer",
    "machine learning engineer", "devops engineer", "site reliability engineer",
    "sre", "platform engineer", "data scientist", "security engineer",
    "embedded engineer", "cloud engineer",
}

def classify_role(role: str) -> str:
    normalized = role.lower().strip()
    for tr in TECHNICAL_ROLES:
        if tr in normalized:
            return "technical"
    return "non_technical"

def infer_language(role: str) -> str:
    r = role.lower()
    if "frontend" in r or "react" in r:
        return "javascript"
    if "mobile" in r or "android" in r:
        return "kotlin"
    if "ios" in r or "swift" in r:
        return "swift"
    return "python"

class QuestionPlanner:
    def __init__(self) -> None:
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    def create_plan(self, jd_data, resume_data, gap_analysis, role="Software Engineer"):
        role_type = classify_role(role)
        lang = infer_language(role)
        if role_type == "technical":
            coding_block = (
                "CODING QUESTIONS REQUIRED: Include exactly 2 questions with category=coding. "
                f"Each needs language={lang}, starter_code (realistic skeleton), difficulty (easy/medium/hard). "
                "Plus: 2 resume_validation, 2 jd_skills, 2 project, 2 scenario, 1 behavioral, 1 candidate_questions. Total=12."
            )
            total = 12
        else:
            coding_block = (
                "NON-TECHNICAL ROLE - NO coding questions. "
                "Distribution: 2 resume_validation, 2 jd_skills, 2 project, 2 behavioral, 2 case_scenario, 1 candidate_questions. Total=11."
            )
            total = 11

        prompt = f"""You are an expert interview question planner for the role of: {role}

JOB DESCRIPTION:
{json.dumps(jd_data, indent=2)}

CANDIDATE RESUME:
{json.dumps(resume_data, indent=2)}

GAP ANALYSIS:
{json.dumps(gap_analysis, indent=2)}

{coding_block}

Return ONLY valid JSON (no markdown fences):
{{"role": "{role}", "role_type": "{role_type}", "primary_language": "{lang}", "questions": [{{"id": 1, "category": "", "question": "", "competency": "", "why": "", "language": null, "starter_code": null, "difficulty": null}}]}}

Rules: Exactly {total} questions. Questions MUST be specific to THIS candidate resume and THIS JD.
Resume validation must reference actual resume facts. Project questions must use actual project names.
Use gap_analysis skill_gaps to probe weak areas.
Coding questions: language/starter_code/difficulty REQUIRED. Non-coding: these fields must be null.
Return JSON only."""

        response = self.client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        result = json.loads(response.text)
        result.setdefault("role", role)
        result.setdefault("role_type", role_type)
        result.setdefault("primary_language", lang)
        return result

def main() -> None:
    paths = {
        "jd": Path("output/prep/jd.json"),
        "resume": Path("output/prep/resume.json"),
        "gap": Path("output/prep/gap_analysis.json"),
    }
    for p in paths.values():
        if not p.exists():
            raise FileNotFoundError(f"Required file not found: {p}")
    jd = json.loads(paths["jd"].read_text(encoding="utf-8"))
    resume = json.loads(paths["resume"].read_text(encoding="utf-8"))
    gap = json.loads(paths["gap"].read_text(encoding="utf-8"))
    out = Path("output/prep/question_plan.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    plan = QuestionPlanner().create_plan(jd, resume, gap)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to: {out}")

if __name__ == "__main__":
    main()

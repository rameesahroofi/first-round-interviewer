import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


load_dotenv(override=True)


class QuestionPlanner:
    def __init__(self) -> None:
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY")
        )

    def create_plan(
        self,
        jd_data: dict,
        resume_data: dict,
        gap_analysis: dict,
    ) -> dict:

        prompt = f"""
You are an expert technical interview question planner.

Create a structured interview plan using the Job Description,
Candidate Resume, and Gap Analysis.

JOB DESCRIPTION:
{json.dumps(jd_data, indent=2)}

CANDIDATE RESUME:
{json.dumps(resume_data, indent=2)}

GAP ANALYSIS:
{json.dumps(gap_analysis, indent=2)}

Create EXACTLY 12 interview questions.

Use this exact distribution:

- 2 resume validation questions
- 3 JD skills / competencies questions
- 2 project deep-dive questions
- 2 scenario / problem-solving questions
- 2 behavioral questions
- 1 candidate questions question

Return ONLY valid JSON using this structure:

{{
    "questions": [
        {{
            "id": 1,
            "category": "",
            "question": "",
            "competency": "",
            "why": ""
        }}
    ]
}}

Rules:

- Return exactly 12 questions.
- Follow the required category distribution exactly.
- Questions must be relevant to the provided JD and resume.
- Use the gap analysis to identify areas that should be verified.
- Resume validation questions should verify claims made by the candidate.
- JD skills questions should test important job requirements.
- Project questions should reference actual projects from the resume.
- Scenario questions should test practical problem-solving.
- Behavioral questions should evaluate professional behavior and collaboration.
- The final question must invite the candidate to ask questions.
- Avoid duplicate questions.
- Do not invent resume experience or job requirements.
- Keep questions suitable for a first-round interview.
- Return JSON only.
"""

        response = self.client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
            },
        )

        return json.loads(response.text)


def main() -> None:
    jd_path = Path("output/prep/jd.json")
    resume_path = Path("output/prep/resume.json")
    gap_path = Path("output/prep/gap_analysis.json")
    output_path = Path("output/prep/question_plan.json")

    if not jd_path.exists():
        raise FileNotFoundError(
            f"JD data not found: {jd_path}"
        )

    if not resume_path.exists():
        raise FileNotFoundError(
            f"Resume data not found: {resume_path}"
        )

    if not gap_path.exists():
        raise FileNotFoundError(
            f"Gap analysis not found: {gap_path}"
        )

    jd_data = json.loads(
        jd_path.read_text(encoding="utf-8")
    )

    resume_data = json.loads(
        resume_path.read_text(encoding="utf-8")
    )

    gap_analysis = json.loads(
        gap_path.read_text(encoding="utf-8")
    )

    planner = QuestionPlanner()

    question_plan = planner.create_plan(
        jd_data,
        resume_data,
        gap_analysis,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            question_plan,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("Question plan created successfully.")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
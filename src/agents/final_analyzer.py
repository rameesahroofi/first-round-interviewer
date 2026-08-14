
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


load_dotenv(override=True)


class FinalAnalyzer:
    def __init__(self) -> None:
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY")
        )

    def analyze(
        self,
        jd: dict,
        resume: dict,
        gap_analysis: dict,
        answer_evaluation: dict,
    ) -> dict:

        prompt = f"""
You are an AI interview performance analyzer.

Analyze the candidate's complete interview performance using
the information provided below.

JOB DESCRIPTION:
{json.dumps(jd, indent=2)}

RESUME:
{json.dumps(resume, indent=2)}

GAP ANALYSIS:
{json.dumps(gap_analysis, indent=2)}

ANSWER EVALUATIONS:
{json.dumps(answer_evaluation, indent=2)}

Produce a final structured assessment of the candidate.

Return ONLY valid JSON using this structure:

{{
    "overall_score": 0,
    "technical_score": 0,
    "communication_score": 0,
    "jd_alignment_score": 0,
    "strengths": [],
    "weaknesses": [],
    "technical_gaps": [],
    "communication_gaps": [],
    "improvement_plan": [],
    "summary": "",
    "recommendation": ""
}}

Rules:

- overall_score = overall interview performance from 0 to 100.
- technical_score = technical performance from 0 to 100.
- communication_score = communication quality from 0 to 100.
- jd_alignment_score = how well the candidate matches the job description from 0 to 100.
- strengths = specific strengths demonstrated by the candidate.
- weaknesses = specific weaknesses demonstrated during the interview.
- technical_gaps = technical areas that need improvement.
- communication_gaps = communication areas that need improvement.
- improvement_plan = practical actions the candidate should take.
- summary = concise overall assessment.
- recommendation must be one of:
  "Strong Candidate"
  "Good Candidate"
  "Needs Improvement"
  "Not Recommended"

Important:
- Base the analysis only on the information provided.
- Do not invent skills, experience, or achievements.
- Do not assume that a skill exists just because it appears in the JD.
- Consider both the resume and actual interview performance.
- Use the answer evaluations to determine interview performance.
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


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def main() -> None:

    jd = load_json(
        Path("output/prep/jd.json")
    )

    resume = load_json(
        Path("output/prep/resume.json")
    )

    gap_analysis = load_json(
        Path("output/prep/gap_analysis.json")
    )

    answer_evaluation = load_json(
        Path("output/prep/answer_evaluation.json")
    )

    analyzer = FinalAnalyzer()

    final_analysis = analyzer.analyze(
        jd=jd,
        resume=resume,
        gap_analysis=gap_analysis,
        answer_evaluation=answer_evaluation,
    )

    output_path = Path(
        "output/prep/final_analysis.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            final_analysis,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("Final analysis generated successfully.")
    print(f"Saved to: {output_path}")
    print()
    print(json.dumps(
        final_analysis,
        indent=2
    ))


if __name__ == "__main__":
    main()


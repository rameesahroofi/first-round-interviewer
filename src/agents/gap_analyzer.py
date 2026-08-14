import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


load_dotenv(override=True)


class GapAnalyzer:
    def __init__(self) -> None:
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY")
        )

    def analyze(self, jd_data: dict, resume_data: dict) -> dict:
        prompt = f"""
You are an interview preparation gap analyzer.

Compare the Job Description with the Candidate Resume.

JOB DESCRIPTION:
{json.dumps(jd_data, indent=2)}

CANDIDATE RESUME:
{json.dumps(resume_data, indent=2)}

Return ONLY valid JSON using this structure:

{{
    "matched_skills": [],
    "skill_gaps": [],
    "verification_areas": [],
    "candidate_strengths": []
}}

Rules:
- matched_skills = requirements from the JD that are supported by the resume
- skill_gaps = important JD requirements that are not clearly demonstrated in the resume
- verification_areas = skills or claims that should be verified through interview questions
- candidate_strengths = areas where the resume provides strong evidence
- Do not invent information.
- Base the analysis only on the provided JD and resume.
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
    output_path = Path("output/prep/gap_analysis.json")

    if not jd_path.exists():
        raise FileNotFoundError(
            f"JD data not found: {jd_path}"
        )

    if not resume_path.exists():
        raise FileNotFoundError(
            f"Resume data not found: {resume_path}"
        )

    jd_data = json.loads(
        jd_path.read_text(encoding="utf-8")
    )

    resume_data = json.loads(
        resume_path.read_text(encoding="utf-8")
    )

    analyzer = GapAnalyzer()

    gap_analysis = analyzer.analyze(
        jd_data,
        resume_data,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            gap_analysis,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("Gap analysis completed successfully.")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
"""
src/agents/resume_rater.py  -  Gemini-backed CV/resume rater
"""
import json
import os
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)


class ResumeRater:
    def __init__(self) -> None:
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    def rate(self, resume_text: str, jd_text: str = "") -> dict:
        jd_section = f"""
TARGET JOB DESCRIPTION (use for alignment scoring):
{jd_text}
""" if jd_text.strip() else "No JD provided - rate on general best practices only."

        prompt = f"""You are an expert resume reviewer and career coach.

Evaluate this resume and provide structured, actionable feedback.

RESUME:
{resume_text}

{jd_section}

Return ONLY valid JSON (no markdown fences):
{{
    "overall_score": 0,
    "ats_score": 0,
    "bullet_quality_score": 0,
    "structure_score": 0,
    "jd_alignment_score": 0,
    "issues": [
        {{
            "category": "ats|bullets|structure|keywords|formatting|other",
            "issue": "",
            "example": "",
            "severity": "high"
        }}
    ],
    "rewrites": [
        {{
            "original": "",
            "improved": "",
            "reason": ""
        }}
    ],
    "strengths": [],
    "summary": ""
}}

Rules:
- All scores are 0-100.
- ats_score: how well the resume will parse through ATS systems (formatting, standard section headers, etc.)
- bullet_quality_score: quality of experience bullets (impact-driven with metrics vs vague duties)
- structure_score: completeness and organization of sections
- jd_alignment_score: only if JD was provided; otherwise set to null
- issues: specific problems found - not generic advice. Reference actual text.
- rewrites: 2-3 concrete before/after bullet improvements using ACTUAL bullets from the resume.
- severity: one of "high", "medium", "low"
- strengths: what the resume does well
- Two different resumes must produce measurably different scores and different specific issues.
- Return JSON only."""

        response = self.client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return json.loads(response.text)

"""
src/agents/linkedin_optimizer.py  -  Gemini-backed LinkedIn profile optimizer
"""
import json
import os
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)


class LinkedInOptimizer:
    def __init__(self) -> None:
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    def analyze(self, profile_text: str) -> dict:
        prompt = f"""You are an expert LinkedIn profile coach.

Analyze the following LinkedIn profile text and provide structured optimization feedback.

PROFILE TEXT:
{profile_text}

Return ONLY valid JSON (no markdown fences):
{{
    "section_scores": {{
        "headline": 0,
        "about": 0,
        "experience": 0,
        "skills": 0,
        "overall_completeness": 0
    }},
    "overall_score": 0,
    "issues": [
        {{
            "section": "",
            "issue": "",
            "severity": "high"
        }}
    ],
    "rewrites": [
        {{
            "section": "",
            "original": "",
            "suggested_rewrite": "",
            "reason": ""
        }}
    ],
    "summary": ""
}}

Rules:
- Scores are 0-100.
- Identify specific, non-generic issues tied to what was actually written.
- Provide rewrite suggestions for the weakest 2-3 sections only.
- severity: one of "high", "medium", "low"
- Issues must be specific to this profile - not boilerplate advice.
- Rewrites must reference actual text from the profile.
- Return JSON only."""

        response = self.client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return json.loads(response.text)

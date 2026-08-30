"""
src/agents/code_evaluator.py  -  Gemini-backed code evaluation
"""
import json
import os
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)


class CodeEvaluator:
    def __init__(self) -> None:
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    def evaluate(
        self,
        question: str,
        code: str,
        language: str,
        stdout: str = "",
        stderr: str = "",
        competency: str = "",
    ) -> dict:
        prompt = f"""You are an expert code reviewer and technical interview evaluator.

INTERVIEW CODING QUESTION:
{question}

COMPETENCY BEING EVALUATED:
{competency}

CANDIDATE'S CODE ({language}):
`{language}
{code}
`

EXECUTION RESULT:
stdout: {stdout or "(empty)"}
stderr: {stderr or "(none)"}

Evaluate the code on correctness, efficiency, and quality.

Return ONLY valid JSON (no markdown fences):
{{
    "score": 0,
    "correctness": 0,
    "efficiency": 0,
    "code_quality": 0,
    "passed_execution": true,
    "strengths": [],
    "weaknesses": [],
    "feedback": "",
    "recommendation": ""
}}

Rules:
- score: overall 0-100
- correctness: does the code solve the problem correctly? 0-100
- efficiency: time/space complexity quality. 0-100
- code_quality: readability, naming, structure. 0-100
- passed_execution: true if stderr is empty and stdout looks correct
- strengths: specific things done well
- weaknesses: specific issues with the code
- feedback: constructive improvement suggestions
- recommendation: one of "Strong", "Good", "Needs Improvement", "Poor"
- Base analysis only on the code provided. Do not invent facts.
- Return JSON only."""

        response = self.client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return json.loads(response.text)

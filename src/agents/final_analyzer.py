"""
src/agents/final_analyzer.py  -  Updated with code_submissions + integrity sections
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv(override=True)


class FinalAnalyzer:
    def __init__(self) -> None:
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    def analyze(
        self,
        jd: dict,
        resume: dict,
        gap_analysis: dict,
        answer_evaluation: dict,
        code_submissions: list | None = None,
        integrity_flags: list | None = None,
        flagged_for_review: bool = False,
        speech_metrics: dict | None = None,
        body_language_metrics: dict | None = None,
    ) -> dict:

        code_section = ""
        if code_submissions:
            code_section = f"""
CODE SUBMISSIONS (coding questions answered):
{json.dumps(code_submissions, indent=2)}
"""

        integrity_section = ""
        if integrity_flags:
            integrity_section = f"""
INTEGRITY FLAGS (proctoring events):
flagged_for_review: {flagged_for_review}
{json.dumps(integrity_flags, indent=2)}
"""

        speech_section = ""
        if speech_metrics:
            speech_section = f"""
SPEECH METRICS (filler words & speaking pace):
{json.dumps(speech_metrics, indent=2)}
"""

        body_language_section = ""
        if body_language_metrics:
            body_language_section = f"""
BODY LANGUAGE METRICS (eye contact & posture):
{json.dumps(body_language_metrics, indent=2)}
"""

        prompt = f"""You are an AI interview performance analyzer.

Analyze the candidate's complete interview performance.

JOB DESCRIPTION:
{json.dumps(jd, indent=2)}

RESUME:
{json.dumps(resume, indent=2)}

GAP ANALYSIS:
{json.dumps(gap_analysis, indent=2)}

ANSWER EVALUATIONS:
{json.dumps(answer_evaluation, indent=2)}
{code_section}
{integrity_section}
{speech_section}
{body_language_section}

Return ONLY valid JSON (no markdown fences):
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
    "recommendation": "",
    "code_performance": {{
        "attempted": 0,
        "passed": 0,
        "average_score": 0,
        "notes": ""
    }},
    "integrity": {{
        "flagged_for_review": false,
        "flag_count": 0,
        "flags": [],
        "notes": ""
    }},
    "speech_analysis": {{
        "wpm": 0,
        "total_filler_words": 0,
        "feedback": ""
    }},
    "body_language_analysis": {{
        "eye_contact_score": 0,
        "feedback": ""
    }}
}}

Rules:
- overall_score: 0-100 based on ALL evaluated dimensions
- technical_score: consider both verbal answers AND code submissions if present
- communication_score: clarity, structure, completeness (incorporate speech analysis & filler words)
- jd_alignment_score: how well candidate matches the JD
- recommendation: one of "Strong Candidate", "Good Candidate", "Needs Improvement", "Not Recommended"
- code_performance: summarize code submission results (0s if no code submissions)
- integrity: always include; set flagged_for_review and populate flags if proctoring data present
- speech_analysis: populate using SPEECH METRICS. Provide constructive feedback on filler words (like "um") and pace (WPM).
- body_language_analysis: populate using BODY LANGUAGE METRICS. Provide feedback on posture and eye contact score.
- Base analysis only on provided information. Do not invent skills or achievements.
- Return JSON only."""

        response = self.client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        result = json.loads(response.text)

        # Always ensure integrity section reflects submitted flags even if LLM drops it
        if "integrity" not in result:
            result["integrity"] = {}
        result["integrity"]["flagged_for_review"] = flagged_for_review
        result["integrity"]["flag_count"] = len(integrity_flags or [])
        result["integrity"].setdefault("flags", integrity_flags or [])

        return result


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    jd = load_json(Path("output/prep/jd.json"))
    resume = load_json(Path("output/prep/resume.json"))
    gap_analysis = load_json(Path("output/prep/gap_analysis.json"))
    answer_evaluation = load_json(Path("output/prep/answer_evaluation.json"))

    final_analysis = FinalAnalyzer().analyze(
        jd=jd,
        resume=resume,
        gap_analysis=gap_analysis,
        answer_evaluation=answer_evaluation,
    )

    out = Path("output/prep/final_analysis.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(final_analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Final analysis generated successfully.")
    print(f"Saved to: {out}")


if __name__ == "__main__":
    main()

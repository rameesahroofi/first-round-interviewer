# src/agents/explainable_evaluator.py
import json
from typing import Dict, Any

class ExplainableEvaluator:
    """
    Evaluates candidate responses to produce evidence-backed score breakdowns 
    and STAR behavioral metrics.
    """
    
    SYSTEM_EVALUATION_PROMPT = """
You are an expert interview evaluator. Analyze the candidate's answer based on the job role and question asked.
Return ONLY a valid JSON object matching this schema:
{
  "score": <number 1-10>,
  "technical_accuracy": <number 1-10 or null if non-technical>,
  "communication_score": <number 1-10>,
  "evidence_rationale": "<Detailed explanation justifying the score with direct reference to what candidate said>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "weaknesses": ["<weakness 1>", "<weakness 2>"],
  "improvement_recommendation": "<Specific guidance on how to answer better>",
  "tech_mentioned": ["<tool/framework 1>", "<tool/framework 2>"],
  "star_analysis": {
     "is_behavioral_question": <true/false>,
     "situation": "<Present/Weak/Missing>",
     "task": "<Present/Weak/Missing>",
     "action": "<Present/Weak/Missing>",
     "result": "<Present/Weak/Missing>",
     "star_feedback": "<Feedback specifically on STAR structure>"
  }
}
Do NOT include Markdown code fence tags. Return raw JSON only.
"""

    @staticmethod
    def parse_and_validate_evaluation(llm_raw_response: str) -> Dict[str, Any]:
        """Validates AI response structure to ensure valid scores and justification."""
        try:
            clean_str = llm_raw_response.strip()
            if clean_str.startswith("```"):
                clean_str = clean_str.split("```")[1]
                if clean_str.startswith("json"):
                    clean_str = clean_str[4:]
            data = json.loads(clean_str.strip())
            
            if "score" not in data or not isinstance(data["score"], (int, float)):
                data["score"] = 5.0
            if "evidence_rationale" not in data:
                data["evidence_rationale"] = "Evaluation provided without inline evidence."
            return data
            
        except (json.JSONDecodeError, Exception):
            return {
                "score": 5.0,
                "technical_accuracy": None,
                "communication_score": 5.0,
                "evidence_rationale": "Recorded turn evaluation fallback.",
                "strengths": ["Answer recorded"],
                "weaknesses": ["Evaluation structure unverified"],
                "improvement_recommendation": "Structure responses with clear context and results.",
                "tech_mentioned": [],
                "star_analysis": {
                    "is_behavioral_question": False,
                    "situation": "Unverified",
                    "task": "Unverified",
                    "action": "Unverified",
                    "result": "Unverified",
                    "star_feedback": "N/A"
                }
            }
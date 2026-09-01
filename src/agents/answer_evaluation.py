import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


load_dotenv(override=True)


class AnswerEvaluator:
    def __init__(self) -> None:
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY")
        )

    def evaluate(
        self,
        question: str,
        answer: str,
        competency: str,
    ) -> dict:

        prompt = f"""
You are an AI interview answer evaluator.

Evaluate the candidate's answer to the interview question below.

INTERVIEW QUESTION:
{question}

COMPETENCY BEING EVALUATED:
{competency}

CANDIDATE ANSWER:
{answer}

Evaluate the answer fairly and objectively.

Return ONLY valid JSON using this structure:

{{
    "score": 0,
    "relevance": 0,
    "technical_quality": 0,
    "communication": 0,
    "strengths": [],
    "weaknesses": [],
    "feedback": "",
    "recommendation": "",
    "star_analysis": {{
        "situation": false,
        "task": false,
        "action": false,
        "result": false,
        "missing_parts": []
    }}
}}

Rules:

- score = overall score from 0 to 100
- relevance = how directly the answer addresses the question, from 0 to 100
- technical_quality = technical correctness and depth, from 0 to 100
- communication = clarity, structure, and completeness, from 0 to 100
- strengths = specific things the candidate did well
- weaknesses = specific areas that could be improved
- feedback = concise constructive feedback for the candidate
- recommendation = one of:
  "Strong"
  "Good"
  "Needs Improvement"
  "Poor"
- star_analysis = Check whether the answer follows the STAR method (Situation, Task, Action, Result). 
  Set the booleans to true if present, false otherwise. Add missing parts to `missing_parts`.
- Do not invent information that is not present in the candidate's answer.
- Evaluate the answer according to the competency.
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

    input_path = Path(
        "output/prep/answers.json"
    )

    output_path = Path(
        "output/prep/answer_evaluation.json"
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"Answers file not found: {input_path}"
        )

    answers_data = json.loads(
        input_path.read_text(encoding="utf-8")
    )

    answers = answers_data.get("answers", [])

    if not answers:
        raise ValueError(
            "No interview answers were found."
        )

    evaluator = AnswerEvaluator()

    evaluations = []

    for answer_data in answers:

        question_id = answer_data.get(
            "question_id"
        )

        question = answer_data.get(
            "question",
            ""
        )

        answer = answer_data.get(
            "candidate_answer",
            ""
        )

        competency = answer_data.get(
            "competency",
            ""
        )

        print(
            f"Evaluating question {question_id}..."
        )

        evaluation = evaluator.evaluate(
            question=question,
            answer=answer,
            competency=competency,
        )

        evaluations.append(
            {
                "question_id": question_id,
                "question": question,
                "competency": competency,
                "candidate_answer": answer,
                "evaluation": evaluation,
            }
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            {
                "evaluations": evaluations
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "All answers evaluated successfully."
    )

    print(
        f"Evaluated {len(evaluations)} answers."
    )

    print(
        f"Saved to: {output_path}"
    )


if __name__ == "__main__":
    main()
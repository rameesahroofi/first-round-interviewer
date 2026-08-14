import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


load_dotenv(override=True)


class AnswerExtractor:
    def __init__(self) -> None:
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY")
        )

    def extract(self) -> dict:
        transcript_path = Path(
            "output/prep/interview_transcript.json"
        )

        questions_path = Path(
            "output/prep/approved_plan.json"
        )

        output_path = Path(
            "output/prep/answers.json"
        )

        if not transcript_path.exists():
            raise FileNotFoundError(
                f"Interview transcript not found: {transcript_path}"
            )

        if not questions_path.exists():
            raise FileNotFoundError(
                f"Approved interview plan not found: {questions_path}"
            )

        transcript = json.loads(
            transcript_path.read_text(encoding="utf-8")
        )

        questions = json.loads(
            questions_path.read_text(encoding="utf-8")
        )

        prompt = f"""
You are an interview answer extraction system.

Your job is to match the candidate's answers from the interview
transcript to the approved interview questions.

APPROVED INTERVIEW QUESTIONS:

{json.dumps(questions, indent=2, ensure_ascii=False)}

INTERVIEW TRANSCRIPT:

{json.dumps(transcript, indent=2, ensure_ascii=False)}

Return ONLY valid JSON using this structure:

{{
    "answers": [
        {{
            "question_id": 1,
            "question": "",
            "category": "",
            "competency": "",
            "candidate_answer": ""
        }}
    ]
}}

RULES:

- Match candidate answers to the correct approved question.
- Preserve the candidate's meaning.
- Do not invent information.
- Do not evaluate or score the candidate.
- Do not add strengths or weaknesses.
- Include only information supported by the transcript.
- If an approved question was not answered, use an empty string.
- Combine relevant follow-up answers when they belong to the same
  approved question.
- Keep the original question, category, and competency from the
  approved interview plan.
- Return JSON only.
"""

        response = self.client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
            },
        )

        result = json.loads(response.text)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return result


def main() -> None:
    extractor = AnswerExtractor()

    result = extractor.extract()

    print("Answers extracted successfully.")
    print(
        f"Extracted {len(result.get('answers', []))} answers."
    )
    print(
        "Saved to: output/prep/answers.json"
    )


if __name__ == "__main__":
    main()
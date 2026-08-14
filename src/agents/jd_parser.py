import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai


load_dotenv(override=True)


class JDParser:
    def __init__(self) -> None:
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY")
        )

    def parse(self, jd_text: str) -> dict:
        prompt = f"""
You are a job description parser.

Analyze the following job description and extract the information
into structured JSON.

JOB DESCRIPTION:
{jd_text}

Return ONLY valid JSON using this structure:

{{
    "role": "",
    "seniority": "",
    "competencies": [],
    "must_haves": [],
    "nice_to_haves": [],
    "responsibilities": [],
    "technologies": []
}}

Rules:
- competencies = major skills or competency areas required for the role
- must_haves = explicitly required qualifications or skills
- nice_to_haves = preferred but non-essential qualifications
- responsibilities = important duties mentioned in the JD
- technologies = specific tools, languages, frameworks, platforms, or technologies
- seniority = infer from the JD when possible
- Do not invent information that is not supported by the JD.
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
    input_path = Path("inputs/jd.txt")
    output_path = Path("output/prep/jd.json")

    if not input_path.exists():
        raise FileNotFoundError(
            f"Job description not found: {input_path}"
        )

    jd_text = input_path.read_text(encoding="utf-8")

    parser = JDParser()
    jd_data = parser.parse(jd_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(jd_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"JD parsed successfully.")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
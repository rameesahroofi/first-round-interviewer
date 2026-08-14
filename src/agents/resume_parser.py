import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from pypdf import PdfReader


load_dotenv(override=True)


class ResumeParser:
    def __init__(self) -> None:
        self.client = genai.Client(
            api_key=os.getenv("GOOGLE_API_KEY")
        )

    def extract_text(self, pdf_path: Path) -> str:
        reader = PdfReader(pdf_path)

        text = ""

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        return text

    def parse(self, resume_text: str) -> dict:
        prompt = f"""
You are a resume parser.

Analyze the following candidate resume and extract the information
into structured JSON.

RESUME:
{resume_text}

Return ONLY valid JSON using this structure:

{{
    "candidate_name": "",
    "education": [],
    "skills": [],
    "experience": [],
    "projects": [],
    "certifications": [],
    "achievements": []
}}

Rules:
- Extract only information supported by the resume.
- Do not invent qualifications, experience, skills, or achievements.
- Preserve important technical details.
- Include project descriptions when available.
- Include technologies mentioned in projects or experience.
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
    input_path = Path("inputs/resume.pdf")
    output_path = Path("output/prep/resume.json")

    if not input_path.exists():
        raise FileNotFoundError(
            f"Resume not found: {input_path}"
        )

    parser = ResumeParser()

    resume_text = parser.extract_text(input_path)

    if not resume_text.strip():
        raise ValueError(
            "No text could be extracted from the resume PDF."
        )

    resume_data = parser.parse(resume_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(resume_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Resume parsed successfully.")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
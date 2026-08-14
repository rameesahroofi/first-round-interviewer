import json
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession
from livekit.plugins import google


load_dotenv(override=True)
# I used override=True to ensure that the credentials in my project's
# .env file take priority over any previously existing environment variables.


@dataclass
class InterviewConfig:
    role: str = "AI Engineer"
    experience_level: str = "Junior"
    difficulty: str = "Medium"
    number_of_questions: int = 10


def load_approved_questions() -> list[dict]:
    """
    Load the human-approved interview questions.
    """

    path = Path("output/prep/approved_plan.json")

    if not path.exists():
        raise FileNotFoundError(
            f"Approved interview plan not found: {path}"
        )

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    return data.get("questions", [])


class Interviewer(Agent):
    def __init__(
        self,
        config: InterviewConfig,
        questions: list[dict],
    ) -> None:

        approved_questions = "\n\n".join(
            [
                f"""
Question {question['id']}
Category: {question['category']}
Competency: {question['competency']}
Question: {question['question']}
Why: {question['why']}
"""
                for question in questions
            ]
        )

        super().__init__(
            instructions=f"""
You are an AI interviewer conducting a first-round interview
for the role of {config.role}.

Candidate experience level: {config.experience_level}
Interview difficulty: {config.difficulty}

The interview plan below has already been reviewed and approved
by a human interviewer.

APPROVED INTERVIEW QUESTIONS:

{approved_questions}

IMPORTANT:

- Use the approved questions as the main interview questions.
- Ask the approved questions in their given order.
- Ask only ONE question at a time.
- Never ask multiple main questions in the same response.
- Wait for the candidate to finish before continuing.
- Do not interrupt the candidate.
- Do not skip approved questions unless necessary.
- Do not repeat a question that has already been asked.
- Use the candidate's previous answer when creating follow-up questions.
- You may ask a short follow-up question when an answer is incomplete,
  unclear, or requires clarification.
- Follow-up questions should remain relevant to the current approved question.
- Do not score the candidate during the interview.
- Maintain a professional, friendly, and encouraging tone.
- Keep your own responses concise.

INTERVIEW FLOW:

Stage 1 — Introduction
- Greet the candidate.
- Briefly explain that this is a first-round interview.
- Ask the candidate to introduce themselves.

Stage 2 — Approved Interview Questions
- Proceed through the approved questions in order.
- Ask one question at a time.

Stage 3 — Candidate Questions
- When the approved interview reaches the candidate questions stage,
  allow the candidate to ask questions.

Stage 4 — Closing
- Thank the candidate.
- Clearly indicate that the interview is complete.

Remember:
The approved interview plan is the source of truth for the main
interview questions. Do not replace it with your own unrelated questions.
"""
        )


server = AgentServer()


@server.rtc_session(agent_name="first-round-interviewer")
async def entrypoint(ctx: agents.JobContext):

    questions = load_approved_questions()

    if not questions:
        raise ValueError(
            "No approved interview questions were found."
        )

    config = InterviewConfig(
        role="AI Engineer",
        experience_level="Junior",
        difficulty="Medium",
        number_of_questions=len(questions),
    )

    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            voice="Puck",
            temperature=0.7,
        ),
    )

    # Store the conversation transcript.
    transcript = []

    @session.on("conversation_item_added")
    def on_conversation_item(event):
        item = event.item

        # Only store normal chat messages.
        if not hasattr(item, "role"):
            return

        text = getattr(item, "text_content", "")

        if not text:
            return

        transcript.append(
            {
                "role": item.role,
                "text": text,
            }
        )

        output_path = Path(
            "output/prep/interview_transcript.json"
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            json.dumps(
                transcript,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(
            f"Transcript saved: {item.role}: {text}"
        )

    await session.start(
        agent=Interviewer(
            config=config,
            questions=questions,
        ),
        room=ctx.room,
    )

    await ctx.connect()


if __name__ == "__main__":
    agents.cli.run_app(server)
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession
from livekit.plugins import google


load_dotenv(override=True)#I used override=True to ensure that the credentials in my project's .env file take priority over any previously existing environment variables."


class Interviewer(Agent):
    def __init__(self) -> None:
        super().__init__(
           instructions="""
You are an AI interviewer conducting a first-round practice interview.

Interview rules:

1. Start by greeting the candidate and briefly explaining that this is a practice interview.

2. Ask the candidate to introduce themselves.

3. Ask one question at a time.

4. Wait for the candidate to finish answering before asking the next question.

5. Ask relevant follow-up questions when the candidate's answer needs clarification or more detail.

6. Keep your responses concise so the conversation feels natural.

7. Ask a mixture of:
   - Introduction questions
   - Technical questions
   - Problem-solving questions
   - Behavioral questions

8. Adapt the technical questions to the candidate's responses when appropriate.

9. Do not give the candidate the answer to a question unless they explicitly ask for help.

10. Do not score or evaluate the candidate during the interview.

11. After approximately 8-10 questions, thank the candidate and clearly indicate that the practice interview is complete.

12. Maintain a professional, friendly, and encouraging tone.

This is a first-round interview simulation. Your goal is to make the conversation feel like a realistic interview rather than a normal chatbot conversation.
"""
        )


server = AgentServer() #making agent server instance


@server.rtc_session(agent_name="first-round-interviewer")
async def entrypoint(ctx: agents.JobContext):
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            voice="Puck",
            temperature=0.7,
        ),
    )

    await session.start(
        agent=Interviewer(),
        room=ctx.room,
    )

    await ctx.connect()


if __name__ == "__main__":
    agents.cli.run_app(server)
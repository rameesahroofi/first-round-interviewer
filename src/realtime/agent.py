import json
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession
from livekit.plugins import google


load_dotenv(override=True)


OUTPUT_DIR = Path("output/prep")


def load_json_safe(path: Path, default=None):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def load_approved_questions() -> list[dict]:
    path = OUTPUT_DIR / "approved_plan.json"
    if not path.exists():
        raise FileNotFoundError(f"Approved interview plan not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("questions", [])


def load_candidate_context() -> dict:
    """Load resume, gap analysis, and plan metadata for injecting into the prompt."""
    resume = load_json_safe(OUTPUT_DIR / "resume.json", {})
    gap = load_json_safe(OUTPUT_DIR / "gap_analysis.json", {})
    plan = load_json_safe(OUTPUT_DIR / "question_plan.json", {})
    prefs = load_json_safe(OUTPUT_DIR / "preferences.json", {})

    name = resume.get("candidate_name", "the candidate")
    skills = resume.get("skills", [])[:8]
    experience = resume.get("experience", [])[:3]
    projects = resume.get("projects", [])[:2]
    skill_gaps = gap.get("skill_gaps", [])[:5]
    strengths = gap.get("candidate_strengths", [])[:3]
    role = plan.get("role", "the applied role")

    exp_summary = "; ".join(
        f"{e.get('title', '')} at {e.get('company', '')}" for e in experience if isinstance(e, dict)
    ) or "not specified"

    proj_summary = "; ".join(
        p.get("name", "") if isinstance(p, dict) else str(p) for p in projects
    ) or "not specified"

    return {
        "name": name,
        "role": role,
        "skills_summary": ", ".join(str(s) for s in skills) or "not listed",
        "experience_summary": exp_summary,
        "projects_summary": proj_summary,
        "skill_gaps": skill_gaps,
        "strengths": strengths,
        "persona": prefs.get("persona", "Friendly HR"),
        "language": prefs.get("language", "English"),
    }


class Interviewer(Agent):
    def __init__(self, questions: list[dict], ctx: dict) -> None:
        name = ctx["name"]
        role = ctx["role"]
        skills = ctx["skills_summary"]
        experience = ctx["experience_summary"]
        projects = ctx["projects_summary"]
        gaps = ctx["skill_gaps"]
        strengths = ctx["strengths"]
        persona = ctx.get("persona", "Friendly HR")
        language = ctx.get("language", "English")

        gaps_str = ", ".join(str(g) for g in gaps) if gaps else "none identified"
        strengths_str = ", ".join(str(s) for s in strengths) if strengths else "none identified"

        approved_questions = "\n\n".join(
            f"Question {q['id']} [{q['category']}]\n"
            f"Competency: {q['competency']}\n"
            f"Question: {q['question']}\n"
            f"Why asked: {q['why']}"
            for q in questions
        )

        persona_instructions = {
            "Friendly HR": "You are warm, encouraging, and supportive. Focus on making the candidate comfortable.",
            "Strict HR": "You are highly professional, stoic, and direct. Keep pleasantries to a minimum and maintain a formal tone.",
            "Technical Interviewer": "You are a senior engineer. Focus deeply on the technical details and push the candidate to explain the 'how' and 'why'.",
            "Behavioral/Culture Fit": "You are focused on the candidate's core values, teamwork, and how they handle conflicts. Probe heavily into their soft skills."
        }.get(persona, "Professional, encouraging, and genuinely curious.")

        language_instruction = f"IMPORTANT: You MUST conduct the entire interview in {language}. If the language is an Urdu-English mix, seamlessly blend both languages as is common in Pakistan (using Urdu grammar with English technical terms). However, the approved questions are provided in English; you must TRANSLATE them naturally on the fly into {language} when asking them."

        super().__init__(
            instructions=f"""You are an expert human interviewer conducting a Vetto interview
for the role of {role}. You are speaking with {name}.

Your Persona: {persona}
{persona_instructions}

{language_instruction}

CANDIDATE CONTEXT (use this to personalize every interaction):
- Name: {name}
- Applying for: {role}
- Key skills: {skills}
- Experience: {experience}
- Projects: {projects}
- Identified skill gaps (probe harder here): {gaps_str}
- Demonstrated strengths: {strengths_str}

APPROVED INTERVIEW QUESTIONS:

{approved_questions}

BEHAVIORAL RULES (follow these strictly — they define your interviewing style):

1. NEVER jump silently from one topic to the next. Always acknowledge what the candidate
   just said before moving on. Example: "Got it — thanks for walking me through that.
   That's helpful context." or "Interesting approach, especially the part about [X]."

2. ALWAYS paraphrase-and-transition: briefly reflect back a key point from their answer,
   then bridge to the next question. Never read the next question cold without a transition.

3. PACING RULE:
   - If the answer was solid and complete: move on after one brief acknowledgment.
   - If the answer was vague, very short, or unclear: ask exactly ONE clarifying follow-up
     tied to the same approved question, then proceed regardless of the follow-up answer.
   - Never fish for more after a strong answer.

4. GAP PROBE RULE: When the current question touches on a skill in the gaps list
   ({gaps_str}), probe one level deeper than you normally would on the follow-up.

5. PERSONALIZATION: Reference the candidate's actual experience and projects when
   transitioning between topics. Use their name naturally (not every turn — just when
   it fits). Example: "You mentioned earlier that you worked on [project name]..."

6. STAGE 1 — GREETING: Greet {name} by name. Reference one specific thing from their
   resume (a project or skill) to show you've read it. Example: "I noticed you worked on
   [actual project] — I'm looking forward to discussing that."

7. STAGE 2 — QUESTIONS: Proceed through approved questions in order. Ask one at a time.
   Never ask two approved questions in the same turn.

8. STAGE 3 — CANDIDATE QUESTIONS: When reaching the candidate_questions item, hand
   the floor to {name} warmly and answer any questions they have briefly.

9. STAGE 4 — CLOSING: Thank {name} by name. Reference one thing they said that stood out.
   Clearly indicate the interview is complete. Keep it warm and professional.

10. TONE: {persona_instructions}

11. DEAD AIR IS FORBIDDEN: Every response must either acknowledge the previous answer,
    ask a follow-up, or transition to the next question. Never respond with only the
    next question verbatim without any transition.

IMPORTANT: Do not score the candidate during the interview. Do not reveal which
competencies you are testing. Follow the approved question list as the source of truth.
"""
        )


server = AgentServer()


@server.rtc_session(agent_name="first-round-interviewer")
async def entrypoint(ctx: agents.JobContext):

    questions = load_approved_questions()

    if not questions:
        raise ValueError("No approved interview questions were found.")

    candidate_ctx = load_candidate_context()

    # Build the realtime model with server-side VAD for barge-in support
    try:
        realtime_model = google.realtime.RealtimeModel(
            voice="Puck",
            temperature=0.7,
            turn_detection=google.realtime.TurnDetection(type="server_vad"),
        )
    except (TypeError, AttributeError):
        # Older plugin version without TurnDetection - fall back to default
        realtime_model = google.realtime.RealtimeModel(
            voice="Puck",
            temperature=0.7,
        )

    session = AgentSession(llm=realtime_model)

    transcript = []

    @session.on("conversation_item_added")
    def on_conversation_item(event):
        item = event.item
        if not hasattr(item, "role"):
            return
        text = getattr(item, "text_content", "")
        if not text:
            return
        transcript.append({"role": item.role, "text": text})
        output_path = Path("output/prep/interview_transcript.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(transcript, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Transcript: {item.role}: {text[:80]}...")

    await session.start(
        agent=Interviewer(questions=questions, ctx=candidate_ctx),
        room=ctx.room,
    )

    await ctx.connect()


if __name__ == "__main__":
    agents.cli.run_app(server)

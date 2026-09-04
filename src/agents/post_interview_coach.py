# src/agents/post_interview_coach.py
from typing import Dict, Any, List
from src.agents.report_and_progress import ProgressTrackerDB

class PostInterviewCoachAgent:
    """
    Handles post-interview Q&A grounded strictly in interview transcripts/memory,
    and analyzes historical weaknesses to seed the next practice session.
    """

    @classmethod
    def answer_candidate_query(cls, query: str, session_data: Dict[str, Any]) -> str:
        """
        Answers candidate questions about their performance strictly using session telemetry.
        """
        query_lower = query.lower()
        
        if "score" in query_lower or "overall" in query_lower:
            return (f"Your overall score was {session_data.get('overall_score', 0)}/100. "
                    f"Technical Knowledge: {session_data.get('technical_score', 0)}/100, "
                    f"Communication: {session_data.get('communication_score', 0)}/100.")

        if "communication" in query_lower or "speaking" in query_lower or "pace" in query_lower:
            speech = session_data.get("speech_analysis", {})
            wpm = speech.get("wpm", session_data.get("wpm", 0))
            fillers = speech.get("total_filler_words", session_data.get("filler_count", 0))
            return (f"Your speaking pace was {wpm} WPM with a total of "
                    f"{fillers} filler words detected.")

        if "weak" in query_lower or "improve" in query_lower:
            weaknesses = session_data.get("weak_areas", session_data.get("weaknesses", []))
            if weaknesses:
                return f"Main improvement target: Focus on {', '.join(weaknesses)}."
            return "You performed strongly across all evaluated criteria."

        return "I can explain your overall score, speaking pace, communication breakdown, or specific questions from your transcript."

    @classmethod
    def plan_next_interview_focus(cls) -> Dict[str, Any]:
        """
        Analyzes historical weaknesses from ProgressTrackerDB to generate 
        targeted focus areas for the candidate's next practice interview.
        """
        history = ProgressTrackerDB.load_history()
        if not history:
            return {
                "target_focus": "Balanced Foundational Assessment",
                "recommended_difficulty": "normal",
                "emphasis": ["General Technical Concepts", "STAR Behavioral Formatting"]
            }

        latest_session = history[-1]
        weaknesses = latest_session.get("weak_areas", [])
        
        emphasis = []
        if latest_session.get("communication_score", 10) < 7:
            emphasis.append("Communication Structure & Concise Explanations")
        if latest_session.get("technical_score", 10) < 7:
            emphasis.append("Deep Technical Architecture & Code Trade-offs")
        if latest_session.get("filler_count", 0) > 10:
            emphasis.append("Speaking Cadence & Eliminating Filler Words")

        if not emphasis:
            emphasis.append("Advanced System Design & Scalability Challenges")

        return {
            "target_focus": f"Targeted Improvement Session for {latest_session.get('job_role')}",
            "recommended_difficulty": "challenging" if latest_session.get("overall_score", 0) >= 7.5 else "normal",
            "emphasis": emphasis
        }
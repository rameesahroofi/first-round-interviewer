# src/realtime/session_memory.py
from typing import List, Dict, Any, Optional

class InterviewSessionMemory:
    """
    Maintains state across the interview session including candidate claims,
    technical tools mentioned, turn history, and flagged weak/strong areas.
    """
    def __init__(self, session_id: str, candidate_name: str = "Candidate", job_role: str = "Software Engineer"):
        self.session_id: str = session_id
        self.candidate_name: str = candidate_name
        self.job_role: str = job_role
        
        # Claims extracted from resume & JD parsing
        self.extracted_claims: List[Dict[str, Any]] = []
        
        # Real-time interview tracking
        self.technologies_mentioned: List[str] = []
        self.topics_covered: List[str] = []
        self.weak_areas: List[Dict[str, Any]] = []
        self.strong_areas: List[Dict[str, Any]] = []
        self.contradictions: List[Dict[str, Any]] = []
        
        # Granular turn history
        self.turn_history: List[Dict[str, Any]] = []

    def record_turn(self, question_id: str, question: str, answer: str, evaluation: Dict[str, Any]):
        """Records an answer turn and updates real-time analytics state."""
        score = evaluation.get("score", 0)
        
        turn_data = {
            "question_id": question_id,
            "question": question,
            "answer": answer,
            "score": score,
            "strengths": evaluation.get("strengths", []),
            "weaknesses": evaluation.get("weaknesses", []),
            "tech_mentioned": evaluation.get("tech_mentioned", [])
        }
        self.turn_history.append(turn_data)
        
        if question_id not in self.topics_covered:
            self.topics_covered.append(question_id)

        # Track tools & frameworks candidate explicitly brings up
        for tech in evaluation.get("tech_mentioned", []):
            if tech.lower() not in [t.lower() for t in self.technologies_mentioned]:
                self.technologies_mentioned.append(tech)

        # Classify weak vs strong performances
        if score < 6:
            self.weak_areas.append({
                "question": question,
                "score": score,
                "reason": evaluation.get("weaknesses", [])
            })
        elif score >= 8:
            self.strong_areas.append({
                "question": question,
                "score": score,
                "reason": evaluation.get("strengths", [])
            })

    def log_contradiction(self, earlier_statement: str, new_statement: str, topic: str):
        """Logs detected statement discrepancies for human or AI clarification."""
        self.contradictions.append({
            "topic": topic,
            "earlier_statement": earlier_statement,
            "new_statement": new_statement,
            "resolved": False
        })

    def get_prompt_context(self) -> str:
        """Returns a clean context string to inject into interviewer LLM prompts."""
        return f"""
INTERVIEW SESSION MEMORY:
- Candidate Name: {self.candidate_name}
- Target Role: {self.job_role}
- Tech Stack Introduced by Candidate: {', '.join(self.technologies_mentioned) if self.technologies_mentioned else 'None yet'}
- Covered Question IDs ({len(self.topics_covered)}): {', '.join(self.topics_covered)}
- Identified Weak Areas: {[w['question'] for w in self.weak_areas]}
- Demonstrated Strengths: {[s['question'] for s in self.strong_areas]}
- Active Contradictions to Clarify: {len([c for c in self.contradictions if not c['resolved']])}
"""
# src/agents/adaptive_planner.py
from typing import Dict, Any, List
from src.realtime.session_memory import InterviewSessionMemory

class AdaptivePlannerAgent:
    """
    Decides the next interview action (Follow-up vs Next Approved Root Question)
    while enforcing human-approval guardrails and depth limits.
    """
    def __init__(self, max_followup_depth: int = 2):
        self.max_followup_depth = max_followup_depth

    def plan_next_step(
        self,
        current_question: Dict[str, Any],
        candidate_answer: str,
        evaluation: Dict[str, Any],
        memory: InterviewSessionMemory,
        approved_question_bank: List[Dict[str, Any]],
        current_followup_depth: int
    ) -> Dict[str, Any]:
        """
        Determines whether to ask an approved follow-up branch, generate a controlled 
        dynamic probe, or move to the next human-approved question.
        """
        score = evaluation.get("score", 10)
        
        # Guardrail 1: Enforce maximum follow-up depth per topic
        if current_followup_depth >= self.max_followup_depth:
            return self._get_next_approved_root(approved_question_bank, memory)

        # Guardrail 2: Check for Pre-Approved Branch (Option A)
        approved_branches = current_question.get("approved_followups", [])
        if approved_branches:
            if score < 6:
                probe_branch = next((b for b in approved_branches if b.get("type") == "probe"), None)
                if probe_branch:
                    return {
                        "action": "ASK_FOLLOWUP",
                        "question_text": probe_branch["text"],
                        "source": "PRE_APPROVED_PROBE"
                    }
            elif score >= 8:
                challenge_branch = next((b for b in approved_branches if b.get("type") == "challenge"), None)
                if challenge_branch:
                    return {
                        "action": "ASK_FOLLOWUP",
                        "question_text": challenge_branch["text"],
                        "source": "PRE_APPROVED_CHALLENGE"
                    }

        # Guardrail 3: Dynamic Adaptive Directives (Option B - Controlled Scope)
        if score < 6:
            return {
                "action": "GENERATE_DYNAMIC_FOLLOWUP",
                "directive": "PROBE_WEAKNESS",
                "topic": current_question.get("topic", "General"),
                "instruction": f"Candidate struggled (Score: {score}/10). Ask a focused clarification question on {current_question.get('topic')}."
            }
        elif score >= 8 and current_question.get("difficulty") != "hard":
            return {
                "action": "GENERATE_DYNAMIC_FOLLOWUP",
                "directive": "CHALLENGE_MASTERY",
                "topic": current_question.get("topic", "General"),
                "instruction": f"Candidate mastered response (Score: {score}/10). Ask a deeper technical scenario/edge-case follow-up."
            }

        # Fallback: Move to next approved root question
        return self._get_next_approved_root(approved_question_bank, memory)

    def _get_next_approved_root(self, question_bank: List[Dict[str, Any]], memory: InterviewSessionMemory) -> Dict[str, Any]:
        for q in question_bank:
            if q["id"] not in memory.topics_covered:
                return {
                    "action": "ASK_ROOT_QUESTION",
                    "question_id": q["id"],
                    "question_text": q["text"],
                    "source": "APPROVED_BANK"
                }
        return {"action": "END_INTERVIEW", "message": "All human-approved questions completed."}
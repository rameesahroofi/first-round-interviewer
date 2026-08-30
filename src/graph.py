"""
src/graph.py  -  LangGraph pipeline: resume_parser -> jd_parser -> gap_analyzer -> question_planner
"""
import json
import os
import tempfile
from pathlib import Path
from typing import TypedDict, Optional

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from src.agents.resume_parser import ResumeParser
from src.agents.jd_parser import JDParser
from src.agents.gap_analyzer import GapAnalyzer
from src.agents.question_planner import QuestionPlanner

load_dotenv(override=True)

OUTPUT_DIR = Path("output/prep")


class PipelineState(TypedDict):
    role: str
    jd_text: str
    resume_bytes: bytes
    resume_data: Optional[dict]
    jd_data: Optional[dict]
    gap_analysis: Optional[dict]
    question_plan: Optional[dict]
    error: Optional[str]


# ------------------------------------------------------------------ nodes

def node_parse_resume(state: PipelineState) -> PipelineState:
    try:
        parser = ResumeParser()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(state["resume_bytes"])
            tmp_path = Path(tmp.name)
        text = parser.extract_text(tmp_path)
        tmp_path.unlink(missing_ok=True)
        if not text.strip():
            raise ValueError("No text could be extracted from the resume PDF.")
        resume_data = parser.parse(text)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / "resume.json").write_text(
            json.dumps(resume_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {**state, "resume_data": resume_data, "error": None}
    except Exception as e:
        return {**state, "error": f"resume_parser: {e}"}


def node_parse_jd(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    try:
        jd_data = JDParser().parse(state["jd_text"])
        (OUTPUT_DIR / "jd.json").write_text(
            json.dumps(jd_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {**state, "jd_data": jd_data}
    except Exception as e:
        return {**state, "error": f"jd_parser: {e}"}


def node_gap_analysis(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    try:
        gap = GapAnalyzer().analyze(state["jd_data"], state["resume_data"])
        (OUTPUT_DIR / "gap_analysis.json").write_text(
            json.dumps(gap, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {**state, "gap_analysis": gap}
    except Exception as e:
        return {**state, "error": f"gap_analyzer: {e}"}


def node_plan_questions(state: PipelineState) -> PipelineState:
    if state.get("error"):
        return state
    try:
        plan = QuestionPlanner().create_plan(
            state["jd_data"], state["resume_data"], state["gap_analysis"], state["role"]
        )
        (OUTPUT_DIR / "question_plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {**state, "question_plan": plan}
    except Exception as e:
        return {**state, "error": f"question_planner: {e}"}


# ------------------------------------------------------------------ graph

def _build_graph():
    g = StateGraph(PipelineState)
    g.add_node("parse_resume", node_parse_resume)
    g.add_node("parse_jd", node_parse_jd)
    g.add_node("gap_analysis", node_gap_analysis)
    g.add_node("plan_questions", node_plan_questions)
    g.set_entry_point("parse_resume")
    g.add_edge("parse_resume", "parse_jd")
    g.add_edge("parse_jd", "gap_analysis")
    g.add_edge("gap_analysis", "plan_questions")
    g.add_edge("plan_questions", END)
    return g.compile()


_pipeline = _build_graph()


def run_pipeline(role: str, jd_text: str, resume_bytes: bytes) -> dict:
    """
    Run the full interview-prep pipeline.
    Returns the final state dict.
    Raises RuntimeError if any node set an error.
    """
    initial: PipelineState = {
        "role": role,
        "jd_text": jd_text,
        "resume_bytes": resume_bytes,
        "resume_data": None,
        "jd_data": None,
        "gap_analysis": None,
        "question_plan": None,
        "error": None,
    }
    final = _pipeline.invoke(initial)
    if final.get("error"):
        raise RuntimeError(final["error"])
    return final

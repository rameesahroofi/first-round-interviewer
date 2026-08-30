import json
from pathlib import Path

import streamlit as st


QUESTION_PLAN_PATH = Path("output/prep/question_plan.json")
APPROVED_PLAN_PATH = Path("output/prep/approved_plan.json")
FINAL_ANALYSIS_PATH = Path("output/prep/final_analysis.json")
FINAL_REPORT_PATH = Path("output/prep/final_report.md")
RESUME_PATH = Path("output/prep/resume.json")
JD_PATH = Path("output/prep/jd.json")
GAP_ANALYSIS_PATH = Path("output/prep/gap_analysis.json")

if "plan_approved" not in st.session_state:
    st.session_state.plan_approved = APPROVED_PLAN_PATH.exists()

st.set_page_config(
    page_title="Interview Question Review",
    page_icon="🎤",
    layout="wide",
)

st.title("🎤 Interview Question Review")
st.write(
    "Review and edit the AI-generated interview questions "
    "before starting the interview."
)

# --------------------------------------------------
# CONTEXT PANEL: Resume / JD / Gap Analysis Summary
# --------------------------------------------------

with st.expander("📋 Candidate & Role Context (click to expand)", expanded=True):
    col1, col2 = st.columns(2)

    with col1:
        if RESUME_PATH.exists():
            resume = json.loads(RESUME_PATH.read_text(encoding="utf-8"))
            st.subheader("👤 Candidate Summary")
            st.write(f"**Name:** {resume.get('candidate_name', 'Not found')}")

            skills = resume.get("skills", [])
            if skills:
                st.write(f"**Skills:** {', '.join(str(s) for s in skills[:12])}")

            experience = resume.get("experience", [])
            if experience:
                st.write("**Experience:**")
                for exp in experience[:3]:
                    if isinstance(exp, dict):
                        title = exp.get("title", "")
                        company = exp.get("company", "")
                        st.write(f"  - {title} @ {company}")
                    else:
                        st.write(f"  - {exp}")

            projects = resume.get("projects", [])
            if projects:
                st.write("**Projects:**")
                for proj in projects[:3]:
                    if isinstance(proj, dict):
                        st.write(f"  - {proj.get('name', proj)}")
                    else:
                        st.write(f"  - {proj}")
        else:
            st.info("Resume data not found. Run /api/prepare first.")

    with col2:
        if JD_PATH.exists():
            jd = json.loads(JD_PATH.read_text(encoding="utf-8"))
            st.subheader("💼 Job Description Summary")
            st.write(f"**Role:** {jd.get('role', 'Not found')}")
            st.write(f"**Seniority:** {jd.get('seniority', 'Not specified')}")
            must_haves = jd.get("must_haves", [])
            if must_haves:
                st.write("**Must Haves:**")
                for m in must_haves[:5]:
                    st.write(f"  - {m}")
        else:
            st.info("JD data not found.")

        if GAP_ANALYSIS_PATH.exists():
            gap = json.loads(GAP_ANALYSIS_PATH.read_text(encoding="utf-8"))
            st.subheader("⚠️ Gap Analysis")
            gaps = gap.get("skill_gaps", [])
            if gaps:
                st.write("**Skill Gaps (probe harder):**")
                for g in gaps[:5]:
                    st.write(f"  - ⚠️ {g}")
            strengths = gap.get("candidate_strengths", [])
            if strengths:
                st.write("**Candidate Strengths:**")
                for s in strengths[:4]:
                    st.write(f"  - ✅ {s}")

st.divider()

# --------------------------------------------------
# QUESTION REVIEW
# --------------------------------------------------

if not QUESTION_PLAN_PATH.exists():
    st.error(f"Question plan not found: {QUESTION_PLAN_PATH}")
    st.stop()

question_plan = json.loads(QUESTION_PLAN_PATH.read_text(encoding="utf-8"))
questions = question_plan.get("questions", [])

role = question_plan.get("role", "")
role_type = question_plan.get("role_type", "")
if role:
    st.info(f"**Role:** {role} | **Type:** {role_type.replace('_', ' ').title()}")

st.subheader(f"Generated Questions ({len(questions)})")

edited_questions = []

for question in questions:
    qid = question.get("id", "?")
    cat = question.get("category", "")
    
    icon = "💻" if cat == "coding" else "❓"
    st.markdown(f"### {icon} Question {qid} [{cat}]")

    category = st.text_input(
        "Category",
        value=cat,
        key=f"category_{qid}",
    )

    question_text = st.text_area(
        "Question",
        value=question.get("question", ""),
        key=f"question_{qid}",
    )

    competency = st.text_input(
        "Competency",
        value=question.get("competency", ""),
        key=f"competency_{qid}",
    )

    why = st.text_area(
        "Why this question?",
        value=question.get("why", ""),
        key=f"why_{qid}",
    )

    edited_q = {
        "id": qid,
        "category": category,
        "question": question_text,
        "competency": competency,
        "why": why,
        "language": question.get("language"),
        "starter_code": question.get("starter_code"),
        "difficulty": question.get("difficulty"),
    }

    if cat == "coding":
        st.markdown("**💻 Coding Question Details**")
        lang = st.text_input("Language", value=question.get("language", "python"), key=f"lang_{qid}")
        difficulty = st.selectbox("Difficulty", ["easy", "medium", "hard"],
                                  index=["easy", "medium", "hard"].index(question.get("difficulty", "medium")),
                                  key=f"diff_{qid}")
        starter = st.text_area("Starter Code", value=question.get("starter_code", ""), key=f"starter_{qid}")
        edited_q["language"] = lang
        edited_q["difficulty"] = difficulty
        edited_q["starter_code"] = starter

    edited_questions.append(edited_q)
    st.divider()

# --------------------------------------------------
# APPROVE BUTTON
# --------------------------------------------------

if st.button("✅ Approve Interview Plan", type="primary"):
    approved_plan = {"questions": edited_questions}
    APPROVED_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    APPROVED_PLAN_PATH.write_text(
        json.dumps(approved_plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    st.session_state.plan_approved = True
    st.success("Interview plan approved successfully!")
    st.write(f"Saved to: {APPROVED_PLAN_PATH}")

# --------------------------------------------------
# RESULTS SECTION (always visible when approved)
# --------------------------------------------------

if st.session_state.plan_approved:
    st.divider()
    st.header("📊 Interview Results")

if not FINAL_ANALYSIS_PATH.exists():
    st.info("Final interview analysis is not available yet.")
else:
    final_analysis = json.loads(FINAL_ANALYSIS_PATH.read_text(encoding="utf-8"))

    st.subheader("Performance Scores")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Overall", f"{final_analysis.get('overall_score', 0)}/100")
    with col2:
        st.metric("Technical", f"{final_analysis.get('technical_score', 0)}/100")
    with col3:
        st.metric("Communication", f"{final_analysis.get('communication_score', 0)}/100")
    with col4:
        st.metric("JD Alignment", f"{final_analysis.get('jd_alignment_score', 0)}/100")

    st.divider()
    st.subheader("🎯 Recommendation")
    st.write(final_analysis.get("recommendation", "Not available"))

    st.subheader("📝 Summary")
    st.write(final_analysis.get("summary", "No summary available."))

    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("💪 Strengths")
        for s in final_analysis.get("strengths", []):
            st.write(f"- {s}")
        st.subheader("🧑‍💻 Technical Gaps")
        for g in final_analysis.get("technical_gaps", []):
            st.write(f"- {g}")
    with col_r:
        st.subheader("⚠️ Weaknesses")
        for w in final_analysis.get("weaknesses", []):
            st.write(f"- {w}")
        st.subheader("💬 Communication Gaps")
        for cg in final_analysis.get("communication_gaps", []):
            st.write(f"- {cg}")

    st.subheader("📚 Improvement Plan")
    for item in final_analysis.get("improvement_plan", []):
        st.write(f"- {item}")

    # Code Submissions Section
    code_perf = final_analysis.get("code_performance", {})
    if code_perf and code_perf.get("attempted", 0) > 0:
        st.divider()
        st.subheader("💻 Code Performance")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Attempted", code_perf.get("attempted", 0))
        with c2:
            st.metric("Passed", code_perf.get("passed", 0))
        with c3:
            st.metric("Avg Score", f"{code_perf.get('average_score', 0)}/100")
        if code_perf.get("notes"):
            st.write(code_perf["notes"])

    # Integrity Section
    integrity = final_analysis.get("integrity", {})
    if integrity:
        st.divider()
        flagged = integrity.get("flagged_for_review", False)
        flag_count = integrity.get("flag_count", 0)
        if flagged:
            st.error(f"⚠️ FLAGGED FOR REVIEW — {flag_count} integrity violations detected")
        elif flag_count > 0:
            st.warning(f"⚠️ {flag_count} minor integrity event(s) noted")
        else:
            st.success("✅ No integrity issues detected")

        flags = integrity.get("flags", [])
        if flags:
            with st.expander("View integrity flag details"):
                for flag in flags:
                    st.write(f"- **{flag.get('type', '')}** at {flag.get('timestamp', '')} — {flag.get('details', '')}")

    if FINAL_REPORT_PATH.exists():
        st.divider()
        st.subheader("📄 Full Interview Report")
        st.markdown(FINAL_REPORT_PATH.read_text(encoding="utf-8"))

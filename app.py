import json
from pathlib import Path

import streamlit as st


QUESTION_PLAN_PATH = Path("output/prep/question_plan.json")
APPROVED_PLAN_PATH = Path("output/prep/approved_plan.json")
FINAL_ANALYSIS_PATH = Path("output/prep/final_analysis.json")
FINAL_REPORT_PATH = Path("output/prep/final_report.md")
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


if not QUESTION_PLAN_PATH.exists():
    st.error(
        f"Question plan not found: {QUESTION_PLAN_PATH}"
    )
    st.stop()


question_plan = json.loads(
    QUESTION_PLAN_PATH.read_text(
        encoding="utf-8"
    )
)


questions = question_plan.get("questions", [])


st.subheader(
    f"Generated Questions ({len(questions)})"
)


edited_questions = []


for question in questions:

    st.markdown(
        f"### Question {question['id']}"
    )

    category = st.text_input(
        "Category",
        value=question["category"],
        key=f"category_{question['id']}",
    )

    question_text = st.text_area(
        "Question",
        value=question["question"],
        key=f"question_{question['id']}",
    )

    competency = st.text_input(
        "Competency",
        value=question["competency"],
        key=f"competency_{question['id']}",
    )

    why = st.text_area(
        "Why this question?",
        value=question["why"],
        key=f"why_{question['id']}",
    )

    edited_questions.append(
        {
            "id": question["id"],
            "category": category,
            "question": question_text,
            "competency": competency,
            "why": why,
        }
    )

    st.divider()


if st.button(
    "✅ Approve Interview Plan",
    type="primary",
):

    approved_plan = {
        "questions": edited_questions
    }

    APPROVED_PLAN_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    APPROVED_PLAN_PATH.write_text(
        json.dumps(
            approved_plan,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    st.session_state.plan_approved = True

    st.success(
        "Interview plan approved successfully!"
    )

    st.write(
        f"Saved to: {APPROVED_PLAN_PATH}"
    )
    if st.session_state.plan_approved:

      st.divider()

      st.header("📊 Interview Results")

if not FINAL_ANALYSIS_PATH.exists():

    st.info(
        "Final interview analysis is not available yet."
    )

else:

    final_analysis = json.loads(
        FINAL_ANALYSIS_PATH.read_text(
            encoding="utf-8"
        )
    )

    st.subheader("Performance Scores")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Overall",
            f"{final_analysis.get('overall_score', 0)}/100"
        )

    with col2:
        st.metric(
            "Technical",
            f"{final_analysis.get('technical_score', 0)}/100"
        )

    with col3:
        st.metric(
            "Communication",
            f"{final_analysis.get('communication_score', 0)}/100"
        )

    with col4:
        st.metric(
            "JD Alignment",
            f"{final_analysis.get('jd_alignment_score', 0)}/100"
        )

    st.divider()

    st.subheader("🎯 Recommendation")

    st.write(
        final_analysis.get(
            "recommendation",
            "Not available"
        )
    )

    st.subheader("📝 Summary")

    st.write(
        final_analysis.get(
            "summary",
            "No summary available."
        )
    )

    st.subheader("💪 Strengths")

    strengths = final_analysis.get(
        "strengths",
        []
    )

    if strengths:
        for strength in strengths:
            st.write(f"• {strength}")
    else:
        st.write("No strengths reported.")

    st.subheader("⚠️ Weaknesses")

    weaknesses = final_analysis.get(
        "weaknesses",
        []
    )

    if weaknesses:
        for weakness in weaknesses:
            st.write(f"• {weakness}")
    else:
        st.write("No weaknesses reported.")

    st.subheader("🧑‍💻 Technical Gaps")

    technical_gaps = final_analysis.get(
        "technical_gaps",
        []
    )

    if technical_gaps:
        for gap in technical_gaps:
            st.write(f"• {gap}")
    else:
        st.write("No technical gaps reported.")

    st.subheader("💬 Communication Gaps")

    communication_gaps = final_analysis.get(
        "communication_gaps",
        []
    )

    if communication_gaps:
        for gap in communication_gaps:
            st.write(f"• {gap}")
    else:
        st.write("No communication gaps reported.")

    st.subheader("📚 Improvement Plan")

    improvement_plan = final_analysis.get(
        "improvement_plan",
        []
    )

    if improvement_plan:
        for item in improvement_plan:
            st.write(f"• {item}")
    else:
        st.write("No improvement plan available.")

    if FINAL_REPORT_PATH.exists():

        st.divider()

        st.subheader("📄 Full Interview Report")

        report = FINAL_REPORT_PATH.read_text(
            encoding="utf-8"
        )

        st.markdown(report)
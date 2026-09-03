# src/agents/report_and_progress.py
import json
import os
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class ProgressTrackerDB:
    """
    Manages historical session storage for tracking progress, score trends,
    and weak/strong areas across multiple practice interviews.
    """
    DB_FILE = "interview_history.json"

    @classmethod
    def save_session(cls, session_data: Dict[str, Any]) -> None:
        history = cls.load_history()
        session_entry = {
            "session_id": session_data.get("session_id"),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "job_role": session_data.get("job_role", "Software Engineer"),
            "overall_score": session_data.get("overall_score", 0),
            "technical_score": session_data.get("technical_score", 0),
            "communication_score": session_data.get("communication_score", 0),
            "wpm": session_data.get("wpm", 0),
            "filler_count": session_data.get("filler_count", 0),
            "weak_areas": session_data.get("weak_areas", [])
        }
        history.append(session_entry)
        with open(cls.DB_FILE, "w") as f:
            json.dump(history, f, indent=2)

    @classmethod
    def load_history(cls) -> List[Dict[str, Any]]:
        if not os.path.exists(cls.DB_FILE):
            return []
        try:
            with open(cls.DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []


class ProfessionalPDFReportGenerator:
    """
    Generates a PDF coaching report summarizing overall performance, 
    dimensional breakdown, audio analytics, and STAR behavioral evaluations.
    """

    @staticmethod
    def generate_pdf(session_data: Dict[str, Any], output_path: str = "interview_report.pdf") -> str:
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#0F172A'),
            spaceAfter=6
        )
        subtitle_style = ParagraphStyle(
            'SubTitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#475569'),
            spaceAfter=14
        )
        heading2 = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=13,
            textColor=colors.HexColor('#1E293B'),
            spaceBefore=12,
            spaceAfter=6
        )

        story = []

        # Document Header
        story.append(Paragraph("First Round AI — Executive Interview Coaching Report", title_style))
        story.append(Paragraph(
            f"Candidate: <b>{session_data.get('candidate_name', 'Candidate')}</b> | "
            f"Role: <b>{session_data.get('job_role', 'Software Engineer')}</b> | "
            f"Date: <b>{datetime.now().strftime('%Y-%m-%d')}</b>",
            subtitle_style
        ))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceAfter=12))

        # Overall Metrics Summary Table
        metrics_table_data = [
            ["Overall Score", "Technical", "Communication", "Speaking Pace", "Filler Words"],
            [
                f"{session_data.get('overall_score', 0)}/10",
                f"{session_data.get('technical_score', 0)}/10",
                f"{session_data.get('communication_score', 0)}/10",
                f"{session_data.get('wpm', 0)} WPM",
                f"{session_data.get('filler_count', 0)}"
            ]
        ]

        t = Table(metrics_table_data, colWidths=[100, 100, 100, 100, 100])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#0F172A')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
        ]))
        story.append(t)
        story.append(Spacer(1, 10))

        # Question Analysis Section
        story.append(Paragraph("Detailed Question-by-Question Evaluation", heading2))
        for idx, q_item in enumerate(session_data.get("questions", []), 1):
            story.append(Paragraph(f"<b>Q{idx}: {q_item.get('question')}</b> (Score: {q_item.get('score')}/10)", styles['Normal']))
            story.append(Paragraph(f"<i>Answer:</i> {q_item.get('answer')}", styles['Normal']))
            story.append(Paragraph(f"<b>Evaluation Rationale:</b> {q_item.get('rationale')}", styles['Normal']))
            story.append(Spacer(1, 8))

        doc.build(story)
        return output_path
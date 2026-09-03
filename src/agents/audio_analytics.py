# src/agents/audio_analytics.py
import re
from typing import Dict, Any

class AudioAnalyticsEngine:
    """
    Computes transcript speech metrics including Words Per Minute (WPM),
    filler word counts, and speaking pace status.
    """
    
    FILLER_PATTERNS = [
        r'\bum\b', r'\buh\b', r'\blike\b', r'\byou know\b', 
        r'\bbasically\b', r'\bactually\b', r'\bso\b', r'\bi mean\b'
    ]

    @classmethod
    def analyze_transcript_segment(cls, transcript: str, duration_seconds: float) -> Dict[str, Any]:
        if not transcript or duration_seconds <= 0:
            return {
                "word_count": 0,
                "wpm": 0,
                "filler_count": 0,
                "filler_breakdown": {},
                "pace_status": "No Speech Detected",
                "recommendation": "No response transcript captured."
            }

        words = re.findall(r'\b\w+\b', transcript.lower())
        word_count = len(words)
        
        minutes = duration_seconds / 60.0
        wpm = round(word_count / minutes, 1) if minutes > 0 else 0

        filler_breakdown = {}
        total_fillers = 0
        
        for pattern in cls.FILLER_PATTERNS:
            matches = re.findall(pattern, transcript.lower())
            count = len(matches)
            if count > 0:
                clean_key = pattern.replace(r'\b', '').replace('\\', '')
                filler_breakdown[clean_key] = count
                total_fillers += count

        if wpm < 110:
            pace_status = "Slightly Slow"
            recommendation = "Try to maintain steady momentum when explaining complex points."
        elif 110 <= wpm <= 160:
            pace_status = "Optimal Pace"
            recommendation = "Great job maintaining an articulate and readable speaking pace."
        else:
            pace_status = "Slightly Fast"
            recommendation = "Your speaking pace is fast. Pause briefly after delivering key findings."

        return {
            "word_count": word_count,
            "duration_seconds": round(duration_seconds, 1),
            "wpm": wpm,
            "filler_count": total_fillers,
            "filler_breakdown": filler_breakdown,
            "pace_status": pace_status,
            "recommendation": recommendation
        }
// frontend/src/components/ProgressDashboard.tsx
import React, { useEffect, useState } from 'react';

interface SessionHistory {
  session_id: string;
  date: string;
  job_role: string;
  overall_score: number;
  technical_score: number;
  communication_score: number;
  wpm: number;
  filler_count: number;
  weak_areas: string[];
}

export const ProgressDashboard: React.FC = () => {
  const [history, setHistory] = useState<SessionHistory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/interview/history')
      .then((res) => res.json())
      .then((data) => {
        setHistory(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error('Failed to fetch progress history:', err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="p-4 text-slate-300">Loading progress trends...</div>;

  return (
    <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 text-white max-w-4xl mx-auto my-6">
      <h2 className="text-2xl font-bold mb-4 text-indigo-400">Interview Performance Tracker</h2>
      
      {history.length === 0 ? (
        <p className="text-slate-400">No previous interview sessions recorded yet. Complete an interview to start tracking progress!</p>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
              <span className="text-slate-400 text-sm">Total Sessions</span>
              <p className="text-3xl font-bold text-white">{history.length}</p>
            </div>
            <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
              <span className="text-slate-400 text-sm">Latest Score</span>
              <p className="text-3xl font-bold text-emerald-400">
                {history[history.length - 1]?.overall_score || 0}/10
              </p>
            </div>
            <div className="bg-slate-800 p-4 rounded-lg border border-slate-700">
              <span className="text-slate-400 text-sm">Avg Speaking Pace</span>
              <p className="text-3xl font-bold text-blue-400">
                {Math.round(history.reduce((acc, curr) => acc + curr.wpm, 0) / history.length)} WPM
              </p>
            </div>
          </div>

          <h3 className="text-lg font-semibold text-slate-300 mb-2">Past Interviews History</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="p-3">Date</th>
                  <th className="p-3">Role</th>
                  <th className="p-3">Overall Score</th>
                  <th className="p-3">Technical</th>
                  <th className="p-3">Communication</th>
                  <th className="p-3">Pace / Fillers</th>
                </tr>
              </thead>
              <tbody>
                {history.map((session, idx) => (
                  <tr key={idx} className="border-b border-slate-800/50 hover:bg-slate-800/40">
                    <td className="p-3 text-slate-300">{session.date}</td>
                    <td className="p-3 font-medium text-indigo-300">{session.job_role}</td>
                    <td className="p-3 font-bold text-emerald-400">{session.overall_score}/10</td>
                    <td className="p-3">{session.technical_score}/10</td>
                    <td className="p-3">{session.communication_score}/10</td>
                    <td className="p-3 text-slate-400">{session.wpm} WPM ({session.filler_count} fillers)</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
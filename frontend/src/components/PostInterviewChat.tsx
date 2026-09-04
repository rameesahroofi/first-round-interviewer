// frontend/src/components/PostInterviewChat.tsx
import React, { useState } from 'react';

interface PostInterviewChatProps {
  sessionSummary?: any;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const PostInterviewChat: React.FC<PostInterviewChatProps> = ({ sessionSummary }) => {
  const [messages, setMessages] = useState<Array<{ sender: 'user' | 'ai'; text: string }>>([
    { sender: 'ai', text: 'Hello! I am your AI Interview Coach. Ask me anything about your interview scores, speaking pace, or how to improve specific answers!' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userText = input;
    setInput('');
    setMessages((prev) => [...prev, { sender: 'user', text: userText }]);
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/interview/post-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: 'session_' + Date.now(),
          message: userText,
          session_summary: sessionSummary || {}
        })
      });
      const data = await response.json();
      setMessages((prev) => [...prev, { sender: 'ai', text: data.reply }]);
    } catch (error) {
      setMessages((prev) => [...prev, { sender: 'ai', text: 'Sorry, I failed to process that query. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 max-w-2xl mx-auto my-6 text-white flex flex-col h-[450px]">
      <h3 className="text-lg font-bold text-indigo-400 mb-3 border-b border-slate-800 pb-2">
        Post-Interview AI Coach Assistant
      </h3>
      
      <div className="flex-1 overflow-y-auto space-y-3 p-2">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg p-3 text-sm ${
                msg.sender === 'user' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-200 border border-slate-700'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
        {loading && <div className="text-slate-500 text-xs italic">AI Coach is analyzing transcript...</div>}
      </div>

      <div className="flex gap-2 mt-3 pt-2 border-t border-slate-800">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="e.g., Why was my communication score 7?"
          className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
        />
        <button
          onClick={sendMessage}
          className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  );
};
import { useEffect, useRef, useState } from "react";
import { getInterviewChat, sendInterviewChatMessage } from "../../api/historyApi.js";

export default function InterviewChatPanel({ interviewId }) {
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getInterviewChat(interviewId)
      .then((data) => {
        if (!cancelled) setMessages(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this chat. Try refreshing.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [interviewId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const handleSend = async (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;

    setError("");
    setInput("");
    const optimisticUser = { id: `temp-${Date.now()}`, role: "user", content: text };
    setMessages((prev) => [...prev, optimisticUser]);
    setSending(true);

    try {
      const reply = await sendInterviewChatMessage(interviewId, text);
      setMessages((prev) => [...prev, reply]);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't send that. Please try again.");
      setMessages((prev) => prev.filter((m) => m.id !== optimisticUser.id));
      setInput(text);
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-3 text-sm text-slate-400">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        Loading chat…
      </div>
    );
  }

  return (
    <div>
      <p className="mb-2 text-xs font-medium text-slate-500">Ask about this interview</p>
      <div className="flex h-[50vh] flex-col rounded-lg border border-surface-border bg-surface-raised">
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {messages.length === 0 && (
            <p className="text-sm text-slate-500">
              Ask about your weaknesses, how to phrase an answer better, or request extra practice
              questions on this interview's topics.
            </p>
          )}
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
          {sending && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-accent border-t-transparent" />
              Thinking…
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && (
          <p className="mx-4 mb-2 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </p>
        )}

        <form onSubmit={handleSend} className="flex gap-2 border-t border-surface-border p-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a follow-up…"
            disabled={sending}
            className="flex-1 rounded-md border border-surface-border bg-surface px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-accent disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

function MessageBubble({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
          isUser ? "bg-accent text-white" : "border border-surface-border bg-surface text-slate-200"
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}

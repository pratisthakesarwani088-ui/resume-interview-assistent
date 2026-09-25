import { useEffect, useRef, useState } from "react";
import { getChatHistory, sendChatMessage } from "../../api/assistantApi.js";

export default function ChatPanel({ mode, placeholder, roleOptions }) {
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [selectedRole, setSelectedRole] = useState("");
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getChatHistory(mode)
      .then((data) => {
        if (cancelled) return;
        setMessages(data.messages);
        setSelectedRole(data.selected_role || "");
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this conversation. Try refreshing.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [mode]);

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
      const reply = await sendChatMessage(mode, text, roleOptions ? selectedRole : undefined);
      setMessages((prev) => [...prev, reply]);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail || "Couldn't send that. Please try again.");
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
        Loading conversation…
      </div>
    );
  }

  return (
    <div className="flex h-[60vh] flex-col">
      {roleOptions && roleOptions.length > 0 && (
        <div className="mb-3">
          <label className="mb-1 block text-xs text-slate-500">Target role (optional)</label>
          <select
            value={selectedRole}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2 text-sm text-slate-200 outline-none focus:border-accent"
          >
            <option value="">General guidance</option>
            {roleOptions.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-surface-border bg-surface-raised p-4">
        {messages.length === 0 && (
          <p className="text-sm text-slate-500">{placeholder}</p>
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
        <p className="mt-2 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      <form onSubmit={handleSend} className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          disabled={sending}
          className="flex-1 rounded-md border border-surface-border bg-surface-raised px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-accent disabled:opacity-50"
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

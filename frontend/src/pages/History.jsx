import { useEffect, useState } from "react";
import Navbar from "../components/Navbar.jsx";
import InterviewChatPanel from "../components/history/InterviewChatPanel.jsx";
import {
  deleteInterview,
  getInterviewHistoryDetail,
  listInterviewHistory,
  renameInterview,
} from "../api/historyApi.js";

export default function History() {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    listInterviewHistory()
      .then((data) => {
        if (!cancelled) setItems(data);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load your interview history.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleRenamedInList = (id, newTitle) => {
    setItems((prev) => prev.map((it) => (it.id === id ? { ...it, title: newTitle } : it)));
  };

  const handleDeletedInList = (id) => {
    setItems((prev) => prev.filter((it) => it.id !== id));
    setSelectedId(null);
  };

  return (
    <div className="min-h-screen bg-surface">
      <Navbar />
      <main className="mx-auto max-w-3xl px-5 py-10">
        <h1 className="text-lg font-semibold text-slate-50">Interview History</h1>

        {loading && (
          <div className="mt-8 flex items-center gap-3 text-sm text-slate-400">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
            Loading your history…
          </div>
        )}

        {!loading && error && (
          <p className="mt-8 max-w-sm rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </p>
        )}

        {!loading && !error && selectedId === null && (
          <HistoryList items={items} onSelect={setSelectedId} />
        )}

        {!loading && !error && selectedId !== null && (
          <HistoryDetail
            id={selectedId}
            onBack={() => setSelectedId(null)}
            onRenamed={handleRenamedInList}
            onDeleted={handleDeletedInList}
          />
        )}
      </main>
    </div>
  );
}

function HistoryList({ items, onSelect }) {
  if (items.length === 0) {
    return (
      <p className="mt-8 text-sm text-slate-400">
        No completed interviews yet — finish a mock interview in the AI Assistant to see it here.
      </p>
    );
  }

  return (
    <div className="mt-6 space-y-3">
      {items.map((item) => (
        <button
          key={item.id}
          onClick={() => onSelect(item.id)}
          className="block w-full rounded-lg border border-surface-border bg-surface-raised p-4 text-left transition-colors hover:border-accent/50"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-100">{item.title}</p>
              <p className="mt-0.5 text-xs text-slate-500">
                {item.role} · {formatDate(item.date)} · {item.question_count} questions
              </p>
            </div>
            {item.overall_score !== null && (
              <span className="shrink-0 rounded-full bg-accent-soft px-2.5 py-1 text-xs text-accent">
                {item.overall_score}/100
              </span>
            )}
          </div>
        </button>
      ))}
    </div>
  );
}

function HistoryDetail({ id, onBack, onRenamed, onDeleted }) {
  const [loading, setLoading] = useState(true);
  const [interview, setInterview] = useState(null);
  const [error, setError] = useState("");

  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");
  const [savingTitle, setSavingTitle] = useState(false);
  const [titleError, setTitleError] = useState("");

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getInterviewHistoryDetail(id)
      .then((data) => {
        if (cancelled) return;
        setInterview(data);
        setTitleInput(data.title);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load this interview.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const handleSaveTitle = async () => {
    setTitleError("");
    setSavingTitle(true);
    try {
      const updated = await renameInterview(id, titleInput.trim());
      setInterview(updated);
      onRenamed(id, updated.title);
      setEditingTitle(false);
    } catch (err) {
      setTitleError(err.response?.data?.detail || "Couldn't save that title.");
    } finally {
      setSavingTitle(false);
    }
  };

  const handleDelete = async () => {
    setDeleteError("");
    setDeleting(true);
    try {
      await deleteInterview(id);
      onDeleted(id);
    } catch (err) {
      setDeleteError(err.response?.data?.detail || "Couldn't delete this interview.");
      setDeleting(false);
    }
  };

  return (
    <div className="mt-6">
      <button onClick={onBack} className="mb-4 text-sm text-slate-400 hover:text-slate-200">
        ← Back to history
      </button>

      {loading && (
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          Loading…
        </div>
      )}

      {!loading && error && (
        <p className="max-w-sm rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {error}
        </p>
      )}

      {!loading && interview && (
        <div className="space-y-5">
          <div>
            {editingTitle ? (
              <div className="flex flex-wrap items-center gap-2">
                <input
                  value={titleInput}
                  onChange={(e) => setTitleInput(e.target.value)}
                  maxLength={200}
                  autoFocus
                  className="min-w-0 flex-1 rounded-md border border-surface-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 outline-none focus:border-accent"
                />
                <button
                  onClick={handleSaveTitle}
                  disabled={savingTitle}
                  className="rounded-md bg-accent px-3 py-1.5 text-sm text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
                >
                  {savingTitle ? "Saving…" : "Save"}
                </button>
                <button
                  onClick={() => {
                    setEditingTitle(false);
                    setTitleInput(interview.title);
                    setTitleError("");
                  }}
                  className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-slate-300 hover:text-slate-100"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h2 className="text-base font-medium text-slate-100">{interview.title}</h2>
                <button
                  onClick={() => setEditingTitle(true)}
                  className="text-xs text-slate-500 hover:text-accent"
                >
                  Rename
                </button>
              </div>
            )}
            {titleError && <p className="mt-1.5 text-xs text-red-400">{titleError}</p>}
            <p className="mt-1 text-xs text-slate-500">
              {interview.role} · {formatDate(interview.date)}
            </p>
          </div>

          {interview.final_report && <FinalReportCard report={interview.final_report} />}

          <div className="space-y-3">
            <p className="text-xs font-medium text-slate-500">Question-by-question review</p>
            {interview.qa_log.map((qa, i) => (
              <div key={i} className="rounded-lg border border-surface-border bg-surface-raised p-4">
                <p className="text-sm text-slate-200">{qa.question}</p>
                <p className="mt-2 text-sm text-slate-400">
                  <span className="text-slate-500">Your answer: </span>
                  {qa.answer}
                </p>
                <div className="mt-2 flex items-center gap-2 text-xs">
                  <span className="rounded-full bg-accent-soft px-2 py-0.5 text-accent">{qa.score}/10</span>
                </div>
                <p className="mt-2 text-sm text-slate-400">{qa.feedback}</p>
                <p className="mt-2 text-xs text-slate-500">
                  <span className="text-slate-500">Ideal answer: </span>
                  {qa.ideal_answer}
                </p>
              </div>
            ))}
          </div>

          <InterviewChatPanel interviewId={interview.id} />

          <div className="border-t border-surface-border pt-4">
            {!confirmingDelete ? (
              <button
                onClick={() => setConfirmingDelete(true)}
                className="text-sm text-red-400 hover:text-red-300"
              >
                Delete this interview
              </button>
            ) : (
              <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3">
                <p className="text-sm text-red-400">Delete this interview permanently? This can't be undone.</p>
                {deleteError && <p className="mt-1.5 text-xs text-red-400">{deleteError}</p>}
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className="rounded-md bg-red-500/90 px-3 py-1.5 text-sm text-white transition-colors hover:bg-red-500 disabled:opacity-50"
                  >
                    {deleting ? "Deleting…" : "Yes, delete"}
                  </button>
                  <button
                    onClick={() => setConfirmingDelete(false)}
                    className="rounded-md border border-surface-border px-3 py-1.5 text-sm text-slate-300 hover:text-slate-100"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function FinalReportCard({ report }) {
  return (
    <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-5">
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-semibold text-accent">{report.overall_score}</span>
        <span className="text-sm text-slate-500">/ 100</span>
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-xs font-medium text-slate-400">Strengths</p>
          <ul className="mt-1 space-y-1 text-sm text-slate-300">
            {report.strengths.map((s, i) => (
              <li key={i}>• {s}</li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-medium text-slate-400">Weak areas</p>
          <ul className="mt-1 space-y-1 text-sm text-slate-300">
            {report.weak_areas.map((w, i) => (
              <li key={i}>• {w}</li>
            ))}
          </ul>
        </div>
      </div>
      <p className="mt-4 text-sm text-slate-300">{report.feedback}</p>
    </div>
  );
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

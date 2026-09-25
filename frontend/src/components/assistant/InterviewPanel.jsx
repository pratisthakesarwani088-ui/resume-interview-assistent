import { useEffect, useState } from "react";
import { getInterviewStatus, startInterview, submitInterviewAnswer } from "../../api/assistantApi.js";

export default function InterviewPanel({ roleOptions }) {
  const [loading, setLoading] = useState(true);
  const [interview, setInterview] = useState(null);
  const [selectedRole, setSelectedRole] = useState(roleOptions?.[0] || "");
  const [starting, setStarting] = useState(false);
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [showingNewInterview, setShowingNewInterview] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getInterviewStatus()
      .then((data) => {
        if (cancelled) return;
        setInterview(data.has_interview ? data : null);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't check your interview status.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleStart = async (e) => {
    e.preventDefault();
    if (!selectedRole) {
      setError("Choose a role to interview for.");
      return;
    }
    setError("");
    setStarting(true);
    try {
      const data = await startInterview(selectedRole);
      setInterview({ has_interview: true, ...data });
      setShowingNewInterview(false);
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't start the interview. Please try again.");
    } finally {
      setStarting(false);
    }
  };

  const handleSubmitAnswer = async (e) => {
    e.preventDefault();
    const text = answer.trim();
    if (!text || submitting) return;
    setError("");
    setSubmitting(true);
    try {
      const data = await submitInterviewAnswer(text);
      setInterview({ has_interview: true, ...data });
      setAnswer("");
    } catch (err) {
      setError(err.response?.data?.detail || "Couldn't submit that answer. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-3 text-sm text-slate-400">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
        Checking your interview status…
      </div>
    );
  }

  const needsRoleSelection = !interview || showingNewInterview;

  if (needsRoleSelection) {
    return (
      <div className="max-w-sm">
        <p className="mb-4 text-sm text-slate-400">
          Pick a role and start a 10-15 question theory-only mock interview based on your resume.
        </p>
        <form onSubmit={handleStart} className="space-y-3">
          <select
            value={selectedRole}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="w-full rounded-md border border-surface-border bg-surface-raised px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-accent"
          >
            {(!roleOptions || roleOptions.length === 0) && <option value="">No suggested roles yet</option>}
            {roleOptions?.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
          {error && (
            <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={starting || !selectedRole}
            className="w-full rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {starting ? "Starting…" : "Start interview"}
          </button>
        </form>
      </div>
    );
  }

  if (interview.status === "completed") {
    return (
      <div className="max-w-2xl space-y-4">
        <FinalReportCard interview={interview} />
        <QAHistory qaLog={interview.qa_log} />
        <button
          onClick={() => setShowingNewInterview(true)}
          className="rounded-md border border-surface-border px-4 py-2 text-sm text-slate-300 transition-colors hover:border-accent/60 hover:text-slate-100"
        >
          Start a new interview
        </button>
      </div>
    );
  }

  // in_progress
  return (
    <div className="max-w-2xl space-y-4">
      <p className="text-xs text-slate-500">
        {interview.role} — question {interview.current_question_index + 1} of {interview.total_questions}
      </p>

      <div className="rounded-lg border border-surface-border bg-surface-raised p-5">
        <p className="text-sm text-slate-100">{interview.current_question}</p>
      </div>

      <form onSubmit={handleSubmitAnswer} className="space-y-3">
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          rows={5}
          placeholder="Type your answer…"
          disabled={submitting}
          className="w-full resize-none rounded-md border border-surface-border bg-surface-raised px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-accent disabled:opacity-50"
        />
        {error && (
          <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={submitting || !answer.trim()}
          className="rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          {submitting ? "Evaluating…" : "Submit answer"}
        </button>
      </form>

      <QAHistory qaLog={interview.qa_log} />
    </div>
  );
}

function FinalReportCard({ interview }) {
  const report = interview.final_report;
  if (!report) {
    return (
      <div className="rounded-lg border border-surface-border bg-surface-raised p-5">
        <p className="text-sm text-slate-300">
          Interview completed for <span className="text-slate-100">{interview.role}</span>. The summary
          report couldn't be generated, but your answer-by-answer feedback is below.
        </p>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-5">
      <p className="text-sm font-medium text-emerald-400">Interview complete — {interview.role}</p>
      <div className="mt-2 flex items-baseline gap-2">
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

function QAHistory({ qaLog }) {
  if (!qaLog || qaLog.length === 0) return null;
  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-slate-500">Question-by-question review</p>
      {qaLog.map((qa, i) => (
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
  );
}

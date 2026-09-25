export default function AnalysisSection({ analysis, onRetry, retrying }) {
  if (analysis.status === "failed") {
    return (
      <div className="mt-6 max-w-sm rounded-lg border border-red-500/30 bg-red-500/10 p-5">
        <p className="text-sm text-red-400">
          Resume analysis failed. This doesn't affect your uploaded resume.
        </p>
        <button
          onClick={onRetry}
          disabled={retrying}
          className="mt-3 rounded-md border border-red-500/40 px-3 py-1.5 text-sm text-red-300 transition-colors hover:bg-red-500/10 disabled:opacity-50"
        >
          {retrying ? "Retrying…" : "Retry analysis"}
        </button>
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-4">
      <ScoreCard score={analysis.ats_score} />
      <ListCard title="Strengths" items={analysis.strengths} tone="emerald" />
      <ListCard title="Weaknesses" items={analysis.weaknesses} tone="amber" />
      <ListCard title="Skills found" items={analysis.extracted_skills} chips />
      <ListCard title="Projects & experience" items={analysis.projects_experience} />
      <RolesCard roles={analysis.suggested_roles} />
      <ListCard title="Suggestions to improve" items={analysis.improvement_suggestions} />
    </div>
  );
}

function Card({ title, children }) {
  return (
    <section className="rounded-lg border border-surface-border bg-surface-raised p-5">
      <h2 className="text-sm font-medium text-slate-200">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function ScoreCard({ score }) {
  return (
    <Card title="ATS compatibility (estimate)">
      <div className="flex items-baseline gap-2">
        <span className="text-3xl font-semibold text-accent">{score}</span>
        <span className="text-sm text-slate-500">/ 100</span>
      </div>
      <p className="mt-1.5 text-xs text-slate-500">
        An estimate of how well this resume would parse in a typical ATS — not a
        guarantee from any specific system.
      </p>
    </Card>
  );
}

function ListCard({ title, items, tone, chips }) {
  if (!items || items.length === 0) return null;

  if (chips) {
    return (
      <Card title={title}>
        <div className="flex flex-wrap gap-1.5">
          {items.map((item, i) => (
            <span
              key={i}
              className="rounded-full border border-surface-border bg-surface px-2.5 py-1 text-xs text-slate-300"
            >
              {item}
            </span>
          ))}
        </div>
      </Card>
    );
  }

  const dotColor = tone === "emerald" ? "bg-emerald-400" : tone === "amber" ? "bg-amber-400" : "bg-accent";

  return (
    <Card title={title}>
      <ul className="space-y-1.5">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2 text-sm text-slate-300">
            <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${dotColor}`} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function RolesCard({ roles }) {
  if (!roles || roles.length === 0) return null;
  return (
    <Card title="Suggested roles">
      <div className="space-y-4">
        {roles.map((r, i) => (
          <div key={i} className={i > 0 ? "border-t border-surface-border pt-4" : ""}>
            <p className="text-sm font-medium text-slate-200">{r.role}</p>
            {r.required_skills?.length > 0 && (
              <p className="mt-1.5 text-xs text-slate-500">
                Required: <span className="text-slate-400">{r.required_skills.join(", ")}</span>
              </p>
            )}
            {r.missing_skills?.length > 0 && (
              <p className="mt-1 text-xs text-amber-400/90">
                Missing: {r.missing_skills.join(", ")}
              </p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

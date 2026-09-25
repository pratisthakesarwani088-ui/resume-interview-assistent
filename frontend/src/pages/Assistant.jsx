import { useEffect, useState } from "react";
import Navbar from "../components/Navbar.jsx";
import ChatPanel from "../components/assistant/ChatPanel.jsx";
import InterviewPanel from "../components/assistant/InterviewPanel.jsx";
import { getAnalysisStatus } from "../api/analysisApi.js";

const TABS = [
  { key: "resume_expert", label: "Resume Expert" },
  { key: "interviewer", label: "AI Interviewer" },
  { key: "career_coach", label: "Career Coach" },
  { key: "tutor", label: "AI Tutor" },
];

export default function Assistant() {
  const [activeTab, setActiveTab] = useState("resume_expert");
  const [roleOptions, setRoleOptions] = useState([]);

  useEffect(() => {
    getAnalysisStatus()
      .then((data) => {
        if (data.has_analysis && data.analysis.status === "completed") {
          setRoleOptions(data.analysis.suggested_roles.map((r) => r.role));
        }
      })
      .catch(() => {
        // Role suggestions are a nice-to-have here; chat/interview still
        // work without them (career coach falls back to general guidance,
        // interview role selection just shows no suggestions).
      });
  }, []);

  return (
    <div className="min-h-screen bg-surface">
      <Navbar />
      <main className="mx-auto max-w-3xl px-5 py-10">
        <h1 className="text-lg font-semibold text-slate-50">AI Assistant</h1>

        <div className="mt-4 flex flex-wrap gap-2 border-b border-surface-border pb-3">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
                activeTab === tab.key
                  ? "bg-accent text-white"
                  : "text-slate-400 hover:bg-surface-raised hover:text-slate-200"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="mt-6">
          {activeTab === "resume_expert" && (
            <ChatPanel
              mode="resume_expert"
              placeholder="Ask about your ATS score, skills, projects, strengths, weaknesses, or skill gaps."
            />
          )}
          {activeTab === "career_coach" && (
            <ChatPanel
              mode="career_coach"
              placeholder="Ask for career or learning guidance based on your resume."
              roleOptions={roleOptions}
            />
          )}
          {activeTab === "tutor" && (
            <ChatPanel
              mode="tutor"
              placeholder="Ask for an explanation of a concept, or request practice questions."
            />
          )}
          {activeTab === "interviewer" && <InterviewPanel roleOptions={roleOptions} />}
        </div>
      </main>
    </div>
  );
}

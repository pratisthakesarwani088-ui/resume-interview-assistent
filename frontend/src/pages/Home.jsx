import { useEffect, useRef, useState } from "react";
import Navbar from "../components/Navbar.jsx";
import AnalysisSection from "../components/AnalysisSection.jsx";
import { getResumeStatus, uploadResume } from "../api/resumeApi.js";
import { getAnalysisStatus, triggerAnalysis } from "../api/analysisApi.js";

// Mirrors the backend's MAX_RESUME_SIZE_MB default (see backend/.env.example).
const MAX_SIZE_MB = 5;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

export default function Home() {
  const [checking, setChecking] = useState(true);
  const [resume, setResume] = useState(null); // null while unknown/none
  const [selectedFile, setSelectedFile] = useState(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef(null);

  const [analysis, setAnalysis] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getResumeStatus()
      .then((data) => {
        if (cancelled) return;
        setResume(data.has_resume ? data.resume : null);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't check your resume status. Try refreshing the page.");
      })
      .finally(() => {
        if (!cancelled) setChecking(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Once a processed resume is confirmed, check for an existing analysis and
  // auto-run one if there isn't one yet — this is what makes the analysis
  // "just show up on Home after processing" without an extra button.
  useEffect(() => {
    if (!resume || resume.status !== "processed") return;
    let cancelled = false;

    const runAnalysis = async () => {
      setAnalysisError("");
      try {
        const statusData = await getAnalysisStatus();
        if (cancelled) return;
        if (statusData.has_analysis && statusData.analysis.status === "completed") {
          setAnalysis(statusData.analysis);
          return;
        }
        setAnalyzing(true);
        const result = await triggerAnalysis();
        if (!cancelled) setAnalysis(result);
      } catch (err) {
        if (!cancelled) {
          const detail = err.response?.data?.detail;
          setAnalysisError(detail || "Couldn't analyze your resume right now.");
        }
      } finally {
        if (!cancelled) setAnalyzing(false);
      }
    };

    runAnalysis();
    return () => {
      cancelled = true;
    };
  }, [resume]);

  const handleRetryAnalysis = async () => {
    setAnalysisError("");
    setAnalyzing(true);
    try {
      const result = await triggerAnalysis();
      setAnalysis(result);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setAnalysisError(detail || "Couldn't analyze your resume right now.");
    } finally {
      setAnalyzing(false);
    }
  };

  const validateClientSide = (file) => {
    if (!file) return "Please choose a file.";
    if (!file.name.toLowerCase().endsWith(".pdf")) return "Only PDF files are accepted.";
    if (file.type && file.type !== "application/pdf") return "Only PDF files are accepted.";
    if (file.size > MAX_SIZE_BYTES) return `File is too large. Maximum size is ${MAX_SIZE_MB}MB.`;
    if (file.size === 0) return "File is empty.";
    return "";
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0] ?? null;
    setError("");
    setSelectedFile(file);
    if (file) {
      const clientError = validateClientSide(file);
      if (clientError) setError(clientError);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    const clientError = validateClientSide(selectedFile);
    if (clientError) {
      setError(clientError);
      return;
    }
    setError("");
    setUploading(true);
    setProgress(0);
    try {
      const uploaded = await uploadResume(selectedFile, { onProgress: setProgress });
      setResume(uploaded);
      setSelectedFile(null);
    } catch (err) {
      const data = err.response?.data;
      if (err.response?.status === 409) {
        setError(data?.detail || "You've already uploaded a resume.");
      } else if (data?.file) {
        setError(Array.isArray(data.file) ? data.file.join(" ") : String(data.file));
      } else if (data?.detail) {
        setError(data.detail);
      } else {
        setError("Upload failed. Please try again.");
      }
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface">
      <Navbar />
      <main className="mx-auto max-w-3xl px-5 py-10">
        <h1 className="text-lg font-semibold text-slate-50">Home</h1>

        {checking && (
          <div className="mt-8 flex items-center gap-3 text-sm text-slate-400">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
            Checking your resume status…
          </div>
        )}

        {!checking && resume && (
          <ProcessedState
            resume={resume}
            analysis={analysis}
            analyzing={analyzing}
            analysisError={analysisError}
            onRetryAnalysis={handleRetryAnalysis}
          />
        )}

        {!checking && !resume && (
          <UploadForm
            selectedFile={selectedFile}
            error={error}
            uploading={uploading}
            progress={progress}
            fileInputRef={fileInputRef}
            onFileChange={handleFileChange}
            onSubmit={handleUpload}
          />
        )}
      </main>
    </div>
  );
}

function ProcessedState({ resume, analysis, analyzing, analysisError, onRetryAnalysis }) {
  return (
    <div className="mt-8 max-w-2xl">
      <div className="max-w-sm rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-5">
        <div className="flex items-center gap-2 text-emerald-400">
          <CheckIcon />
          <span className="text-sm font-medium">Resume uploaded and processed</span>
        </div>
        <dl className="mt-4 space-y-1.5 text-sm">
          <Row label="File" value={resume.original_filename} />
          <Row label="Pages" value={resume.page_count} />
          <Row label="Uploaded" value={new Date(resume.uploaded_at).toLocaleString()} />
        </dl>
      </div>

      {analyzing && (
        <div className="mt-6 flex max-w-sm items-center gap-3 text-sm text-slate-400">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          Analyzing your resume…
        </div>
      )}

      {!analyzing && analysisError && (
        <div className="mt-6 max-w-sm rounded-lg border border-red-500/30 bg-red-500/10 p-5">
          <p className="text-sm text-red-400">{analysisError}</p>
          <button
            onClick={onRetryAnalysis}
            className="mt-3 rounded-md border border-red-500/40 px-3 py-1.5 text-sm text-red-300 transition-colors hover:bg-red-500/10"
          >
            Retry analysis
          </button>
        </div>
      )}

      {!analyzing && !analysisError && analysis && (
        <AnalysisSection analysis={analysis} onRetry={onRetryAnalysis} retrying={analyzing} />
      )}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-400">{label}</dt>
      <dd className="truncate text-slate-200">{value}</dd>
    </div>
  );
}

function UploadForm({ selectedFile, error, uploading, progress, fileInputRef, onFileChange, onSubmit }) {
  return (
    <div className="mt-8 max-w-sm">
      <p className="mb-4 text-sm text-slate-400">
        Upload your resume as a PDF (up to {MAX_SIZE_MB}MB) to get started.
      </p>

      <form onSubmit={onSubmit} className="space-y-4">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="w-full rounded-lg border border-dashed border-surface-border bg-surface-raised px-4 py-8 text-center text-sm text-slate-400 transition-colors hover:border-accent/60 hover:text-slate-200 disabled:opacity-50"
        >
          {selectedFile ? (
            <span className="text-slate-200">{selectedFile.name}</span>
          ) : (
            <span>Tap to choose a PDF file</span>
          )}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf,.pdf"
          onChange={onFileChange}
          className="hidden"
        />

        {error && (
          <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </p>
        )}

        {uploading && (
          <div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-raised">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="mt-1.5 text-xs text-slate-500">
              {progress < 100 ? `Uploading… ${progress}%` : "Processing your resume…"}
            </p>
          </div>
        )}

        <button
          type="submit"
          disabled={!selectedFile || uploading}
          className="w-full rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          {uploading ? "Uploading…" : "Upload resume"}
        </button>
      </form>
    </div>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
      <path
        fillRule="evenodd"
        d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0l-3.5-3.5a1 1 0 111.4-1.4l2.8 2.8 6.8-6.8a1 1 0 011.4 0z"
        clipRule="evenodd"
      />
    </svg>
  );
}

import { analysisApi } from "./axios.js";

export async function getAnalysisStatus() {
  const { data } = await analysisApi.get("/me/");
  return data; // { has_resume, has_analysis, analysis? }
}

export async function triggerAnalysis() {
  const { data } = await analysisApi.post("/analyze/");
  return data; // the serialized ResumeAnalysis
}

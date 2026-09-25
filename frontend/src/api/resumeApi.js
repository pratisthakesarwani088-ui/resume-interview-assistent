import { resumesApi } from "./axios.js";

export async function getResumeStatus() {
  const { data } = await resumesApi.get("/me/");
  return data; // { has_resume: false } | { has_resume: true, resume: {...} }
}

export async function uploadResume(file, { onProgress } = {}) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await resumesApi.post("/upload/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded * 100) / event.total));
      }
    },
  });
  return data; // the serialized Resume
}
